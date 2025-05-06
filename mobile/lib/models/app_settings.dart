class AppSettings {
  final double detectionThreshold;
  final double microphoneThreshold;
  final bool filterLowConfidence;
  final bool showAllPredictions;

  const AppSettings({
    this.detectionThreshold = 0.2, // Default threshold value (20%)
    this.microphoneThreshold = 0.1, // Default microphone threshold (10%)
    this.filterLowConfidence = true,
    this.showAllPredictions = false,
  });

  // Copy with method for immutability
  AppSettings copyWith({
    double? detectionThreshold,
    double? microphoneThreshold,
    bool? filterLowConfidence,
    bool? showAllPredictions,
  }) {
    return AppSettings(
      detectionThreshold: detectionThreshold ?? this.detectionThreshold,
      microphoneThreshold: microphoneThreshold ?? this.microphoneThreshold,
      filterLowConfidence: filterLowConfidence ?? this.filterLowConfidence,
      showAllPredictions: showAllPredictions ?? this.showAllPredictions,
    );
  }
}