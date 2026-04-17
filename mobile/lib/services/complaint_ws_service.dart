import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/complaint_status_update.dart';

class ComplaintWebSocketService {
  WebSocketChannel? _channel;
  final _statusController = StreamController<ComplaintStatusUpdate>.broadcast();
  Stream<ComplaintStatusUpdate> get statusStream => _statusController.stream;
  
  String? _currentUrl;
  int _retryCount = 0;
  final int _maxRetries = 3;
  Timer? _reconnectTimer;

  void connect(String complaintId, String token) {
    const wsBase = String.fromEnvironment('WS_URL', defaultValue: 'wss://road-damage-appsystem.onrender.com');
    _currentUrl = '$wsBase/ws/complaints/$complaintId?token=$token';
    _connectInternal();
  }

  void _connectInternal() {
    if (_currentUrl == null) return;
    
    try {
      _channel = WebSocketChannel.connect(Uri.parse(_currentUrl!));
      _retryCount = 0; 
      
      _channel!.stream.listen((message) {
        try {
          final data = jsonDecode(message);
          if (data['type'] == 'ping') {
             // Let the backend ping us, no mandatory response required but we're alive
             return;
          }
          final update = ComplaintStatusUpdate.fromJson(data);
          _statusController.add(update);
        } catch (e) {
          // Ignore invalid payload formats dynamically
        }
      }, onDone: () {
        if (_channel?.closeCode == 4001) {
          // Don't auto-reconnect on Token failures. Terminate manually.
          return;
        }
        _handleDisconnect();
      }, onError: (err) {
        _handleDisconnect();
      });
    } catch (e) {
      _handleDisconnect();
    }
  }

  void _handleDisconnect() {
    if (_retryCount >= _maxRetries) return;
    
    _retryCount++;
    // Exponential Backoff algorithm: 2, 4, 8 seconds
    final backoff = min(pow(2, _retryCount) * 1000, 10000).toInt();
    
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(Duration(milliseconds: backoff), () {
      _connectInternal();
    });
  }

  void disconnect() {
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _channel = null;
    _currentUrl = null;
  }
  
  void dispose() {
    disconnect();
    _statusController.close();
  }
}
