// lib/services/offline_queue.dart
// =================================
// Hive-backed offline complaint queue with automatic sync on reconnect.
//
// Dependencies (pubspec.yaml):
//   hive: ^2.2.3
//   hive_flutter: ^1.1.0
//   connectivity_plus: ^5.0.2  (existing: ^6.0.3 is compatible)
//
// Usage:
//   await OfflineQueue.init();
//   await OfflineQueue.enqueue(draft);
//   await OfflineQueue.processQueue(apiService);

import 'dart:async';
import 'dart:convert';
import 'dart:developer' as dev;
import 'dart:io';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:hive_flutter/hive_flutter.dart';

// ── Typed draft ───────────────────────────────────────────────────────────────

class ComplaintDraft {
  final String imagePath;
  final double latitude;
  final double longitude;
  final String? address;
  final String? nearbySensitive;
  final String? areaType;
  final DateTime createdAt;
  int retryCount;

  ComplaintDraft({
    required this.imagePath,
    required this.latitude,
    required this.longitude,
    this.address,
    this.nearbySensitive,
    this.areaType,
    DateTime? createdAt,
    this.retryCount = 0,
  }) : createdAt = createdAt ?? DateTime.now();

  Map<String, dynamic> toJson() => {
        'imagePath': imagePath,
        'latitude': latitude,
        'longitude': longitude,
        'address': address,
        'nearbySensitive': nearbySensitive,
        'areaType': areaType,
        'createdAt': createdAt.toIso8601String(),
        'retryCount': retryCount,
      };

  factory ComplaintDraft.fromJson(Map<String, dynamic> json) => ComplaintDraft(
        imagePath: json['imagePath'] as String,
        latitude: (json['latitude'] as num).toDouble(),
        longitude: (json['longitude'] as num).toDouble(),
        address: json['address'] as String?,
        nearbySensitive: json['nearbySensitive'] as String?,
        areaType: json['areaType'] as String?,
        createdAt: DateTime.tryParse(json['createdAt'] as String? ?? '') ?? DateTime.now(),
        retryCount: (json['retryCount'] as int?) ?? 0,
      );
}

// ── Offline Queue ─────────────────────────────────────────────────────────────

class OfflineQueue {
  static const String _boxName = 'offline_complaints';
  static Box<String>? _box;
  static StreamSubscription<List<ConnectivityResult>>? _connectivitySub;

  // ── Init ────────────────────────────────────────────────────────────────────
  /// Call once at app startup (e.g. in main()).
  static Future<void> init() async {
    await Hive.initFlutter();
    _box = await Hive.openBox<String>(_boxName);
    dev.log('[OfflineQueue] Hive box opened — ${_box!.length} pending items');

    // Listen for connectivity changes to auto-sync
    _connectivitySub?.cancel();
    _connectivitySub = Connectivity().onConnectivityChanged.listen((results) {
      final isOnline = results.contains(ConnectivityResult.mobile) ||
          results.contains(ConnectivityResult.wifi);
      if (isOnline && pendingCount > 0) {
        dev.log('[OfflineQueue] Connectivity restored — processing queue');
        processQueue(null); // Uses default API; caller must set static callback
      }
    });
  }

  // ── Enqueue ─────────────────────────────────────────────────────────────────
  static Future<void> enqueue(ComplaintDraft draft) async {
    final box = await _getBox();
    final key = '${draft.createdAt.millisecondsSinceEpoch}_${draft.latitude.toStringAsFixed(5)}';
    await box.put(key, jsonEncode(draft.toJson()));
    dev.log('[OfflineQueue] Enqueued draft: $key  (total: ${box.length})');
  }

