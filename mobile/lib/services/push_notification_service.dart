import 'package:flutter/material.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';

class PushNotificationService {
  static final FirebaseMessaging _messaging = FirebaseMessaging.instance;
  static FlutterLocalNotificationsPlugin? _localNotif;

  static Future<void> init(BuildContext context) async {
    // 1. Request Permission (alert, badge, sound)
    NotificationSettings settings = await _messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );

    if (settings.authorizationStatus != AuthorizationStatus.authorized) {
      print('User declined or has not accepted FCM permission');
      return;
    }

    // 2. Initialize FlutterLocalNotificationsPlugin
    _localNotif = FlutterLocalNotificationsPlugin();
    const AndroidInitializationSettings androidInitSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const DarwinInitializationSettings iosInitSettings =
        DarwinInitializationSettings();
    const InitializationSettings initSettings = InitializationSettings(
      android: androidInitSettings,
      iOS: iosInitSettings,
    );
    await _localNotif!.initialize(initSettings);

    // 3. Create Android notification channel (High Importance)
    const AndroidNotificationChannel channel = AndroidNotificationChannel(
      'roadwatch_channel', // id
      'RoadWatch Alerts',  // name
      importance: Importance.high,
    );

    await _localNotif!
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(channel);

    // 4. Get FCM Token, save it, and send to backend
    String? token = await _messaging.getToken();
    if (token != null) {
      await _syncToken(token);
    }

    _messaging.onTokenRefresh.listen((newToken) {
      _syncToken(newToken);
    });

    // 5. Handle Foreground Messages
    FirebaseMessaging.onMessage.listen((RemoteMessage message) {
      print('Received message in foreground: ${message.messageId}');
      showLocalNotification(message);
    });

    // 6. Handle Background / Terminated Taps
    FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
      _handleNavigation(context, message);
    });

    RemoteMessage? initialMessage = await _messaging.getInitialMessage();
    if (initialMessage != null) {
      _handleNavigation(context, initialMessage);
    }
  }

  static Future<void> _syncToken(String token) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('fcm_token', token);
      final api = ApiService(); 
      await api.updateFcmToken(token);
      print('FCM token synchronized with backend.');
    } catch (e) {
      print('Error synchronizing FCM token: $e');
    }
  }

  static Future<void> refreshTokenIfNeeded() async {
    final prefs = await SharedPreferences.getInstance();
    final String? storedToken = prefs.getString('fcm_token');
    final String? currentToken = await _messaging.getToken();

    if (currentToken != null && currentToken != storedToken) {
      await _syncToken(currentToken);
    }
  }

  static Future<void> showLocalNotification(RemoteMessage message) async {
    if (_localNotif == null) return;
    
    // Only show if the message has notification payload
    if (message.notification != null) {
      const AndroidNotificationDetails androidDetails =
          AndroidNotificationDetails(
        'roadwatch_channel',
        'RoadWatch Alerts',
        importance: Importance.high,
        priority: Priority.high,
      );
      const NotificationDetails platformDetails =
          NotificationDetails(android: androidDetails);

      await _localNotif!.show(
        message.hashCode,
        message.notification?.title ?? 'RoadWatch',
        message.notification?.body ?? '',
        platformDetails,
      );
    }
  }

  static void _handleNavigation(BuildContext context, RemoteMessage message) {
    if (message.data.containsKey('complaint_id')) {
      final complaintId = message.data['complaint_id'];
      // Assuming context is accessible here (may need a global nav key in a real app)
      Navigator.of(context).pushNamed('/my-complaints');
      // Or if you have a specific route: Navigator.of(context).pushNamed('/complaint-detail', arguments: complaintId);
    }
  }
}
