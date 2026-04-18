import 'dart:async';
import 'dart:convert';
import 'dart:developer';
import 'package:flutter/widgets.dart';
import 'package:geolocator/geolocator.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

class LocationBroadcastService with WidgetsBindingObserver {
  WebSocketChannel? _channel;
  Timer? _timer;
  bool _isConnected = false;
  String? _jwtToken;
  String? _wsUrl;
  
  // Singleton pattern
  static final LocationBroadcastService _instance = LocationBroadcastService._internal();
  factory LocationBroadcastService() => _instance;
  LocationBroadcastService._internal() {
    WidgetsBinding.instance.addObserver(this);
  }

  void start(String jwtToken, String baseUrl) async {
    _jwtToken = jwtToken;
    _wsUrl = baseUrl.replaceFirst('http', 'ws');
    
    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.deniedForever || permission == LocationPermission.denied) {
      log('Location permissions denied.');
      return;
    }
    
    _connect();
  }

  void _connect() {
    if (_jwtToken == null || _wsUrl == null) return;
    
    try {
      _channel = WebSocketChannel.connect(
        Uri.parse('$_wsUrl/ws/officers/location?token=$_jwtToken'),
      );
      
      _isConnected = true;
      _channel!.stream.listen(
        (message) {}, 
        onDone: () {
          _isConnected = false;
          _reconnectWithBackoff();
        },
        onError: (error) {
          _isConnected = false;
          _reconnectWithBackoff();
        }
      );
      
      _startBroadcasting();
    } catch (e) {
      _reconnectWithBackoff();
    }
  }

  void _reconnectWithBackoff() {
    _timer?.cancel();
    if (_jwtToken == null) return;
    Future.delayed(const Duration(seconds: 5), () {
      if (!_isConnected) _connect();
    });
  }

  void _startBroadcasting() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 30), (timer) async {
      if (!_isConnected || _channel == null) return;
      
      try {
        final position = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.high
        );
        
        final payload = jsonEncode({
          'lat': position.latitude,
          'lng': position.longitude,
          'timestamp': DateTime.now().toIso8601String(),
        });
        
        _channel!.sink.add(payload);
      } catch (e) {
        log('Error getting location: $e');
      }
    });
  }

  void stop() {
    _jwtToken = null;
    _timer?.cancel();
    _channel?.sink.close();
    _isConnected = false;
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused || state == AppLifecycleState.detached) {
      _timer?.cancel();
      _channel?.sink.close();
    } else if (state == AppLifecycleState.resumed) {
      if (_jwtToken != null && !_isConnected) {
        _connect();
      }
    }
  }
}
