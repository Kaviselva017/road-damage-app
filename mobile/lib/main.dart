import 'package:firebase_core/firebase_core.dart';
import 'dart:developer' as dev;
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:flutter_jailbreak_detection/flutter_jailbreak_detection.dart';
import 'screens/splash_screen.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';
import 'screens/report_screen.dart';
import 'screens/my_complaints_screen.dart';
import 'services/api_service.dart';
import 'services/push_notification_service.dart';
import 'services/local_notification_helper.dart';
import 'services/sync_service.dart';

@pragma('vm:entry-point')
Future<void> _firebaseBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  dev.log("Handling a background message: ${message.messageId}");
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  await Firebase.initializeApp();
  await SyncService.init();
  FirebaseMessaging.onBackgroundMessage(_firebaseBackgroundHandler);
  
  // Root/Jailbreak Detection
  bool isJailbroken = false;
  try {
    isJailbroken = await FlutterJailbreakDetection.jailbroken;
  } catch (_) {}

  // Initialize Supabase
  await Supabase.initialize(
    url: const String.fromEnvironment('SUPABASE_URL'),
    anonKey: const String.fromEnvironment('SUPABASE_ANON_KEY'),
  );

  runApp(
    MultiProvider(
      providers: [
        Provider<ApiService>(create: (_) => ApiService()),
      ],
      child: RoadDamageApp(isJailbroken: isJailbroken),
    ),
  );
}

class RoadDamageApp extends StatelessWidget {
  final bool isJailbroken;
  const RoadDamageApp({super.key, required this.isJailbroken});

  @override
  Widget build(BuildContext context) {
    if (isJailbroken) {
      // In a real app, we might show a persistent warning banner.
      dev.log("SECURITY WARNING: Device is rooted/jailbroken.");
    }

    return MaterialApp(
      title: 'RoadWatch',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFFF5A623),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
        fontFamily: 'Inter',
      ),
      initialRoute: '/',
      routes: {
        '/': (context) => const SplashScreen(),
        '/login': (context) => const LoginScreen(),
        '/home': (context) => const HomeScreen(),
        '/report': (context) => const ReportScreen(),
        '/my-complaints': (context) => const MyComplaintsScreen(),
      },
    );
  }
}
