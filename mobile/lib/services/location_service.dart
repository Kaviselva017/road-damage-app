// lib/services/location_service.dart
// ====================================
// High-accuracy location service for RoadWatch.
//
// Takes 3 GPS readings over ~3 seconds and returns the reading with
// the highest accuracy. Falls back to last known location on timeout.
//
// Dependencies:
//   geolocator: ^11.0.0 (already in pubspec.yaml)

import 'dart:async';
import 'dart:developer' as dev;

import 'package:geolocator/geolocator.dart';

// ── Typed result ──────────────────────────────────────────────────────────────

class LocationResult {
  final double lat;
  final double lng;
  final double accuracy; // metres
  final DateTime timestamp;

  const LocationResult({
    required this.lat,
    required this.lng,
    required this.accuracy,
    required this.timestamp,
  });

  /// Accuracy quality tier.
  ///   green  ← < 10 m
  ///   amber  ← 10–30 m
  ///   red    ← > 30 m
  String get qualityTier {
    if (accuracy < 10) return 'green';
    if (accuracy <= 30) return 'amber';
    return 'red';
  }

  @override
  String toString() =>
      'LocationResult(lat: $lat, lng: $lng, accuracy: ${accuracy.toStringAsFixed(1)}m, tier: $qualityTier)';
}

// ── Location Service ──────────────────────────────────────────────────────────

class LocationService {
  /// Ensure location permissions are granted.
  /// Returns null if everything is OK, or a human-readable error message.
  static Future<String?> ensurePermissions() async {
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      return 'Location services are disabled. Please enable GPS.';
    }

    LocationPermission perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) {
      perm = await Geolocator.requestPermission();
    }

    if (perm == LocationPermission.denied) {
      return 'Location permission denied.';
    }
    if (perm == LocationPermission.deniedForever) {
      return 'Location permission permanently denied. Open app settings to allow.';
    }
    return null; // OK
  }

  /// Takes up to 3 GPS readings over ~3 seconds and returns the one with
  /// the highest accuracy (lowest accuracy number in metres).
  ///
  /// Falls back to [Geolocator.getLastKnownPosition] if all readings time out.
  /// Returns null only if no position can be determined at all.
  static Future<LocationResult?> getBestLocation({
    int readings = 3,
    Duration readingInterval = const Duration(seconds: 1),
    Duration perReadingTimeout = const Duration(seconds: 5),
  }) async {
    final List<Position> positions = [];

    for (int i = 0; i < readings; i++) {
      try {
        final pos = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.best,
          timeLimit: perReadingTimeout,
        );
        positions.add(pos);
        dev.log(
          '[LocationService] Reading ${i + 1}/$readings: '
          '(${pos.latitude.toStringAsFixed(6)}, ${pos.longitude.toStringAsFixed(6)}) '
          'accuracy=${pos.accuracy.toStringAsFixed(1)}m',
        );
      } catch (e) {
        dev.log('[LocationService] Reading ${i + 1} failed: $e');
      }

      // Wait between readings (skip wait after last reading)
      if (i < readings - 1) {
        await Future.delayed(readingInterval);
      }
    }

    // Pick best (lowest accuracy number = most accurate)
    if (positions.isNotEmpty) {
      positions.sort((a, b) => a.accuracy.compareTo(b.accuracy));
      final best = positions.first;
      dev.log('[LocationService] Best of ${positions.length}: accuracy=${best.accuracy.toStringAsFixed(1)}m');
      return LocationResult(
        lat: best.latitude,
        lng: best.longitude,
        accuracy: best.accuracy,
        timestamp: best.timestamp ?? DateTime.now(),
      );
    }

    // Fallback: last known
    dev.log('[LocationService] All readings failed — trying lastKnownPosition');
    try {
      final last = await Geolocator.getLastKnownPosition();
      if (last != null) {
        return LocationResult(
          lat: last.latitude,
          lng: last.longitude,
          accuracy: last.accuracy,
          timestamp: last.timestamp ?? DateTime.now(),
        );
      }
    } catch (e) {
      dev.log('[LocationService] lastKnownPosition also failed: $e');
    }

    return null;
  }

  /// Quick single reading (for non-critical use cases).
  static Future<LocationResult?> getQuickLocation() async {
    try {
      final pos = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 10),
      );
      return LocationResult(
        lat: pos.latitude,
        lng: pos.longitude,
        accuracy: pos.accuracy,
        timestamp: pos.timestamp ?? DateTime.now(),
      );
    } catch (_) {
      // Fallback
      final last = await Geolocator.getLastKnownPosition();
      if (last != null) {
        return LocationResult(
          lat: last.latitude,
          lng: last.longitude,
          accuracy: last.accuracy,
          timestamp: last.timestamp ?? DateTime.now(),
        );
      }
      return null;
    }
  }
}
