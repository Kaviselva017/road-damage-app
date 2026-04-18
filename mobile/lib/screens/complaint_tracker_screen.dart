import 'dart:async';
import 'dart:convert';
import 'dart:developer' as dev;

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:web_socket_channel/io.dart';

import '../services/api_service.dart';

// ── Helpers ───────────────────────────────────────────────────────────────────

final _dtFmt = DateFormat('dd MMM yyyy, hh:mm a');

DateTime? _parseDate(dynamic v) {
  if (v == null) return null;
  var s = v.toString().trim();
  if (s.isEmpty) return null;
  s = s.replaceFirst(' ', 'T');
  if (!RegExp(r'(Z|[+-]\d{2}:\d{2})$').hasMatch(s)) s = '${s}Z';
  try {
    return DateTime.parse(s)
        .toUtc()
        .add(const Duration(hours: 5, minutes: 30));
  } catch (_) {
    return null;
  }
}

String _fmt(dynamic v) {
  final d = _parseDate(v);
  return d == null ? '—' : '${_dtFmt.format(d)} IST';
}

const _kBg = Color(0xFF0F172A);
const _kCard = Color(0xFF1E293B);
const _kBlue = Color(0xFF3B82F6);
const _kPurple = Color(0xFF8B5CF6);
const _kAmber = Color(0xFFF59E0B);
const _kRed = Color(0xFFEF4444);
const _kGreen = Color(0xFF22C55E);

// ── Widget ────────────────────────────────────────────────────────────────────

class ComplaintTrackerScreen extends StatefulWidget {
  const ComplaintTrackerScreen({
    super.key,
    required this.complaintId,
    this.initialStatus = 'pending',
  });

  final String complaintId;
  final String initialStatus;

  @override
  State<ComplaintTrackerScreen> createState() => _ComplaintTrackerScreenState();
}

class _ComplaintTrackerScreenState extends State<ComplaintTrackerScreen> {
  Map<String, dynamic>? _complaint;
  bool _loading = true;
  String? _error;
  IOWebSocketChannel? _wsChannel;
  StreamSubscription<dynamic>? _wsSub;

  @override
  void initState() {
    super.initState();
    _fetchComplaint();
    _connectWebSocket();
  }

  @override
  void dispose() {
    _wsSub?.cancel();
    _wsChannel?.sink.close();
    super.dispose();
  }

  // ── Data fetching ──────────────────────────────────────────────────────────

  Future<void> _fetchComplaint() async {
    try {
      final api = context.read<ApiService>();
      final data = await api.getComplaint(widget.complaintId);
      if (!mounted) return;
      setState(() {
        _complaint = data;
        _loading = false;
      });
    } catch (e) {
      dev.log('[Tracker] fetchComplaint error: $e');
      if (!mounted) return;
      setState(() {
        _error = 'Failed to load complaint details.';
        _loading = false;
      });
    }
  }

  Future<void> _connectWebSocket() async {
    // Capture context-dependent objects before any await
    final api = context.read<ApiService>();
    try {
      final token = await api.getToken();
      if (!mounted) return;
      if (token == null) return;

      final wsBase = ApiService.baseUrl
          .replaceFirst('https://', 'wss://')
          .replaceFirst('http://', 'ws://')
          .replaceFirst('/api', '');

      final uri =
          Uri.parse('$wsBase/ws/complaints/${widget.complaintId}?token=$token');

      _wsChannel = IOWebSocketChannel.connect(uri);

      _wsSub = _wsChannel!.stream.listen(
        (raw) {
          try {
            final msg = jsonDecode(raw as String) as Map<String, dynamic>;
            if (msg['type'] == 'ping') return;

            if (!mounted) return;
            setState(() {
              _complaint ??= {};
              if (msg['status'] != null) {
                _complaint!['status'] = msg['status'];
              }
              if (msg['damage_type'] != null) {
                _complaint!['damage_type'] = msg['damage_type'];
              }
              if (msg['confidence'] != null) {
                _complaint!['confidence_score'] = msg['confidence'];
              }
              if (msg['complaint_id'] != null) {
                _complaint!['complaint_id'] = msg['complaint_id'];
              }
            });

            final status = msg['status'] as String?;
            if (status == 'analyzed') {
              _showSnack('AI analysis complete! 🤖', _kPurple);
            } else if (status == 'completed') {
              _showSnack('Road has been repaired! ✅', _kGreen);
            }
          } catch (e) {
            dev.log('[Tracker] WS parse error: $e');
          }
        },
        onError: (e) => dev.log('[Tracker] WS error: $e'),
        onDone: () => dev.log('[Tracker] WS closed'),
      );
    } catch (e) {
      dev.log('[Tracker] WS connect error: $e');
    }
  }

