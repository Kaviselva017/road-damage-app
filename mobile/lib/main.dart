import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'screens/splash_screen.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';
import 'screens/report_screen.dart';
import 'screens/my_complaints_screen.dart';
import 'services/api_service.dart';

void main() {
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
      title: 'Road Damage Reporter',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFFF5A623),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
        fontFamily: 'Roboto',
      ),
      // Start at splash screen which checks auth state
      // No more forced login every time — if token exists, go straight to home
      initialRoute: '/',
      routes: {
        '/': (_) => const SplashScreen(),
        '/login': (_) => const LoginScreen(),
        '/home': (_) => const HomeScreen(),
        '/report': (_) => const ReportScreen(),
        '/my-complaints': (_) => const MyComplaintsScreen(),
      },
    );
  }
}
