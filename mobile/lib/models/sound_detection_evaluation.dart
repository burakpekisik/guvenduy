class SoundDetectionEvaluation {
  final String deviceId;
  final DateTime recordingDate;
  final String recordingName;
  final String detectionClass;
  final double detectionConfidence;
  final bool success;

  SoundDetectionEvaluation({
    required this.deviceId,
    required this.recordingDate,
    required this.recordingName,
    required this.detectionClass,
    required this.detectionConfidence,
    required this.success,
  });

  // Convert to JSON for API request
  Map<String, dynamic> toJson() {
    return {
      'device_id': deviceId,
      'recording_date': recordingDate.toIso8601String(),
      'recording_name': recordingName,
      'detection_class': detectionClass,
      'detection_confidence': detectionConfidence,
      'success': success,
    };
  }
}