import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import 'complaint_detail_screen.dart';
import 'complaint_tracker_screen.dart';

class MyComplaintsScreen extends StatefulWidget {
  const MyComplaintsScreen({super.key});
  @override
  State<MyComplaintsScreen> createState() => _MyComplaintsScreenState();
}

class _MyComplaintsScreenState extends State<MyComplaintsScreen> {
  static final DateFormat _reportDateTimeFormat = DateFormat('dd MMM yyyy, hh:mm a');
  late Future<List<dynamic>> _complaints;

  @override
  void initState() {
    super.initState();
    _complaints = context.read<ApiService>().getMyComplaints();
  }

  Color _severityColor(String severity) {
    switch (severity.toLowerCase()) {
      case 'high': return Colors.redAccent;
      case 'medium': return Colors.orange;
      default: return Colors.greenAccent;
    }
  }

  Color _statusColor(String status) {
    switch (status.toLowerCase()) {
      case 'completed': return Colors.greenAccent;
      case 'in_progress': return Colors.blueAccent;
      case 'assigned': return Colors.orange;
      case 'rejected': return Colors.redAccent;
      default: return Colors.grey;
    }
  }

  String _statusLabel(String status) {
    return status.replaceAll('_', ' ').toUpperCase();
  }

  DateTime? _parseDateValue(dynamic value) {
    if (value == null) return null;
    var text = value.toString().trim();
    if (text.isEmpty) return null;
    text = text.replaceFirst(' ', 'T');
    final hasOffset = RegExp(r'(Z|[+-]\d{2}:\d{2})$').hasMatch(text);
    if (RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text)) {
      text = '${text}T00:00:00Z';
    } else if (!hasOffset) {
      text = '${text}Z';
    }
    try {
      return DateTime.parse(text).toUtc().add(const Duration(hours: 5, minutes: 30));
    } catch (_) {
      return null;
    }
  }

  String _formatReportedAt(dynamic value) {
    final parsed = _parseDateValue(value);
    if (parsed == null) return '--';
    return '${_reportDateTimeFormat.format(parsed)} IST';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Complaints'),
        backgroundColor: const Color(0xFFF5A623),
        foregroundColor: Colors.black,
      ),
      body: FutureBuilder<List<dynamic>>(
        future: _complaints,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }
          final complaints = snap.data ?? [];
          if (complaints.isEmpty) {
            return const Center(
              child: Text('No complaints yet.\nTap + to report road damage.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.white54)));
          }
          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: complaints.length,
            itemBuilder: (_, i) {
              final c = complaints[i];
              return InkWell(
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => ComplaintTrackerScreen(
                        complaintId: c['complaint_id'] as String,
                        initialStatus: c['status'] as String? ?? 'pending',
                      ),
                    ),
                  );
                },
                child: Card(
                  color: Colors.grey[850],
                  margin: const EdgeInsets.only(bottom: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(c['complaint_id'],
                                style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: Color(0xFFF5A623),
                                    fontSize: 14)),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                              decoration: BoxDecoration(
                                color: _statusColor(c['status']).withOpacity(0.15),
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: Text(_statusLabel(c['status']),
                                  style: TextStyle(
                                      color: _statusColor(c['status']),
                                      fontSize: 11,
                                      fontWeight: FontWeight.bold)),
                            ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        Row(children: [
                          Icon(Icons.warning_amber_rounded,
                              size: 16, color: _severityColor(c['severity'])),
                          const SizedBox(width: 6),
                          Text('${c['severity'].toUpperCase()} — ${c['damage_type'].replaceAll('_', ' ')}',
                              style: TextStyle(
                                  color: _severityColor(c['severity']), fontSize: 13)),
                        ]),
                        const SizedBox(height: 6),
                        if (c['address'] != null)
                          Row(children: [
                            const Icon(Icons.location_on, size: 14, color: Colors.white38),
                            const SizedBox(width: 4),
                            Expanded(child: Text(c['address'],
                                style: const TextStyle(color: Colors.white60, fontSize: 12))),
                          ]),
                        const SizedBox(height: 8),
                        Row(children: [
                          const Icon(Icons.schedule, size: 14, color: Colors.white38),
                          const SizedBox(width: 4),
                          Expanded(
                            child: Text(
                              'Registered ${_formatReportedAt(c['created_at'])}',
                              style: const TextStyle(color: Colors.white60, fontSize: 12),
                            ),
                          ),
                        ]),
                        if (c['description'] != null) ...[
                          const SizedBox(height: 8),
                          Text(c['description'],
                              style: const TextStyle(color: Colors.white70, fontSize: 12)),
                        ],
                        if (c['officer_notes'] != null) ...[
                          const SizedBox(height: 8),
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: Colors.blueAccent.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text('Officer: ${c['officer_notes']}',
                                style: const TextStyle(color: Colors.lightBlueAccent, fontSize: 12)),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
