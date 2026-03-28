import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:geolocator/geolocator.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';

class ReportScreen extends StatefulWidget {
  const ReportScreen({super.key});
  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  File? _image;
  Position? _position;
  Map<String, dynamic>? _priorityPreview;
  bool _isLoading = false;
  bool _isSyncingPriority = false;
  bool _locationDeniedForever = false;
  bool _locationServicesDisabled = false;
  String? _result;
  String? _error;
  String _locationStatus = 'Requesting location sync...';

  final ImagePicker _picker = ImagePicker();

  Future<void> _pickImage(ImageSource source) async {
    final XFile? file = await _picker.pickImage(
      source: source,
      imageQuality: 85,
      maxWidth: 1920,
    );
    if (file != null) setState(() => _image = File(file.path));
  }

  Future<void> _getLocation() async {
    if (mounted) {
      setState(() {
        _error = null;
        _locationStatus = 'Checking GPS permission...';
      });
    }
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      if (!mounted) return;
      setState(() {
        _locationServicesDisabled = true;
        _locationStatus = 'Location services are disabled.';
        _error = 'Turn on device location to sync priority analysis faster.';
      });
      return;
    }
    if (mounted) {
      setState(() => _locationServicesDisabled = false);
    }
    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied) {
      if (!mounted) return;
      setState(() {
        _locationStatus = 'Location permission denied.';
        _error = 'Allow location access so GPS and priority analysis can sync automatically.';
      });
      return;
    }
    if (permission == LocationPermission.deniedForever) {
      if (!mounted) return;
      setState(() {
        _locationDeniedForever = true;
        _locationStatus = 'Location permission permanently denied.';
        _error = 'Open app settings and allow location access to sync automatically.';
      });
      return;
    }
    try {
      final pos = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 15),
      );
      if (!mounted) return;
      setState(() {
        _position = pos;
        _locationDeniedForever = false;
        _locationStatus = 'Live GPS synced';
      });
      await _syncPriorityPreview();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _locationStatus = 'Unable to read device GPS.';
        _error = 'Could not get your live location. Try again in an open area.';
      });
    }
  }

  Future<void> _syncPriorityPreview() async {
    if (_position == null) return;
    if (mounted) {
      setState(() => _isSyncingPriority = true);
    }
    try {
      final api = context.read<ApiService>();
      final preview = await api.previewPriority(
        latitude: _position!.latitude,
        longitude: _position!.longitude,
      );
      if (!mounted) return;
      setState(() {
        _priorityPreview = preview;
        _locationStatus = (preview['duplicate_detected'] ?? false)
            ? 'GPS synced with nearby reports'
            : 'GPS and priority synced';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error ??= 'Priority preview sync failed. Submission still works.';
      });
    } finally {
      if (mounted) {
        setState(() => _isSyncingPriority = false);
      }
    }
  }

  Future<void> _submit() async {
    if (_image == null) {
      setState(() => _error = 'Please capture or select a road image.');
      return;
    }
    setState(() { _isLoading = true; _error = null; });

    if (_position == null) await _getLocation();
    if (_position == null) {
      setState(() {
        _error ??= 'Location is required to submit a complaint.';
        _isLoading = false;
      });
      return;
    }

    try {
      final api = context.read<ApiService>();
      final complaint = await api.submitComplaint(
        latitude: _position!.latitude,
        longitude: _position!.longitude,
        address: _priorityPreview?['address'] as String?,
        areaType: _priorityPreview?['area_type'] as String?,
        impactScore:
            (_priorityPreview?['impact_score'] as num?)?.toDouble(),
        sensitiveLocationCount:
            (_priorityPreview?['sensitive_location_count'] as num?)?.toInt(),
        image: _image!,
      );
      setState(() {
        _result = complaint['complaint_id'];
        _isLoading = false;
      });
    } catch (e) {
      setState(() { _error = e.toString(); _isLoading = false; });
    }
  }

  @override
  void initState() {
    super.initState();
    _getLocation();
  }

  String _formatAreaLabel(dynamic areaType) {
    final raw = (areaType ?? 'residential').toString().replaceAll('_', ' ');
    return raw.isEmpty
        ? 'Residential'
        : raw[0].toUpperCase() + raw.substring(1);
  }

  Color _priorityColor(num score) {
    if (score >= 70) return Colors.redAccent;
    if (score >= 35) return const Color(0xFFF5A623);
    return Colors.greenAccent;
  }

  @override
  Widget build(BuildContext context) {
    if (_result != null) return _buildSuccess();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Report Road Damage'),
        backgroundColor: const Color(0xFFF5A623),
        foregroundColor: Colors.black,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Image preview
            GestureDetector(
              onTap: () => _showImageSourceDialog(),
              child: Container(
                height: 240,
                decoration: BoxDecoration(
                  color: Colors.grey[850],
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: const Color(0xFFF5A623), width: 2),
                ),
                child: _image == null
                    ? const Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.camera_alt, size: 56, color: Color(0xFFF5A623)),
                          SizedBox(height: 12),
                          Text('Tap to capture road damage photo',
                              style: TextStyle(color: Colors.white54)),
                        ],
                      )
                    : ClipRRect(
                        borderRadius: BorderRadius.circular(14),
                        child: Image.file(_image!, fit: BoxFit.cover)),
              ),
            ),
            const SizedBox(height: 20),

            // Location card
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.grey[850],
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Icon(
                      _position != null
                          ? Icons.location_on
                          : Icons.location_searching,
                      color:
                          _position != null ? Colors.greenAccent : Colors.orange,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        _position != null
                            ? 'GPS: ${_position!.latitude.toStringAsFixed(5)}, ${_position!.longitude.toStringAsFixed(5)}'
                            : _locationStatus,
                        style: const TextStyle(
                            color: Colors.white70, fontSize: 13),
                      ),
                    ),
                  ]),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      OutlinedButton.icon(
                        onPressed: _isLoading ? null : _getLocation,
                        icon: const Icon(Icons.my_location),
                        label: Text(
                          _position == null ? 'Allow location' : 'Refresh GPS',
                        ),
                      ),
                      if (_locationDeniedForever)
                        OutlinedButton.icon(
                          onPressed: Geolocator.openAppSettings,
                          icon: const Icon(Icons.settings),
                          label: const Text('Open settings'),
                        ),
                      if (_locationServicesDisabled)
                        OutlinedButton.icon(
                          onPressed: Geolocator.openLocationSettings,
                          icon: const Icon(Icons.gps_off),
                          label: const Text('Turn on GPS'),
                        ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),

            if (_priorityPreview != null || _isSyncingPriority)
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.grey[900],
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFFF5A623)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.bolt, color: Color(0xFFF5A623)),
                        const SizedBox(width: 10),
                        const Expanded(
                          child: Text(
                            'Priority Sync',
                            style: TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        if (_isSyncingPriority)
                          const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      _priorityPreview == null
                          ? 'Syncing live system priority from your current location...'
                          : 'Estimated priority P${(_priorityPreview!['estimated_priority_score'] ?? 0)}',
                      style: TextStyle(
                        color: _priorityPreview == null
                            ? Colors.white70
                            : _priorityColor(
                                (_priorityPreview!['estimated_priority_score']
                                        as num?) ??
                                    0,
                              ),
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    if (_priorityPreview != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        'Area: ${_formatAreaLabel(_priorityPreview!['area_type'])}',
                        style: const TextStyle(color: Colors.white70),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        (_priorityPreview!['duplicate_detected'] ?? false)
                            ? '${_priorityPreview!['nearby_report_count']} nearby open reports detected'
                            : 'No nearby duplicate reports detected',
                        style: const TextStyle(color: Colors.white54),
                      ),
                    ],
                  ],
                ),
              ),

            if (_priorityPreview != null || _isSyncingPriority)
              const SizedBox(height: 12),

            if (_error != null)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.red.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(_error!, style: const TextStyle(color: Colors.redAccent)),
              ),

            const SizedBox(height: 20),
            SizedBox(
              height: 54,
              child: ElevatedButton(
                onPressed: _isLoading ? null : _submit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFF5A623),
                  foregroundColor: Colors.black,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: _isLoading
                    ? const CircularProgressIndicator(color: Colors.black)
                    : const Text('SUBMIT COMPLAINT',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showImageSourceDialog() {
    showModalBottomSheet(
      context: context,
      builder: (_) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(
            leading: const Icon(Icons.camera_alt),
            title: const Text('Take Photo'),
            onTap: () { Navigator.pop(context); _pickImage(ImageSource.camera); },
          ),
          ListTile(
            leading: const Icon(Icons.photo_library),
            title: const Text('Choose from Gallery'),
            onTap: () { Navigator.pop(context); _pickImage(ImageSource.gallery); },
          ),
        ]),
      ),
    );
  }

  Widget _buildSuccess() {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.check_circle, color: Colors.greenAccent, size: 80),
              const SizedBox(height: 20),
              const Text('Complaint Submitted!',
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              Text('Complaint ID: $_result',
                  style: const TextStyle(fontSize: 16, color: Color(0xFFF5A623))),
              const SizedBox(height: 8),
              const Text('A field officer has been notified.\nTrack progress in My Complaints.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.white60)),
              const SizedBox(height: 32),
              ElevatedButton(
                onPressed: () => Navigator.pushReplacementNamed(context, '/home'),
                child: const Text('Back to Home'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
