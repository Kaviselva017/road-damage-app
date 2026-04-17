import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'screens/splash_screen.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';
import 'screens/report_screen.dart';
import 'screens/my_complaints_screen.dart';
import 'services/api_service.dart';
import 'services/push_notification_service.dart';
import 'services/local_notification_helper.dart';

@pragma('vm:entry-point')
Future<void> _firebaseBackgroundHandler(RemoteMessage message) async {
  // If you re-generate firebase_options.yaml via flutterfire, you'd uncomment the options line below.
  await Firebase.initializeApp(/* options: DefaultFirebaseOptions.currentPlatform */);
  print("Handling a background message: ${message.messageId}");
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize Firebase (Assuming DefaultFirebaseOptions is in firebase_options.dart)
  // await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
  await Firebase.initializeApp(); // Keeping without options to prevent compile errors currently since not generated
  
  // Register background handler
  FirebaseMessaging.onBackgroundMessage(_firebaseBackgroundHandler);

  runApp(
    MultiProvider(
      providers: [
        Provider<ApiService>(create: (_) => ApiService()),
      ],
      child: const RoadDamageApp(),
    ),
  );
}

class RoadDamageApp extends StatelessWidget {
  const RoadDamageApp({super.key});

  @override
  Widget build(BuildContext context) {
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
