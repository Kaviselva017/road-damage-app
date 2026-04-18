import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/push_notification_service.dart';
import '../widgets/pending_badge.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  @override
  void initState() {
    super.initState();
    // Initialize notification handlers
    WidgetsBinding.instance.addPostFrameCallback((_) {
      PushNotificationService.setupBackgroundTapHandler(context);
      PushNotificationService.handleInitialMessage(context);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('RoadWatch'),
        backgroundColor: const Color(0xFFF5A623),
        foregroundColor: Colors.black,
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await context.read<ApiService>().logout();
              if (!mounted) return;
              Navigator.pushReplacementNamed(context, '/login');
            },
          )
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Center(child: PendingBadge()),
            const SizedBox(height: 16),
            const Text('Welcome to RoadWatch',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            const Text('Report issues and track repairs in real-time.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white54)),
            const SizedBox(height: 48),
            _ActionCard(
              icon: Icons.add_a_photo,
              title: 'Report Road Damage',
              subtitle: 'Capture and submit a new complaint',
              color: const Color(0xFFF5A623),
              onTap: () => Navigator.pushNamed(context, '/report'),
            ),
            const SizedBox(height: 20),
            _ActionCard(
              icon: Icons.list_alt,
              title: 'My Complaints',
              subtitle: 'Track status of your reports',
              color: const Color(0xFF3ECFB2),
              onTap: () => Navigator.pushNamed(context, '/my-complaints'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final VoidCallback onTap;

  const _ActionCard({required this.icon, required this.title,
      required this.subtitle, required this.color, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: Color.fromRGBO(color.r.toInt(), color.g.toInt(), color.b.toInt(), 0.1),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: Color.fromRGBO(color.r.toInt(), color.g.toInt(), color.b.toInt(), 0.4),
          ),
        ),
        child: Row(children: [
          Icon(icon, color: color, size: 40),
          const SizedBox(width: 20),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: TextStyle(color: color,
                    fontSize: 17, fontWeight: FontWeight.bold)),
                Text(subtitle,
                    style: const TextStyle(color: Colors.white54, fontSize: 13)),
              ],
            ),
          ),
        ]),
      ),
    );
  }
}
