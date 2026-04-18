import 'package:http_certificate_pinning/http_certificate_pinning.dart';
import 'dart:developer' as dev;

class ApiService {
  static const String _configuredBaseUrl =
      String.fromEnvironment('ROADWATCH_API_URL', defaultValue: '');
  static String get baseUrl {
    if (_configuredBaseUrl.isNotEmpty) return _configuredBaseUrl;
    if (Platform.isAndroid) return 'http://10.0.2.2:8000/api';
    return 'http://127.0.0.1:8000/api';
  }
  
  // Production Fingerprint for road-damage-appsystem.onrender.com
  static const List<String> _allowedFingerprints = [
    "5E:0C:BF:6B:43:03:7E:6D:4A:8C:BD:4E:00:8C:AA:ED:4B:32:0A:7D:02:49:5C:3D:28:C2:2C:99:63:73:9B:4E"
  ];

  final Dio _dio = Dio(BaseOptions(baseUrl: baseUrl));

  Dio get dio => _dio;

  ApiService() {
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        // Enforce Pinning in Production
        if (!baseUrl.contains("10.0.2.2") && !baseUrl.contains("localhost")) {
          try {
            await HttpCertificatePinning.check(
              serverURL: baseUrl,
              headerHttp: {},
              sha256Fingerprints: _allowedFingerprints,
              timeout: 10,
            );
          } catch (e) {
             // Log to Sentry & Block
             dev.log("CERTIFICATE PINNING FAILURE: $e");
             return handler.reject(DioException(
                requestOptions: options,
                error: "Connection security error: MITM detected or Invalid Certificate.",
                type: DioExceptionType.connectionError,
             ));
          }
        }
        
        final token = await AuthService.getIdToken();
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        return handler.next(options);
      },
    ));
  }

  // --- Auth synced with Firebase ---
  Future<void> logout() async {
    await AuthService.signOut();
  }

  Future<bool> isLoggedIn() async {
    return AuthService.currentUser != null;
  }

  Future<String?> getToken() async {
    return await AuthService.getIdToken();
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
