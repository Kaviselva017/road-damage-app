import 'dart:developer' as dev;
import 'package:path/path.dart';
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';

class OfflineQueueService {
  static Database? _db;

  static Future<void> init() async {
    if (_db != null) return;
    try {
      final dir = await getApplicationDocumentsDirectory();
      final path = join(dir.path, 'roadwatch_queue.db');
      _db = await openDatabase(
        path,
        version: 1,
        onCreate: (db, version) async {
          await db.execute('''
            CREATE TABLE pending_complaints (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              image_path TEXT NOT NULL,
              latitude REAL NOT NULL,
              longitude REAL NOT NULL,
              address TEXT,
              nearby_places TEXT,
              created_at TEXT NOT NULL,
              retry_count INTEGER DEFAULT 0
            )
          ''');
        },
      );
      dev.log('[OfflineQueue] Database initialized');
    } catch (e) {
      dev.log('[OfflineQueue] Init error: $e');
    }
  }

  static Future<void> enqueue({
    required String imagePath,
    required double latitude,
    required double longitude,
    String? address,
    String? nearbyPlaces,
  }) async {
    await init();
    try {
      await _db?.insert('pending_complaints', {
        'image_path': imagePath,
        'latitude': latitude,
        'longitude': longitude,
        'address': address,
        'nearby_places': nearbyPlaces,
        'created_at': DateTime.now().toIso8601String(),
        'retry_count': 0,
      });
      dev.log('[OfflineQueue] Queued complaint for offline sync');
    } catch (e) {
      dev.log('[OfflineQueue] Enqueue error: $e');
    }
  }

  static Future<List<Map<String, dynamic>>> getPending() async {
    await init();
    try {
      return await _db?.query(
            'pending_complaints',
            where: 'retry_count < ?',
            whereArgs: [3],
            orderBy: 'created_at ASC',
          ) ??
          [];
    } catch (e) {
      dev.log('[OfflineQueue] getPending error: $e');
      return [];
    }
  }

  static Future<void> markSynced(int id) async {
    await init();
    try {
      await _db?.delete(
        'pending_complaints',
        where: 'id = ?',
        whereArgs: [id],
      );
      dev.log('[OfflineQueue] Marked complaint $id as synced');
    } catch (e) {
      dev.log('[OfflineQueue] markSynced error: $e');
    }
  }

  static Future<void> incrementRetry(int id) async {
    await init();
    try {
      await _db?.rawUpdate(
        'UPDATE pending_complaints SET retry_count = retry_count + 1 WHERE id = ?',
        [id],
      );
      dev.log('[OfflineQueue] Incremented retry for complaint $id');
    } catch (e) {
      dev.log('[OfflineQueue] incrementRetry error: $e');
    }
  }

  static Future<int> pendingCount() async {
    await init();
    try {
      final res = await _db?.rawQuery('SELECT COUNT(*) FROM pending_complaints WHERE retry_count < 3');
      return Sqflite.firstIntValue(res ?? []) ?? 0;
    } catch (e) {
      dev.log('[OfflineQueue] pendingCount error: $e');
      return 0;
    }
  }
}
