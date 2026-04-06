import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';

/// Splash screen that checks if user is already logged in.
/// If token exists → skip login and go directly to home.
/// If no token → go to login screen.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});
  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _checkAuth();
  }

  Future<void> _checkAuth() async {
    final api = context.read<ApiService>();
    final loggedIn = await api.isLoggedIn();

    if (!mounted) return;

    if (loggedIn) {
      Navigator.pushReplacementNamed(context, '/home');
    } else {
      Navigator.pushReplacementNamed(context, '/login');
    }
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.construction, size: 64, color: Color(0xFFF5A623)),
            SizedBox(height: 20),
            Text(
              'RoadWatch',
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
                color: Color(0xFFF5A623),
              ),
            ),
            SizedBox(height: 8),
            Text(
              'Citizen App',
              style: TextStyle(color: Colors.white54, fontSize: 14),
            ),
            SizedBox(height: 32),
            CircularProgressIndicator(
              color: Color(0xFFF5A623),
              strokeWidth: 2,
            ),
          ],
        ),
      ),
    );
  }
}
