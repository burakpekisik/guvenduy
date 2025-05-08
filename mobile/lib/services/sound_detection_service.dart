import 'dart:async';
import 'dart:io';
import '../models/sound_detection_result.dart';
import 'api_service.dart';
import 'evaluation_service.dart';

class SoundDetectionService {
  final _detectionController = StreamController<SoundDetectionResult>.broadcast();
  Stream<SoundDetectionResult> get detectionStream => _detectionController.stream;
  
  final ApiService _apiService = ApiService();
  final EvaluationService _evaluationService = EvaluationService();
  StreamSubscription? _audioSubscription;
  bool _isDetecting = false;
  bool _isProcessing = false;  // Flag to track processing state
  String? _authToken;

  Future<bool> checkApiConnection() async {
    return await _apiService.checkHealth();
  }

  // Token eklemek için yeni metot
  void setAuthToken(String token) {
    _authToken = token;
    _apiService.setAuthToken(token);
  }

  void startDetection(Stream<File> audioFileStream) {
    if (_isDetecting) return;
    _isDetecting = true;
    _isProcessing = false;
    
    // Process the audio files sent by the AudioService
    _audioSubscription = audioFileStream.listen((audioFile) async {
      if (!_isProcessing) {
        _isProcessing = true;
        
        // Let UI know we're processing
        _detectionController.add(SoundDetectionResult(
          soundType: 'processing',
          confidence: 0.0,
          timestamp: DateTime.now(),
        ));
        
        // Send the file to API for processing
        try {
          // Get the file name for tracking purposes
          final fileName = audioFile.path.split('/').last;
          
          // Get detection result from API
          final result = await _apiService.detectSound(audioFile);
          
          // Create a new result with the recording file name
          final resultWithFileName = SoundDetectionResult(
            soundType: result.soundType,
            originalSoundType: result.originalSoundType,
            confidence: result.confidence,
            timestamp: result.timestamp,
            error: result.error,
            allPredictions: result.allPredictions,
            recordingFileName: fileName,
          );
          
          // Add to evaluation service for potential evaluation by user
          _evaluationService.addDetectionResult(resultWithFileName);
          
          // Send to UI
          _detectionController.add(resultWithFileName);
        } catch (e) {
          _detectionController.add(SoundDetectionResult(
            soundType: 'error',
            confidence: 0.0,
            timestamp: DateTime.now(),
            error: e.toString(),
          ));
        } finally {
          _isProcessing = false;
          
          // Clean up the temporary file
          try {
            if (await audioFile.exists()) {
              await audioFile.delete();
            }
          } catch (e) {
            print('Error deleting audio file: $e');
          }
        }
      }
    });
  }
  
  // Initialize recent detection results
  Future<void> init() async {
    await _evaluationService.loadPreviousResults();
  }

  void stopDetection() {
    _isDetecting = false;
    _audioSubscription?.cancel();
    _audioSubscription = null;
  }

  void dispose() {
    stopDetection();
    _detectionController.close();
  }
}
