class ComplaintStatusUpdate {
  final String complaintId;
  final String status;
  final String? damageType;
  final double? confidence;
  final String? timestamp;

  ComplaintStatusUpdate({
    required this.complaintId,
    required this.status,
    this.damageType,
    this.confidence,
    this.timestamp,
  });

  factory ComplaintStatusUpdate.fromJson(Map<String, dynamic> json) {
    return ComplaintStatusUpdate(
      complaintId: json['complaint_id'] as String,
      status: json['status'] as String,
      damageType: json['damage_type'] as String?,
      confidence: json['confidence'] != null ? (json['confidence'] as num).toDouble() : null,
      timestamp: json['timestamp'] as String?,
    );
  }
}
