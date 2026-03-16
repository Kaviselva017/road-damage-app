import 'package:flutter/material.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Road Damage Reporter'),
        backgroundColor: const Color(0xFFF5A623),
        foregroundColor: Colors.black,
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => Navigator.pushReplacementNamed(context, '/login'),
          )
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('What would you like to do?',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 32),
            _ActionCard(
              icon: Icons.add_a_photo,
              title: 'Report Road Damage',
              subtitle: 'Capture and submit a new complaint',
              color: const Color(0xFFF5A623),
              onTap: () => Navigator.pushNamed(context, '/report'),
            ),
            const SizedBox(height: 16),
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
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: color.withOpacity(0.4)),
        ),
        child: Row(children: [
          Icon(icon, color: color, size: 40),
          const SizedBox(width: 20),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: TextStyle(color: color,
                  fontSize: 17, fontWeight: FontWeight.bold)),
              Text(subtitle,
                  style: const TextStyle(color: Colors.white54, fontSize: 13)),
            ],
          ),
        ]),
      ),
    );
  }
}
