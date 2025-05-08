import 'dart:async';
import 'dart:convert';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import '../models/sound_detection_result.dart';
import '../models/sound_detection_evaluation.dart';
import '../services/api_service.dart';

class EvaluationService {
  final ApiService _apiService = ApiService();
  final DeviceInfoPlugin _deviceInfo = DeviceInfoPlugin();
  static const int _maxStoredResults = 100;
  String? _authToken;
  
  // Stream for evaluation status updates
  final _evaluationStatusController = StreamController<String>.broadcast();
  Stream<String> get evaluationStatusStream => _evaluationStatusController.stream;
  
  // Stored results for evaluation
  final List<SoundDetectionResult> _recentResults = [];
  List<SoundDetectionResult> get recentResults => List.unmodifiable(_recentResults);
  
  // Singleton pattern
  static final EvaluationService _instance = EvaluationService._internal();
  factory EvaluationService() => _instance;
  EvaluationService._internal();
  
  // Token eklemek için yeni metot
  void setAuthToken(String token) {
    _authToken = token;
    _apiService.setAuthToken(token);
  }
  
  // Add a detection result to the recent results list
  void addDetectionResult(SoundDetectionResult result) {
    // Insert at the beginning of the list
    _recentResults.insert(0, result);
    
    // Keep only the latest 100 results
    if (_recentResults.length > _maxStoredResults) {
      _recentResults.removeLast();
    }
    
    // Save results to shared preferences
    _saveRecentResults();
  }
  
  // Load previously stored detection results
  Future<void> loadPreviousResults() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final jsonString = prefs.getString('recent_detection_results');
      
      if (jsonString != null) {
        final List<dynamic> jsonList = jsonDecode(jsonString);
        
        // Clear existing list
        _recentResults.clear();
        
        // Add all loaded results
        for (var json in jsonList) {
          try {
            final result = SoundDetectionResult(
              soundType: json['soundType'],
              originalSoundType: json['originalSoundType'],
              confidence: json['confidence'],
              timestamp: DateTime.parse(json['timestamp']),
              recordingFileName: json['recordingFileName'] ?? '',
              allPredictions: json['allPredictions'],
            );
            _recentResults.add(result);
          } catch (e) {
            print('Error parsing result: $e');
          }
        }
        
        print('Loaded ${_recentResults.length} previous detection results');
      }
    } catch (e) {
      print('Error loading previous results: $e');
    }
  }
  
  // Save recent results to shared preferences
  Future<void> _saveRecentResults() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      
      final jsonList = _recentResults.map((result) => {
        'soundType': result.soundType,
        'originalSoundType': result.originalSoundType,
        'confidence': result.confidence,
        'timestamp': result.timestamp.toIso8601String(),
        'recordingFileName': result.recordingFileName,
        'allPredictions': result.allPredictions,
      }).toList();
      
      await prefs.setString('recent_detection_results', jsonEncode(jsonList));
    } catch (e) {
      print('Error saving recent results: $e');
    }
  }
  
  // Get a unique device identifier (anonymized)
  Future<String> _getDeviceId() async {
    try {
      // Try to get a stored device ID first
      final prefs = await SharedPreferences.getInstance();
      String? deviceId = prefs.getString('device_id');
      
      if (deviceId == null) {
        // If no device ID is stored, generate a UUID
        deviceId = const Uuid().v4();
        // Store it for future use
        await prefs.setString('device_id', deviceId);
        print('Generated and stored new device ID: $deviceId');
      }
      
      return deviceId;
    } catch (e) {
      // If anything fails, generate a random UUID
      print('Error getting device ID: $e');
      return const Uuid().v4();
    }
  }
  
  // Submit an evaluation for a detection result
  Future<bool> submitEvaluation(SoundDetectionResult result, bool success) async {
    try {
      _evaluationStatusController.add('Submitting evaluation...');
      final deviceId = await _getDeviceId();
      
      // Create evaluation object
      final evaluation = SoundDetectionEvaluation(
        deviceId: deviceId,
        recordingDate: result.timestamp,
        recordingName: result.recordingFileName,
        detectionClass: result.isLowConfidence ? result.originalSoundType! : result.soundType,
        detectionConfidence: result.confidence,
        success: success,
      );
      
      // Submit to API
      final submitted = await _apiService.submitEvaluation(evaluation);
      
      if (submitted) {
        _evaluationStatusController.add('Evaluation submitted successfully');
      } else {
        _evaluationStatusController.add('Failed to submit evaluation');
      }
      
      return submitted;
    } catch (e) {
      print('Error submitting evaluation: $e');
      _evaluationStatusController.add('Error: $e');
      return false;
    }
  }
  
  void dispose() {
    _evaluationStatusController.close();
  }
}