  void _showSnack(String msg, Color color) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg, style: const TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: color,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 4),
      ),
    );
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  String get _status => _complaint?['status'] as String? ?? widget.initialStatus;

  bool _reached(List<String> statuses) => statuses.contains(_status);

  double get _priority {
    final v = _complaint?['priority_score'];
    if (v == null) return 0;
    return (v as num).toDouble().clamp(0, 100);
  }

  String get _urgency =>
      (_complaint?['urgency_label'] as String? ?? '').toLowerCase();

  Color _urgencyColor() {
    switch (_urgency) {
      case 'critical':
        return _kRed;
      case 'high':
        return _kAmber;
      case 'medium':
        return Colors.yellow;
      default:
        return _kGreen;
    }
  }

  String _confidenceLabel() {
    final v = _complaint?['confidence_score'];
    if (v == null) return '';
    final pct = ((v as num).toDouble() * 100).toStringAsFixed(1);
    return '  •  $pct% confidence';
  }

  // ── UI ─────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _kBg,
      appBar: AppBar(
        title: const Text(
          'Complaint Tracker',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        backgroundColor: _kBg,
        iconTheme: const IconThemeData(color: Colors.white),
        elevation: 0,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: _kAmber))
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(_error!,
                        style: const TextStyle(color: Colors.white70),
                        textAlign: TextAlign.center),
                  ),
                )
              : _buildBody(),
    );
  }

  Widget _buildBody() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildSummaryCard(),
          const SizedBox(height: 24),
          _buildTimeline(),
          const SizedBox(height: 24),
          if (_priority > 0) _buildPriorityCard(),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  // ── Summary card ──────────────────────────────────────────────────────────

  Widget _buildSummaryCard() {
    final c = _complaint!;
    final address = c['address'] as String?;
    final lat = c['latitude'];
    final lng = c['longitude'];
    final location = address != null && address.isNotEmpty
        ? address
        : (lat != null && lng != null
            ? 'GPS: ${(lat as num).toStringAsFixed(5)}, ${(lng as num).toStringAsFixed(5)}'
            : null);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: _kCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            c['complaint_id'] as String? ?? widget.complaintId,
            style: const TextStyle(
              color: _kAmber,
              fontSize: 22,
              fontWeight: FontWeight.bold,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 10),
          _infoRow(Icons.calendar_today_outlined,
              'Submitted: ${_fmt(c['created_at'])}'),
          if (location != null) ...[
            const SizedBox(height: 6),
            _infoRow(Icons.location_on_outlined, location),
          ],
        ],
      ),
    );
  }

  Widget _infoRow(IconData icon, String text) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 14, color: Colors.white38),
        const SizedBox(width: 6),
        Expanded(
          child: Text(text,
              style: const TextStyle(color: Colors.white60, fontSize: 13)),
        ),
      ],
    );
  }

  // ── Timeline ───────────────────────────────────────────────────────────────

  Widget _buildTimeline() {
    final dt = (_complaint?['damage_type'] as String? ?? '')
        .replaceAll('_', ' ')
        .toUpperCase();
    final isUndetected = _status == 'undetected';
    final isFailed = _status == 'failed';

    final steps = <_TimelineStep>[
      _TimelineStep(
        color: _kBlue,
        title: 'Submitted',
        icon: Icons.check_circle_outline,
        reached: true,
        subtitle: _fmt(_complaint?['created_at']),
      ),
      _TimelineStep(
        color: _kPurple,
        title: 'AI Analysis',
        icon: Icons.smart_toy_outlined,
        reached:
            _reached(['analyzed', 'assigned', 'in_progress', 'completed']),
        subtitle: _reached(['analyzed', 'assigned', 'in_progress', 'completed'])
            ? '$dt detected${_confidenceLabel()}'
            : 'Running AI detection...',
      ),
      _TimelineStep(
        color: _kAmber,
        title: 'Officer Assigned',
        icon: Icons.person_pin_outlined,
        reached: _reached(['assigned', 'in_progress', 'completed']),
        subtitle:
            (_complaint?['officer_name'] as String?) ?? 'Assigned to field team',
      ),
      _TimelineStep(
        color: _kRed,
        title: 'Repair In Progress',
        icon: Icons.construction_outlined,
        reached: _reached(['in_progress', 'completed']),
        subtitle: 'Field officer working on repair',
      ),
      _TimelineStep(
        color: _kGreen,
        title: 'Completed ✅',
        icon: Icons.verified_outlined,
        reached: _reached(['completed']),
        subtitle: 'Road repaired successfully',
      ),
    ];

    final widgets = <Widget>[];
    for (int i = 0; i < steps.length; i++) {
      widgets.add(_buildStep(steps[i], isLast: i == steps.length - 1));

      // Insert special cards between Step 2 (index 1) and Step 3 (index 2)
      if (i == 1) {
        if (isUndetected) {
          widgets.add(_buildInfoCard(
            'AI could not detect clear damage. An officer will review manually.',
            const Color(0x26F59E0B),
            _kAmber,
          ));
        } else if (isFailed) {
          widgets.add(_buildInfoCard(
            'AI analysis failed. Complaint queued for manual review.',
            const Color(0x26EF4444),
            _kRed,
          ));
        }
      }

      // Resolved proof image after "Completed" step
      if (i == 4 && steps[i].reached) {
        final proofUrl = _complaint?['resolved_proof_url'] as String?;
        if (proofUrl != null && proofUrl.isNotEmpty) {
          widgets.add(const SizedBox(height: 12));
          widgets.add(_buildProofImage(proofUrl));
        }
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: widgets,
    );
  }

  Widget _buildStep(_TimelineStep step, {required bool isLast}) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Circle + connector
        Column(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: step.reached ? step.color : const Color(0xFF334155),
                border: Border.all(
                  color: step.reached
                      ? Color.fromRGBO(
                          step.color.r.toInt(),
                          step.color.g.toInt(),
                          step.color.b.toInt(),
                          0.4,
                        )
                      : const Color(0xFF475569),
                  width: 2,
                ),
              ),
              child: Icon(
                step.icon,
                size: 16,
                color: step.reached ? Colors.white : Colors.white30,
              ),
            ),
            if (!isLast)
              Container(
                width: 2,
                height: 56,
                color: step.reached
                    ? Color.fromRGBO(
                        step.color.r.toInt(),
                        step.color.g.toInt(),
                        step.color.b.toInt(),
                        0.5,
                      )
                    : const Color(0xFF334155),
              ),
          ],
        ),
        const SizedBox(width: 16),
        // Title + subtitle
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(top: 4, bottom: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  step.title,
                  style: TextStyle(
                    color: step.reached ? Colors.white : Colors.white38,
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                if (step.subtitle.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    step.subtitle,
                    style: TextStyle(
                      color: step.reached ? Colors.white60 : Colors.white24,
                      fontSize: 12,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildInfoCard(String message, Color bg, Color border) {
    return Container(
      margin: const EdgeInsets.only(left: 48, bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: Color.fromRGBO(
            border.r.toInt(), border.g.toInt(), border.b.toInt(), 0.4),
        ),
      ),
      child: Text(
        message,
        style: TextStyle(color: border, fontSize: 13),
      ),
    );
  }

  Widget _buildProofImage(String url) {
    return Container(
      margin: const EdgeInsets.only(left: 48),
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Color.fromRGBO(
            _kGreen.r.toInt(), _kGreen.g.toInt(), _kGreen.b.toInt(), 0.4),
        ),
      ),
      child: Image.network(
        url,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => Container(
          height: 100,
          color: _kCard,
          child: const Center(
            child: Text('Could not load proof image',
                style: TextStyle(color: Colors.white38, fontSize: 12)),
          ),
        ),
      ),
    );
  }

  // ── Priority card ──────────────────────────────────────────────────────────

  Widget _buildPriorityCard() {
    final score = _priority;
    final urgencyColor = _urgencyColor();
    final urgencyLabel =
        _urgency.isEmpty ? 'N/A' : _urgency[0].toUpperCase() + _urgency.substring(1);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: _kCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Priority Score',
                  style: TextStyle(
                      color: Colors.white70,
                      fontSize: 13,
                      fontWeight: FontWeight.w600)),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: Color.fromRGBO(
                    urgencyColor.r.toInt(),
                    urgencyColor.g.toInt(),
                    urgencyColor.b.toInt(),
                    0.15,
                  ),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: Color.fromRGBO(
                      urgencyColor.r.toInt(),
                      urgencyColor.g.toInt(),
                      urgencyColor.b.toInt(),
                      0.4,
                    ),
                  ),
                ),
                child: Text(
                  urgencyLabel,
                  style: TextStyle(
                      color: urgencyColor,
                      fontSize: 12,
                      fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Text(
                '${score.toStringAsFixed(0)}',
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 32,
                    fontWeight: FontWeight.bold),
              ),
              const Text('/100',
                  style: TextStyle(color: Colors.white38, fontSize: 16)),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: score / 100,
              minHeight: 8,
              backgroundColor: const Color(0xFF334155),
              valueColor: AlwaysStoppedAnimation<Color>(
                score >= 75
                    ? _kRed
                    : score >= 50
                        ? _kAmber
                        : _kGreen,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Data class ────────────────────────────────────────────────────────────────

class _TimelineStep {
  const _TimelineStep({
    required this.color,
    required this.title,
    required this.icon,
    required this.reached,
    required this.subtitle,
  });

  final Color color;
  final String title;
  final IconData icon;
  final bool reached;
  final String subtitle;
}
