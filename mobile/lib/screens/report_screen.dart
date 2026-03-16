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
  bool _isLoading = false;
  String? _result;
  String? _error;

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
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      setState(() => _error = 'Location services are disabled.');
      return;
    }
    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.deniedForever) {
      setState(() => _error = 'Location permission permanently denied.');
      return;
    }
    final pos = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high);
    setState(() => _position = pos);
  }

  Future<void> _submit() async {
    if (_image == null) {
      setState(() => _error = 'Please capture or select a road image.');
      return;
    }
    setState(() { _isLoading = true; _error = null; });

    if (_position == null) await _getLocation();

    try {
      final api = context.read<ApiService>();
      final complaint = await api.submitComplaint(
        latitude: _position!.latitude,
        longitude: _position!.longitude,
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
              child: Row(children: [
                Icon(
                  _position != null ? Icons.location_on : Icons.location_searching,
                  color: _position != null ? Colors.greenAccent : Colors.orange,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    _position != null
                        ? 'GPS: ${_position!.latitude.toStringAsFixed(5)}, ${_position!.longitude.toStringAsFixed(5)}'
                        : 'Acquiring GPS location...',
                    style: const TextStyle(color: Colors.white70, fontSize: 13),
                  ),
                ),
              ]),
            ),
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
