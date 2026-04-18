import 'dart:async';
import 'dart:developer' as dev;
import 'dart:io';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'offline_queue.dart';
import 'api_service.dart';
import 'local_notification_helper.dart';

class SyncService {
  static bool _isSyncing = false;

  static Future<void> init() async {
    await OfflineQueue.init();
    
    // Initial sync attempt if already connected
    final connectivity = await Connectivity().checkConnectivity();
    if (connectivity.contains(ConnectivityResult.mobile) || 
        connectivity.contains(ConnectivityResult.wifi)) {
    _attemptSync();
  }

  static Future<void> _attemptSync() async {
    if (_isSyncing) return;
    _isSyncing = true;

    try {
      final pendingCount = OfflineQueue.pendingCount;
      if (pendingCount == 0) {
        _isSyncing = false;
        return;
      }

      dev.log('[SyncService] Attempting to sync $pendingCount reports');
      final api = ApiService();
      
      final syncedCount = await OfflineQueue.processQueue(api.submitComplaint);

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

  static int pendingCount() {
    return OfflineQueue.pendingCount;
  }

  static void dispose() {
    OfflineQueue.dispose();
  }
}

