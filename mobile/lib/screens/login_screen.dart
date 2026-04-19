// lib/screens/login_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/auth_service.dart';
import 'phone_collection_screen.dart';
import 'home_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  bool _loading = false;

  Future<void> _handleGoogleSignIn() async {
    setState(() => _loading = true);
    try {
      final auth = context.read<AuthService>();
      final result = await auth.signInWithGoogle();

      if (!mounted) return;
      if (result.requiresPhone) {
        Navigator.pushReplacement(context,
          MaterialPageRoute(builder: (_) => const PhoneCollectionScreen()));
      } else {
        Navigator.pushReplacement(context,
          MaterialPageRoute(builder: (_) => const HomeScreen()));
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Sign-in failed: $e'),
                 backgroundColor: Colors.red.shade700));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.add_road, size: 72, color: Color(0xFF1a73e8)),
              const SizedBox(height: 16),
              const Text('Road Damage Reporter',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              const Text('Help fix your city',
                style: TextStyle(fontSize: 14, color: Colors.grey)),
              const SizedBox(height: 48),
              _loading
                ? const CircularProgressIndicator()
                : OutlinedButton.icon(
                    onPressed: _handleGoogleSignIn,
                    icon: Image.asset('assets/google_logo.png', width: 18, height: 18),
                    label: const Text('Continue with Google',
                      style: TextStyle(fontSize: 15, color: Colors.black87)),
                    style: OutlinedButton.styleFrom(
                      backgroundColor: Colors.white,
                      side: const BorderSide(color: Color(0xFFDDDDDD)),
                      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
            ],
          ),
        ),
      ),
    );
  }
}
