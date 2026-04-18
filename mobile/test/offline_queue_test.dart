// test/offline_queue_test.dart
// ================================
// Unit tests for OfflineQueue (Hive-backed).
//
// Uses a temp directory for Hive, a mock submit function,
// and verifies enqueue/sync/retry behaviour.
//
// Run: flutter test test/offline_queue_test.dart

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';

// We import directly — these are pure Dart, no Flutter widgets.
import 'package:road_damage_app/services/offline_queue.dart';

void main() {
  late Directory tempDir;

  setUp(() async {
    // Use a unique temp directory for each test so Hive state is isolated.
    tempDir = await Directory.systemTemp.createTemp('hive_test_');
    Hive.init(tempDir.path);
  });

  tearDown(() async {
    await Hive.close();
    if (tempDir.existsSync()) {
      tempDir.deleteSync(recursive: true);
    }
  });

  // ── Helper: create a draft whose image file exists on disk ────────────────
  Future<ComplaintDraft> _makeDraft({double lat = 12.97, double lng = 77.59}) async {
    final imgFile = File('${tempDir.path}/test_${lat.hashCode}.jpg');
    await imgFile.writeAsBytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10]); // fake JPEG
    return ComplaintDraft(
      imagePath: imgFile.path,
      latitude: lat,
      longitude: lng,
      address: '123 Test St',
      nearbySensitive: 'Test School',
      areaType: 'school',
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Test 1: Enqueue 2 items, mock 200 response, assert queue empty
  // ─────────────────────────────────────────────────────────────────────────
  test('test_enqueue_and_sync', () async {
    // Enqueue 2 drafts
    final draft1 = await _makeDraft(lat: 12.97, lng: 77.59);
    final draft2 = await _makeDraft(lat: 13.08, lng: 80.27);

    final box = await Hive.openBox<String>('offline_complaints');

    // Manually enqueue (same logic as OfflineQueue.enqueue but using local box)
    final key1 = '${draft1.createdAt.millisecondsSinceEpoch}_${draft1.latitude.toStringAsFixed(5)}';
    await box.put(key1, jsonEncode(draft1.toJson()));

    final key2 = '${draft2.createdAt.millisecondsSinceEpoch}_${draft2.latitude.toStringAsFixed(5)}';
    await box.put(key2, jsonEncode(draft2.toJson()));

    expect(box.length, 2);

    // Mock submit function that always succeeds (simulates 200 response)
    int callCount = 0;
    Future<Map<String, dynamic>> mockSubmit({
      required double latitude,
      required double longitude,
      String? address,
      String? areaType,
      String? nearbySensitive,
      required File image,
    }) async {
      callCount++;
      // Simulate successful 200 response
      return {'complaint_id': 'RD-TEST-$callCount', 'status': 'pending'};
    }

    // Process the queue
    final synced = await OfflineQueue.processQueue(mockSubmit);

    expect(synced, 2, reason: 'Both items should be synced');
    expect(callCount, 2, reason: 'Submit should be called twice');
    expect(box.length, 0, reason: 'Queue should be empty after successful sync');
  });

  // ─────────────────────────────────────────────────────────────────────────
  // Test 2: Mock 500 error, assert item still in queue
  // ─────────────────────────────────────────────────────────────────────────
  test('test_retry_on_fail', () async {
    final draft = await _makeDraft(lat: 28.61, lng: 77.20);

    final box = await Hive.openBox<String>('offline_complaints');
    final key = '${draft.createdAt.millisecondsSinceEpoch}_${draft.latitude.toStringAsFixed(5)}';
    await box.put(key, jsonEncode(draft.toJson()));

    expect(box.length, 1);

    // Mock submit function that always fails (simulates 500 response)
    Future<Map<String, dynamic>> mockFailSubmit({
      required double latitude,
      required double longitude,
      String? address,
      String? areaType,
      String? nearbySensitive,
      required File image,
    }) async {
      throw HttpException('500 Internal Server Error');
    }

    // Process the queue — should fail but keep the item
    final synced = await OfflineQueue.processQueue(mockFailSubmit);

    expect(synced, 0, reason: 'No items should be synced on 500 error');
    expect(box.length, 1, reason: 'Item should remain in queue after failure');

    // Verify retry count was incremented
    final raw = box.get(key);
    expect(raw, isNotNull);
    final updated = jsonDecode(raw!) as Map<String, dynamic>;
    expect(updated['retryCount'], 1, reason: 'Retry count should be incremented');
  });
}
