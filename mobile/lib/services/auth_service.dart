// lib/services/auth_service.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

const _baseUrl = String.fromEnvironment('API_URL', defaultValue: 'http://10.0.2.2:8000');

class AuthResult {
  final String? accessToken;
  final String? refreshToken;
  final bool requiresPhone;
  final String? tempToken;
  final Map<String, dynamic>? user;

  const AuthResult({
    this.accessToken,
    this.refreshToken,
    this.requiresPhone = false,
    this.tempToken,
    this.user,
  });
}

class AuthService extends ChangeNotifier {
  final _googleSignIn = GoogleSignIn(scopes: ['email', 'profile']);
  final _storage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  String? _accessToken;
  Map<String, dynamic>? currentUser;

  Future<AuthResult> signInWithGoogle() async {
    final account = await _googleSignIn.signIn();
    if (account == null) throw Exception('Google sign-in cancelled');

    final auth = await account.authentication;
    final idToken = auth.idToken;
    if (idToken == null) throw Exception('No ID token from Google');

    final res = await http.post(
      Uri.parse('$_baseUrl/auth/google'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'id_token': idToken}),
    );

    if (res.statusCode != 200) {
      throw Exception('Auth failed: ${res.body}');
    }

    final body = jsonDecode(res.body) as Map<String, dynamic>;

    if (body['requires_phone'] == true) {
      await _storage.write(key: 'temp_token', value: body['temp_token']);
      return AuthResult(requiresPhone: true, tempToken: body['temp_token']);
    }

    await _saveTokens(body['access_token'], body['refresh_token']);
    currentUser = body['user'] as Map<String, dynamic>?;
    notifyListeners();

    return AuthResult(
      accessToken: body['access_token'],
      refreshToken: body['refresh_token'],
      user: currentUser,
    );
  }
  
  Future<void> submitPhone(String phoneNumber) async {
    final tempToken = await _storage.read(key: 'temp_token');
    if (tempToken == null) throw Exception('Session expired. Please sign in again.');
  
    final res = await http.post(
      Uri.parse('$_baseUrl/auth/phone'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $tempToken',
      },
      body: jsonEncode({'phone_number': phoneNumber}),
    );
  
    if (res.statusCode == 409) {
      throw Exception('This number is already registered to another account.');
    }
    if (res.statusCode == 422) {
      throw Exception('Invalid phone number format. Use +CountryCodeNumber.');
    }
    if (res.statusCode != 200) {
      throw Exception('Failed to save phone number.');
    }
  
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    await _storage.delete(key: 'temp_token');
    await _saveTokens(body['access_token'], body['refresh_token']);
    currentUser = body['user'] as Map<String, dynamic>?;
    notifyListeners();
  }

  Future<void> _saveTokens(String access, String refresh) async {
    _accessToken = access;
    await _storage.write(key: 'access_token', value: access);
    await _storage.write(key: 'refresh_token', value: refresh);
  }

  Future<String?> getAccessToken() async {
    return _accessToken ?? await _storage.read(key: 'access_token');
  }

  Future<bool> refreshToken() async {
    final stored = await _storage.read(key: 'refresh_token');
    if (stored == null) return false;

    final res = await http.post(
      Uri.parse('$_baseUrl/auth/refresh'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh_token': stored}),
    );

    if (res.statusCode != 200) return false;

    final body = jsonDecode(res.body) as Map<String, dynamic>;
    await _saveTokens(body['access_token'], body['refresh_token']);
    return true;
  }

  Future<void> signOut() async {
    final stored = await _storage.read(key: 'refresh_token');
    if (stored != null) {
      await http.post(
        Uri.parse('$_baseUrl/auth/logout'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh_token': stored}),
      ).catchError((_) {});
    }
    await _googleSignIn.signOut();
    await _storage.deleteAll();
    _accessToken = null;
    currentUser = null;
    notifyListeners();
  }
}
