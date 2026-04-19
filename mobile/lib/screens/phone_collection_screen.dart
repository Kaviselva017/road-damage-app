// lib/screens/phone_collection_screen.dart
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:country_code_picker/country_code_picker.dart';
import 'package:provider/provider.dart';
import '../services/auth_service.dart';
import '../services/api_client.dart';
import 'home_screen.dart';

enum PhoneStatus { idle, checking, available, taken, invalid }

class PhoneCollectionScreen extends StatefulWidget {
  const PhoneCollectionScreen({super.key});
  @override State<PhoneCollectionScreen> createState() => _PhoneCollectionScreenState();
}

class _PhoneCollectionScreenState extends State<PhoneCollectionScreen> {
  final _controller  = TextEditingController();
  final _formKey     = GlobalKey<FormState>();
  String _countryCode = '+91';
  PhoneStatus _status = PhoneStatus.idle;
  bool _submitting    = false;
  Timer? _debounce;

  String get _fullPhone => '$_countryCode${_controller.text.trim()}';

  void _onPhoneChanged(String _) {
    _debounce?.cancel();
    if (_controller.text.trim().length < 6) {
      setState(() => _status = PhoneStatus.idle);
      return;
    }
    setState(() => _status = PhoneStatus.checking);
    _debounce = Timer(const Duration(milliseconds: 600), _checkAvailability);
  }

  Future<void> _checkAvailability() async {
    try {
      final api = context.read<ApiClient>();
      final res = await api.get('/auth/check-phone?phone=${Uri.encodeComponent(_fullPhone)}');
      if (!mounted) return;
      setState(() => _status = (res['available'] == true)
          ? PhoneStatus.available
          : PhoneStatus.taken);
    } catch (_) {
      if (mounted) setState(() => _status = PhoneStatus.idle);
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_status != PhoneStatus.available) return;
    setState(() => _submitting = true);
    try {
      final auth = context.read<AuthService>();
      await auth.submitPhone(_fullPhone);
      if (!mounted) return;
      Navigator.pushReplacement(
          context, MaterialPageRoute(builder: (_) => const HomeScreen()));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$e'), backgroundColor: Colors.red.shade700));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Widget _statusIcon() {
    switch (_status) {
      case PhoneStatus.checking:
        return const SizedBox(width: 18, height: 18,
            child: CircularProgressIndicator(strokeWidth: 2));
      case PhoneStatus.available:
        return const Icon(Icons.check_circle, color: Color(0xFF0F6E56), size: 20);
      case PhoneStatus.taken:
        return const Icon(Icons.cancel, color: Color(0xFF993C1D), size: 20);
      case PhoneStatus.invalid:
        return const Icon(Icons.warning_amber, color: Color(0xFFBA7517), size: 20);
      default:
        return const SizedBox.shrink();
    }
  }

  String? _validator(String? v) {
    if (v == null || v.trim().isEmpty) return 'Phone number required';
    if (v.trim().length < 7) return 'Number too short';
    if (_status == PhoneStatus.taken) return 'This number is already registered';
    return null;
  }

  Future<bool> _onWillPop() async {
    final leave = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Phone number required'),
        content: const Text('You must add a phone number to use the app.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false),
              child: const Text('Stay')),
          TextButton(onPressed: () => Navigator.pop(context, true),
              child: const Text('Sign out')),
        ],
      ),
    );
    if (leave == true) await context.read<AuthService>().signOut();
    return false;
  }

  @override
  Widget build(BuildContext context) {
    return WillPopScope(
      onWillPop: _onWillPop,
      child: Scaffold(
        backgroundColor: Colors.white,
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 32),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.phone_android, size: 40, color: Color(0xFF534AB7)),
                  const SizedBox(height: 16),
                  const Text('Add your phone number',
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  const Text(
                      'Required to submit road damage reports. '
                      'Each number can only be linked to one account.',
                      style: TextStyle(fontSize: 14, color: Colors.grey, height: 1.5)),
                  const SizedBox(height: 32),
                  Row(children: [
                    CountryCodePicker(
                      onChanged: (c) =>
                          setState(() => _countryCode = c.dialCode ?? '+91'),
                      initialSelection: 'IN',
                      showCountryOnly: false,
                      showOnlyCountryWhenClosed: false,
                      alignLeft: false,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextFormField(
                        controller: _controller,
                        onChanged: _onPhoneChanged,
                        validator: _validator,
                        keyboardType: TextInputType.phone,
                        inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                        decoration: InputDecoration(
                          hintText: '9876543210',
                          suffixIcon: Padding(
                              padding: const EdgeInsets.all(12),
                              child: _statusIcon()),
                          border: const OutlineInputBorder(),
                        ),
                      ),
                    ),
                  ]),
                  if (_status == PhoneStatus.available)
                    const Padding(
                      padding: EdgeInsets.only(top: 6),
                      child: Text('Number available',
                          style: TextStyle(fontSize: 12, color: Color(0xFF0F6E56))),
                    ),
                  if (_status == PhoneStatus.taken)
                    const Padding(
                      padding: EdgeInsets.only(top: 6),
                      child: Text('Already registered to another account',
                          style: TextStyle(fontSize: 12, color: Color(0xFF993C1D))),
                    ),
                  const SizedBox(height: 32),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: (_status == PhoneStatus.available && !_submitting)
                          ? _submit : null,
                      style: FilledButton.styleFrom(
                          backgroundColor: const Color(0xFF534AB7),
                          padding: const EdgeInsets.symmetric(vertical: 16)),
                      child: _submitting
                          ? const SizedBox(width: 20, height: 20,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.white))
                          : const Text('Continue',
                              style: TextStyle(fontSize: 16, color: Colors.white)),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }
}
