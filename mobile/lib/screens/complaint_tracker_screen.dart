import 'package:supabase_flutter/supabase_flutter.dart';
import '../services/api_service.dart';
import '../services/realtime_service.dart';

class ComplaintTrackerScreen extends StatefulWidget {
  final String complaintId;
  final String initialStatus;

  const ComplaintTrackerScreen({super.key, required this.complaintId,
    required this.initialStatus,
  });

  @override
  State<ComplaintTrackerScreen> createState() => _ComplaintTrackerScreenState();
}

class _ComplaintTrackerScreenState extends State<ComplaintTrackerScreen> {
  String _currentStatus = 'pending';
  Map<String, dynamic> _extraData = {};
  bool _isConnected = false;
  String? _imageUrl;

  final List<String> _stages = [
    'pending',
    'analyzed',
    'assigned',
    'in_progress',
    'completed'
  ];

  @override
  void initState() {
    super.initState();
    _currentStatus = widget.initialStatus;
    _setupSupabaseRealtime();
    _fetchSignedUrl();
  }

  void _setupSupabaseRealtime() {
    ComplaintRealtimeService.subscribeToComplaint(widget.complaintId, (newRecord) {
      if (!mounted) return;
      setState(() {
        _currentStatus = newRecord['status'] ?? _currentStatus;
        _extraData = newRecord;
        _isConnected = true;
      });
    });
    setState(() => _isConnected = true);
  }

  Future<void> _fetchSignedUrl() async {
    try {
      final api = context.read<ApiService>();
      final res = await api.dio.get('/complaints/${widget.complaintId}/image-url');
      if (mounted) {
        setState(() {
          _imageUrl = res.data['url'];
        });
      }
    } catch (e) {
      debugPrint("Error fetching signed URL: $e");
    }
  }

  @override
  void dispose() {
    ComplaintRealtimeService.unsubscribe();
    super.dispose();
  }

  Widget _buildTimelineNode(String defaultLabel, String stageId, int index) {
    int currentIndex = _stages.indexOf(_currentStatus);
    bool isCompleted = _stages.indexOf(stageId) <= currentIndex;
    bool isCurrent = stageId == _currentStatus;
    
    Color activeColor = Colors.teal;
    if (stageId == 'completed') activeColor = Colors.green;
    if (stageId == 'in_progress') activeColor = Colors.orange;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Container(
                margin: const EdgeInsets.only(top: 8),
                width: 24,
                height: 24,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isCompleted ? activeColor : Colors.grey.shade300,
                  border: isCurrent ? Border.all(color: activeColor.withOpacity(0.5), width: 4) : null,
                ),
                child: isCompleted ? const Icon(Icons.check, size: 16, color: Colors.white) : null,
              ),
              if (index < _stages.length - 1)
                Container(
                  width: 3,
                  height: 60,
                  color: isCompleted ? activeColor : Colors.grey.shade300,
                )
            ],
          ),
          const SizedBox(width: 20),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 10),
                Text(
                  defaultLabel,
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: isCompleted ? FontWeight.bold : FontWeight.w500,
                    color: isCompleted ? Colors.black87 : Colors.grey,
                  ),
                ),
                if (stageId == 'analyzed' && isCompleted && _extraData.containsKey("damage_type")) ...[
                  const SizedBox(height: 4),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.blue.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      "AI Detection: ${_extraData['damage_type'].toString().replaceAll('_', ' ').toUpperCase()} (${((_extraData['confidence'] ?? 0) * 100).toStringAsFixed(1)}%)",
                      style: const TextStyle(fontSize: 12, color: Colors.blue),
                    ),
                  )
                ],
                const SizedBox(height: 20),
              ],
            ),
          )
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Live Tracker'),
        actions: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Icon(
              Icons.circle,
              size: 12,
              color: _isConnected ? Colors.green : Colors.red,
            ),
          )
        ],
      ),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              color: Colors.blueGrey.shade50,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text("Complaint ID", style: TextStyle(color: Colors.grey.shade600)),
                  const SizedBox(height: 4),
                  Text(widget.complaintId, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                ],
              ),
            ),
            const SizedBox(height: 30),
            _buildTimelineNode("Submitted", "pending", 0),
            _buildTimelineNode("Analyzed by AI", "analyzed", 1),
            _buildTimelineNode("Assigned to Officer", "assigned", 2),
            _buildTimelineNode("In Progress", "in_progress", 3),
            _buildTimelineNode("Completed", "completed", 4),
          ],
        ),
      ),
    );
  }
}
