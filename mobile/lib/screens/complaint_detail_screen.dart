import 'package:flutter/material.dart';
import '../services/complaint_ws_service.dart';
import '../models/complaint_status_update.dart';

class ComplaintDetailScreen extends StatefulWidget {
  final Map<String, dynamic> complaint;
  final String token;

  const ComplaintDetailScreen({
    Key? key,
    required this.complaint,
    required this.token,
  }) : super(key: key);

  @override
  State<ComplaintDetailScreen> createState() => _ComplaintDetailScreenState();
}

class _ComplaintDetailScreenState extends State<ComplaintDetailScreen> {
  late ComplaintWebSocketService _wsService;
  late String _currentStatus;

  @override
  void initState() {
    super.initState();
    _currentStatus = widget.complaint['status'] ?? 'pending';
    
    // Instantiate WebSocket Service
    _wsService = ComplaintWebSocketService();
    _wsService.connect(widget.complaint['complaint_id'], widget.token);
    
    // Subscribe to Status Stream
    _wsService.statusStream.listen((update) {
      if (mounted) {
        setState(() {
          _currentStatus = update.status;
          
          // Patch extra AI fields dynamically into memory footprint if needed
          if (update.damageType != null) {
            widget.complaint['damage_type'] = update.damageType;
          }
        });
        
        // Push Success Alert Notification
        if (update.status == 'analyzed') {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text("Your report has been analyzed!"),
              backgroundColor: Colors.green,
            ),
          );
        }
      }
    });
  }

  @override
  void dispose() {
    _wsService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Complaint ${widget.complaint['complaint_id']}'),
        backgroundColor: const Color(0xFFF5A623),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text('Status: ', style: TextStyle(fontSize: 18, color: Colors.white70)),
                Text(
                  _currentStatus.toUpperCase(),
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: _currentStatus == 'analyzed' ? Colors.green : Colors.orange,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            Text('Location: ${widget.complaint['address'] ?? 'Unknown'}', style: const TextStyle(color: Colors.white54)),
            
            const Spacer(),
            const Center(
              child: Text(
                'Listening for live WebSocket updates...',
                style: TextStyle(color: Colors.grey, fontStyle: FontStyle.italic),
              ),
            ),
            const SizedBox(height: 30),
          ],
        ),
      ),
    );
  }
}
