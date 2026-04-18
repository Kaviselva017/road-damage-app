import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'dart:developer' as dev;

class LocalNotificationHelper {
  static final FlutterLocalNotificationsPlugin _notificationsPlugin =
      FlutterLocalNotificationsPlugin();

  static Future<void> init() async {
    const AndroidInitializationSettings initializationSettingsAndroid =
        AndroidInitializationSettings('@mipmap/ic_launcher');

    const InitializationSettings initializationSettings =
        InitializationSettings(android: initializationSettingsAndroid);

    await _notificationsPlugin.initialize(
      initializationSettings,
      onDidReceiveNotificationResponse: (NotificationResponse response) {
        // Handle notification tap in foreground if needed
        dev.log('Notification tapped: ${response.payload}');
      },
    );

    // Create Android channel
    const AndroidNotificationChannel channel = AndroidNotificationChannel(
      'roadwatch_alerts',
      'RoadWatch Alerts',
      description: 'Notifications for road damage status updates',
      importance: Importance.high,
    );

    await _notificationsPlugin
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(channel);
  }

  static Future<void> showNotification({
    required String title,
    required String body,
    String? payload,
  }) async {
    const AndroidNotificationDetails androidDetails =
        AndroidNotificationDetails(
      'roadwatch_alerts',
      'RoadWatch Alerts',
      channelDescription: 'Notifications for road damage status updates',
      importance: Importance.high,
      priority: Priority.high,
      ticker: 'ticker',
    );

    const NotificationDetails notificationDetails =
        NotificationDetails(android: androidDetails);

    await _notificationsPlugin.show(
      0, // ID
      title,
      body,
      notificationDetails,
      payload: payload,
    );
  }
}
