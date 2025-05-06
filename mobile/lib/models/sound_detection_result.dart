class SoundDetectionResult {
  final String soundType;
  final String? originalSoundType; // Added to store original detection when below threshold
  final double confidence;
  final DateTime timestamp;
  final String? error;
  final Map<String, dynamic>? allPredictions;
  final String recordingFileName; // Added for evaluations

  SoundDetectionResult({
    required this.soundType,
    this.originalSoundType,
    required this.confidence,
    required this.timestamp,
    this.error,
    this.allPredictions,
    this.recordingFileName = '', // Default value
  });

  bool get hasError => error != null;
  
  // Helper to check if this was a low confidence result
  bool get isLowConfidence => 
      soundType == 'unknown' && originalSoundType != null;

  @override
  String toString() {
    if (hasError) {
      return 'Error: $error';
    }
    
    if (isLowConfidence) {
      return 'Unknown (Low confidence: $originalSoundType ${(confidence * 100).toStringAsFixed(1)}%)';
    }
    
    return '$soundType (${(confidence * 100).toStringAsFixed(1)}%)';
  }
}
