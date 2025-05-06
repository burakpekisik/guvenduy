import 'dart:async';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/app_settings.dart';

class SettingsService {
  // Stream controller for broadcasting settings changes
  final _settingsController = StreamController<AppSettings>.broadcast();
  Stream<AppSettings> get settingsStream => _settingsController.stream;
  
  // Current settings (cached)
  AppSettings _currentSettings = const AppSettings();
  AppSettings get currentSettings => _currentSettings;
  
  // Keys for SharedPreferences
  static const String _thresholdKey = 'detection_threshold';
  static const String _microphoneThresholdKey = 'microphone_threshold';
  static const String _filterLowConfidenceKey = 'filter_low_confidence';
  static const String _showAllPredictionsKey = 'show_all_predictions';
  
  // Singleton pattern
  static final SettingsService _instance = SettingsService._internal();
  factory SettingsService() => _instance;
  SettingsService._internal();
  
  // Initialize settings from SharedPreferences
  Future<void> init() async {
    await loadSettings();
  }
  
  // Load settings from persistent storage
  Future<void> loadSettings() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      
      final threshold = prefs.getDouble(_thresholdKey) ?? 0.2; // Default 20%
      final microphoneThreshold = prefs.getDouble(_microphoneThresholdKey) ?? 0.1; // Default 10%
      final filterLowConfidence = prefs.getBool(_filterLowConfidenceKey) ?? true;
      final showAllPredictions = prefs.getBool(_showAllPredictionsKey) ?? false;
      
      _currentSettings = AppSettings(
        detectionThreshold: threshold,
        microphoneThreshold: microphoneThreshold,
        filterLowConfidence: filterLowConfidence,
        showAllPredictions: showAllPredictions,
      );
      
      // Broadcast new settings
      _settingsController.add(_currentSettings);
    } catch (e) {
      print('Error loading settings: $e');
    }
  }
  
  // Save settings to persistent storage
  Future<void> saveSettings(AppSettings settings) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      
      await prefs.setDouble(_thresholdKey, settings.detectionThreshold);
      await prefs.setDouble(_microphoneThresholdKey, settings.microphoneThreshold);
      await prefs.setBool(_filterLowConfidenceKey, settings.filterLowConfidence);
      await prefs.setBool(_showAllPredictionsKey, settings.showAllPredictions);
      
      _currentSettings = settings;
      
      // Broadcast new settings
      _settingsController.add(_currentSettings);
    } catch (e) {
      print('Error saving settings: $e');
    }
  }
  
  // Update detection threshold
  Future<void> updateDetectionThreshold(double threshold) async {
    final newSettings = _currentSettings.copyWith(detectionThreshold: threshold);
    await saveSettings(newSettings);
  }
  
  // Update microphone threshold
  Future<void> updateMicrophoneThreshold(double threshold) async {
    final newSettings = _currentSettings.copyWith(microphoneThreshold: threshold);
    await saveSettings(newSettings);
  }
  
  // Update filter low confidence setting
  Future<void> updateFilterLowConfidence(bool filter) async {
    final newSettings = _currentSettings.copyWith(filterLowConfidence: filter);
    await saveSettings(newSettings);
  }
  
  // Update show all predictions setting
  Future<void> updateShowAllPredictions(bool show) async {
    final newSettings = _currentSettings.copyWith(showAllPredictions: show);
    await saveSettings(newSettings);
  }
  
  void dispose() {
    _settingsController.close();
  }
}