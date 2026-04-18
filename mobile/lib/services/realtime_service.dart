import 'package:supabase_flutter/supabase_flutter.dart';

class ComplaintRealtimeService {
  static RealtimeChannel? _channel;

  static void subscribeToComplaint(
    String complaintId,
    void Function(Map<String, dynamic>) onUpdate,
  ) {
    if (_channel != null) unsubscribe();

    _channel = Supabase.instance.client
        .channel('complaint:$complaintId')
        .onPostgresChanges(
          event: PostgresChangeEvent.update,
          schema: 'public',
          table: 'complaints',
          filter: PostgresChangeFilter(
            type: PostgresChangeFilterType.eq,
            column: 'complaint_id', // Adjust if your table uses 'id' vs 'complaint_id'
            value: complaintId,
          ),
          callback: (payload) {
            onUpdate(payload.newRecord);
          },
        )
        .subscribe();
  }

  static void unsubscribe() {
    if (_channel != null) {
      Supabase.instance.client.removeChannel(_channel!);
      _channel = null;
    }
  }
}
