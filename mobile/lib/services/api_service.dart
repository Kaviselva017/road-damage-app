import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiService {
  static const String _configuredBaseUrl =
      String.fromEnvironment('ROADWATCH_API_URL', defaultValue: '');
  static String get baseUrl {
    if (_configuredBaseUrl.isNotEmpty) return _configuredBaseUrl;
    if (Platform.isAndroid) return 'http://10.0.2.2:8000/api';
    return 'http://127.0.0.1:8000/api';
  }

  final Dio _dio = Dio(BaseOptions(baseUrl: baseUrl));
  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  ApiService() {
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _storage.read(key: 'token');
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        return handler.next(options);
      },
    ));
  }

  // --- Auth ---
  Future<Map<String, dynamic>> register(
      String name, String email, String phone, String password) async {
    final res = await _dio.post('/auth/register', data: {
      'name': name, 'email': email, 'phone': phone, 'password': password,
    });
    return res.data;
  }

  Future<String> login(String email, String password) async {
    final res = await _dio.post('/auth/login',
        data: {'email': email, 'password': password});
    final token = res.data['access_token'];
    await _storage.write(key: 'token', value: token);
    return token;
  }

  Future<void> logout() async {
    await _storage.delete(key: 'token');
  }

  /// Check if a valid token exists (user already logged in)
  Future<bool> isLoggedIn() async {
    final token = await _storage.read(key: 'token');
    return token != null && token.isNotEmpty;
  }

  Future<String?> getToken() async {
    return await _storage.read(key: 'token');
  }

  Future<void> updateFcmToken(String token) async {
    await _dio.patch('/auth/fcm-token', data: {'fcm_token': token});
  }

  Future<Map<String, dynamic>> submitComplaint({
    required double latitude,
    required double longitude,
    String? address,
    String? areaType,
    double? impactScore,
    int? sensitiveLocationCount,
    String? nearbySensitive,
    required File image,
  }) async {
    final formData = FormData.fromMap({
      'latitude': latitude,
      'longitude': longitude,
      if (address != null) 'address': address,
      if (areaType != null) 'area_type': areaType,
      if (impactScore != null) 'impact_score': impactScore,
      if (sensitiveLocationCount != null)
        'sensitive_location_count': sensitiveLocationCount,
      if (nearbySensitive != null) 'nearby_sensitive': nearbySensitive,
      'image': await MultipartFile.fromFile(image.path,
          filename: image.path.split('/').last),
    });
    final res = await _dio.post('/complaints/submit', data: formData);
    return res.data;
  }

  Future<List<dynamic>> getMyComplaints() async {
    final res = await _dio.get('/complaints/my');
    return res.data;
  }

  Future<Map<String, dynamic>> getComplaint(String complaintId) async {
    final res = await _dio.get('/complaints/$complaintId');
    return res.data;
  }
}