  // ── Process queue ───────────────────────────────────────────────────────────
  /// Iterates pending drafts, attempts POST to server.
  /// - On 2xx: removes from queue.
  /// - On network error / non-2xx: increments retry, keeps in queue.
  ///
  /// [submitFn] is the async function that performs the real HTTP POST.
  /// Its signature matches ApiService.submitComplaint.
  /// Pass null to skip actual submission (e.g. during connectivity auto-trigger
  /// before the ApiService is available).
  static Future<int> processQueue(
    Future<Map<String, dynamic>> Function({
      required double latitude,
      required double longitude,
      String? address,
      String? areaType,
      String? nearbySensitive,
      required File image,
    })?
        submitFn,
  ) async {
    if (submitFn == null) return 0;

    final box = await _getBox();
    if (box.isEmpty) return 0;

    int synced = 0;
    final keys = box.keys.toList();

    for (final key in keys) {
      final raw = box.get(key);
      if (raw == null) continue;

      try {
        final draft = ComplaintDraft.fromJson(
          jsonDecode(raw) as Map<String, dynamic>,
        );

        // Skip drafts that have exceeded max retries
        if (draft.retryCount >= 5) {
          dev.log('[OfflineQueue] Dropping draft $key after 5 retries');
          await box.delete(key);
          continue;
        }

        final imageFile = File(draft.imagePath);
        if (!imageFile.existsSync()) {
          dev.log('[OfflineQueue] Image missing for draft $key — removing');
          await box.delete(key);
          continue;
        }

        // Attempt POST
        await submitFn(
          latitude: draft.latitude,
          longitude: draft.longitude,
          address: draft.address,
          areaType: draft.areaType,
          nearbySensitive: draft.nearbySensitive,
          image: imageFile,
        );

        // Success (2xx) — remove from queue
        await box.delete(key);
        synced++;
        dev.log('[OfflineQueue] ✓ Synced draft $key');
      } on SocketException {
        // Network error — keep in queue, increment retry
        _incrementRetry(box, key, raw);
        dev.log('[OfflineQueue] Network error for $key — will retry');
        break; // Stop processing — we're offline
      } catch (e) {
        // Server error (5xx, 4xx) — increment retry, continue to next
        _incrementRetry(box, key, raw);
        dev.log('[OfflineQueue] Error syncing $key: $e');
      }
    }

    dev.log('[OfflineQueue] processQueue done: $synced synced, ${box.length} remaining');
    return synced;
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────

  static int get pendingCount => _box?.length ?? 0;

  static Future<List<ComplaintDraft>> getPending() async {
    final box = await _getBox();
    return box.values
        .map((raw) {
          try {
            return ComplaintDraft.fromJson(jsonDecode(raw) as Map<String, dynamic>);
          } catch (_) {
            return null;
          }
        })
        .whereType<ComplaintDraft>()
        .toList();
  }

  static Future<void> clear() async {
    final box = await _getBox();
    await box.clear();
  }

  static void dispose() {
    _connectivitySub?.cancel();
    _connectivitySub = null;
  }

  // ── Private ─────────────────────────────────────────────────────────────────

  static Future<Box<String>> _getBox() async {
    if (_box == null || !_box!.isOpen) {
      _box = await Hive.openBox<String>(_boxName);
    }
    return _box!;
  }

  static void _incrementRetry(Box<String> box, dynamic key, String raw) {
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      map['retryCount'] = ((map['retryCount'] as int?) ?? 0) + 1;
      box.put(key, jsonEncode(map));
    } catch (_) {}
  }
}

// ── Connectivity helper (typed convenience wrapper) ─────────────────────────

class ConnectivityService {
  static final Connectivity _connectivity = Connectivity();

  /// Returns true if currently connected to mobile or WiFi.
  static Future<bool> get isOnline async {
    final result = await _connectivity.checkConnectivity();
    return result.contains(ConnectivityResult.mobile) ||
        result.contains(ConnectivityResult.wifi);
  }

  /// Stream of connectivity changes.
  static Stream<bool> get onConnectivityChanged {
    return _connectivity.onConnectivityChanged.map((results) {
      return results.contains(ConnectivityResult.mobile) ||
          results.contains(ConnectivityResult.wifi);
    });
  }
}
