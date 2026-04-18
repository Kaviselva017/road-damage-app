import 'dart:async';
import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart' as fb;
import '../services/auth_service.dart';
import '../services/push_notification_service.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _phoneCtrl = TextEditingController();
  final _otpCtrl = TextEditingController();
  String? _verificationId;
  bool _loading = false;
  String? _error;
  int _resendTimer = 60;
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _startTimer() {
    _resendTimer = 60;
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_resendTimer == 0) {
        setState(() => _timer?.cancel());
      } else {
        setState(() => _resendTimer--);
      }
    });
  }

  Future<void> _sendOtp() async {
    if (_phoneCtrl.text.isEmpty) {
      setState(() => _error = "Enter phone number");
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      await AuthService.signInWithPhone(
        phoneNumber: _phoneCtrl.text,
        onCodeSent: (String vid) {
          setState(() {
            _verificationId = vid;
            _loading = false;
          });
          _startTimer();
        },
        onError: (fb.FirebaseAuthException e) {
          setState(() {
            _error = e.message;
            _loading = false;
          });
        },
      );
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _verifyOtp() async {
    if (_otpCtrl.text.isEmpty || _verificationId == null) return;
    setState(() { _loading = true; _error = null; });
    try {
      await AuthService.verifyOtp(
        verificationId: _verificationId!,
        smsCode: _otpCtrl.text,
      );
      final profile = await AuthService.syncWithBackend();
      if (!mounted) return;
      if (profile != null) {
        final token = await AuthService.getIdToken();
        if (token != null) await PushNotificationService.init(token);
        if (!mounted) return;
        Navigator.pushReplacementNamed(context, '/home');
      } else {
        setState(() { _error = "Backend sync failed. Try again."; _loading = false; });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = "Invalid OTP code"; _loading = false; });
    }
  }

  Future<void> _googleSignIn() async {
    setState(() { _loading = true; _error = null; });
    try {
      final cred = await AuthService.signInWithGoogle();
      if (!mounted) return;
      if (cred != null) {
        final profile = await AuthService.syncWithBackend();
        if (!mounted) return;
        if (profile != null) {
          final token = await AuthService.getIdToken();
          if (token != null) await PushNotificationService.init(token);
          if (!mounted) return;
          Navigator.pushReplacementNamed(context, '/home');
        } else {
           setState(() { _error = "Backend sync failed"; _loading = false; });
        }
      } else {
          setState(() => _loading = false);
      }
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = "Google Sign-In failed"; _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 40),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 40),
              const Icon(Icons.construction, size: 80, color: Color(0xFFF5A623)),
              const SizedBox(height: 16),
              const Text('RoadWatch',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
              const Text('Secure Citizen Reporting',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.white54, fontSize: 16)),
              const SizedBox(height: 60),
              
              if (_verificationId == null) ...[
                TextField(
                  controller: _phoneCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Phone Number (with +91)',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.phone_android),
                    hintText: '+919876543210'
                  ),
                  keyboardType: TextInputType.phone,
                ),
                const SizedBox(height: 20),
                ElevatedButton(
                  onPressed: _loading ? null : _sendOtp,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFF5A623),
                    foregroundColor: Colors.black,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  child: _loading 
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('SEND OTP', style: TextStyle(fontWeight: FontWeight.bold)),
                ),
              ] else ...[
                 TextField(
                  controller: _otpCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Enter 6-digit OTP',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.lock_clock),
                  ),
                  keyboardType: TextInputType.number,
                  maxLength: 6,
                ),
                const SizedBox(height: 12),
                if (_resendTimer > 0)
                  Text("Resend OTP in $_resendTimer seconds", textAlign: TextAlign.center, style: const TextStyle(color: Colors.grey))
                else
                  TextButton(onPressed: _sendOtp, child: const Text("Resend OTP")),
                const SizedBox(height: 20),
                ElevatedButton(
                  onPressed: _loading ? null : _verifyOtp,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF4CAF50),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  child: const Text('VERIFY & LOGIN', style: TextStyle(fontWeight: FontWeight.bold)),
                ),
              ],

              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 20),
                  child: Text(_error!, style: const TextStyle(color: Colors.redAccent), textAlign: TextAlign.center),
                ),
              
              const SizedBox(height: 40),
              Row(
                children: [
                  Expanded(child: Divider(color: Colors.grey.shade800)),
                  const Padding(padding: EdgeInsets.symmetric(horizontal: 10), child: Text("OR", style: TextStyle(color: Colors.grey))),
                  Expanded(child: Divider(color: Colors.grey.shade800)),
                ],
              ),
              const SizedBox(height: 20),
              OutlinedButton.icon(
                onPressed: _loading ? null : _googleSignIn,
                icon: Image.network('https://upload.wikimedia.org/wikipedia/commons/5/53/Google_%22G%22_Logo.svg', height: 18, 
                   errorBuilder: (c, e, s) => const Icon(Icons.login)),
                label: const Text("Continue with Google"),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  side: BorderSide(color: Colors.grey.shade700)
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

