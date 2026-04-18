import 'package:flutter/material.dart';
import '../services/sync_service.dart';

class PendingBadge extends StatelessWidget {
  const PendingBadge({super.key});

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<int>(
      future: SyncService.pendingCount(),
      builder: (context, snapshot) {
        if (!snapshot.hasData || snapshot.data == 0) {
          return const SizedBox.shrink();
        }

        final count = snapshot.data!;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          decoration: BoxDecoration(
            color: Color.fromRGBO(
              Colors.amber.r.toInt(),
              Colors.amber.g.toInt(),
              Colors.amber.b.toInt(),
              0.15,
            ),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: Color.fromRGBO(
                Colors.amber.r.toInt(),
                Colors.amber.g.toInt(),
                Colors.amber.b.toInt(),
                0.4,
              ),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.hourglass_empty, size: 14, color: Colors.amber),
              const SizedBox(width: 6),
              Text(
                '$count pending',
                style: const TextStyle(
                  color: Colors.amber,
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
