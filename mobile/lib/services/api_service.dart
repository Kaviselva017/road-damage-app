import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiService {
  static const String baseUrl = 'http://YOUR_SERVER_IP:8000/api';
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

  // --- Complaints ---
  Future<Map<String, dynamic>> submitComplaint({
    required double latitude,
    required double longitude,
    String? address,
    required File image,
  }) async {
    final formData = FormData.fromMap({
      'latitude': latitude,
      'longitude': longitude,
      if (address != null) 'address': address,
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
