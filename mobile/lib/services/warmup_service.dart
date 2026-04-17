import 'dart:async';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

class WarmupService {
  static const String _healthUrl = 'https://road-damage-appsystem.onrender.com/healthz';

  /// Call this when the app launches (e.g. before login screen)
  static Future<void> wakeupBackend(BuildContext context) async {
    if (!context.mounted) return;

    bool hasResponded = false;
    final scaffoldMessenger = ScaffoldMessenger.maybeOf(context);

    // Show a loading snackbar if response takes > 3 seconds
    final timeoutTimer = Timer(const Duration(seconds: 3), () {
      if (!hasResponded && context.mounted && scaffoldMessenger != null) {
        scaffoldMessenger.showSnackBar(
          const SnackBar(
            content: Text('Connecting to server...'),
            duration: Duration(days: 1), // Keep open indefinitely
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    });

    try {
      // Send a silent background GET request
      await http.get(Uri.parse(_healthUrl)).timeout(const Duration(seconds: 60));
    } catch (e) {
      // Do not crash the app on timeout/error, let the user proceed normally
      // where regular endpoints will throw actual UI errors.
    } finally {
      hasResponded = true;
      timeoutTimer.cancel();
      if (context.mounted && scaffoldMessenger != null) {
        // Automatically dismiss the connecting snackbar when done
        scaffoldMessenger.hideCurrentSnackBar();
      }
    }
  }
}
