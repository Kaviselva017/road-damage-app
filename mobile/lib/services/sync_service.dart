import 'dart:async';
import 'dart:developer' as dev;
import 'dart:io';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'offline_queue_service.dart';
import 'api_service.dart';
import 'local_notification_helper.dart';

class SyncService {
  static StreamSubscription<List<ConnectivityResult>>? _sub;
  static bool _isSyncing = false;

  static Future<void> init() async {
    await OfflineQueueService.init();
    
    // Initial sync attempt if already connected
    final connectivity = await Connectivity().checkConnectivity();
    if (connectivity.contains(ConnectivityResult.mobile) || 
        connectivity.contains(ConnectivityResult.wifi)) {
      _attemptSync();
    }

    _sub = Connectivity().onConnectivityChanged.listen((List<ConnectivityResult> results) {
      final isConnected = results.contains(ConnectivityResult.mobile) || 
                          results.contains(ConnectivityResult.wifi);
      if (isConnected) {
        dev.log('[SyncService] Connectivity restored, triggering sync');
        _attemptSync();
      }
    });
  }

  static Future<void> _attemptSync() async {
    if (_isSyncing) return;
    _isSyncing = true;

    try {
      final pending = await OfflineQueueService.getPending();
      if (pending.isEmpty) {
        _isSyncing = false;
        return;
      }

      dev.log('[SyncService] Attempting to sync ${pending.length} reports');
      final api = ApiService();
      int syncedCount = 0;

      for (final complaint in pending) {
        final id = complaint['id'] as int;
        final imagePath = complaint['image_path'] as String;
        final file = File(imagePath);

        if (!file.existsSync()) {
          dev.log('[SyncService] Image file $imagePath missing, skipping');
          await OfflineQueueService.markSynced(id);
          continue;
        }

        try {
          await api.submitComplaint(
            latitude: complaint['latitude'] as double,
            longitude: complaint['longitude'] as double,
            address: complaint['address'] as String?,
            nearbySensitive: complaint['nearby_places'] as String?,
            image: file,
          );
          
          await OfflineQueueService.markSynced(id);
          syncedCount++;
          dev.log('[SyncService] Synced complaint $id');
        } catch (e) {
          dev.log('[SyncService] Sync failure for complaint $id: $e');
          await OfflineQueueService.incrementRetry(id);
        }
      }

      if (syncedCount > 0) {
        await LocalNotificationHelper.showNotification(
          title: 'Offline Reports Synced',
          body: '$syncedCount road report(s) auto-submitted successfully!',
        );
      }
    } catch (e) {
      dev.log('[SyncService] Global sync error: $e');
    } finally {
      _isSyncing = false;
    }
  }

  static Future<int> pendingCount() async {
    return await OfflineQueueService.pendingCount();
  }

  static void dispose() {
    _sub?.cancel();
    _sub = null;
  }
}
