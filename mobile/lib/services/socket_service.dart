// lib/services/socket_service.dart
// ===================================
// WebSocket service for the RoadWatch Flutter app.
// Uses web_socket_channel ^2.4.0 (add to pubspec.yaml).
//
// Features:
//   - ConnectSocket(token): authenticates via ?token= query param
//   - DisconnectSocket(): graceful close
//   - Stream<Map<String,dynamic>> statusStream: filtered events for UI
//   - Auto-reconnect on error with exponential back-off (1s → 2s → … → 30s)
//   - Responds to server "ping" with "pong"
//
// pubspec.yaml additions:
//   dependencies:
//     web_socket_channel: ^2.4.0

import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

class SocketService {
  // ── Singleton ──────────────────────────────────────────────────────────────
  static final SocketService _instance = SocketService._internal();
  factory SocketService() => _instance;
  SocketService._internal();

  // ── Config ──────────────────────────────────────────────────────────────────
  static const String _baseWsUrl =
      String.fromEnvironment('WS_BASE_URL', defaultValue: 'ws://10.0.2.2:8000');
  static const int _maxBackoffSeconds = 30;

  // ── State ───────────────────────────────────────────────────────────────────
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _reconnectTimer;

  String? _token;
  String? _userId;

  bool _intentionalClose = false;
  int _backoffSeconds = 1;

  // ── Output stream ────────────────────────────────────────────────────────────
  final StreamController<Map<String, dynamic>> _controller =
      StreamController<Map<String, dynamic>>.broadcast();

  Stream<Map<String, dynamic>> get statusStream => _controller.stream;

  bool get isConnected => _channel != null;

  // ── Public API ───────────────────────────────────────────────────────────────

  /// Connect to the RoadWatch WS endpoint authenticated with [token].
  /// [userId] must match the JWT `sub` claim.
  void connectSocket({required String token, required String userId}) {
    _token = token;
    _userId = userId;
    _intentionalClose = false;
    _backoffSeconds = 1;
    _connect();
  }

  /// Gracefully close the WebSocket and stop auto-reconnect.
  void disconnectSocket() {
    _intentionalClose = true;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _close();
  }

  void dispose() {
    disconnectSocket();
    _controller.close();
  }

  // ── Internal ─────────────────────────────────────────────────────────────────

  void _connect() {
    if (_token == null || _userId == null) return;

    final uri = Uri.parse(
      '$_baseWsUrl/ws/user/$_userId?token=${Uri.encodeComponent(_token!)}',
    );

    debugPrint('[SocketService] Connecting to $uri');

    try {
      _channel = IOWebSocketChannel.connect(uri);
    } catch (e) {
      debugPrint('[SocketService] Connect failed: $e');
      _scheduleReconnect();
      return;
    }

    _subscription = _channel!.stream.listen(
      _onData,
      onError: _onError,
      onDone: _onDone,
      cancelOnError: false,
    );
  }

  void _onData(dynamic raw) {
    try {
      final Map<String, dynamic> msg = jsonDecode(raw as String);
      final event = msg['event'] as String?;

      // Respond to heartbeat
      if (event == 'ping') {
        _send({'event': 'pong'});
        return;
      }

      // Forward meaningful events to listeners
      if (event == 'status_update' || event == 'inference_complete') {
        _controller.add(msg);
      }
    } catch (e) {
      debugPrint('[SocketService] Parse error: $e');
    }
  }

  void _onError(Object error) {
    debugPrint('[SocketService] Stream error: $error');
    _close();
    if (!_intentionalClose) _scheduleReconnect();
  }

  void _onDone() {
    debugPrint('[SocketService] Stream closed');
    _close();
    if (!_intentionalClose) _scheduleReconnect();
  }

  void _close() {
    _subscription?.cancel();
    _subscription = null;
    _channel?.sink.close();
    _channel = null;
  }

  void _send(Map<String, dynamic> payload) {
    try {
      _channel?.sink.add(jsonEncode(payload));
    } catch (e) {
      debugPrint('[SocketService] Send error: $e');
    }
  }

  void _scheduleReconnect() {
    if (_intentionalClose) return;
    final delay = Duration(seconds: _backoffSeconds);
    debugPrint('[SocketService] Reconnecting in ${delay.inSeconds}s …');
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, () {
      if (!_intentionalClose) _connect();
    });
    _backoffSeconds = min(_backoffSeconds * 2, _maxBackoffSeconds);
  }
}
