import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_dotenv/flutter_dotenv.dart';
import '../models/sound_detection_result.dart';
import '../services/settings_service.dart';
import '../models/sound_detection_evaluation.dart';

class ApiService {
  final String baseUrl;
  final String predictEndpoint;
  final String healthEndpoint;
  final String evaluationsEndpoint;
  final SettingsService _settingsService = SettingsService();
  String? _authToken;
  
  ApiService({
    String? baseUrl,
    String? predictEndpoint,
    String? healthEndpoint,
    String? evaluationsEndpoint,
  }) : 
    baseUrl = baseUrl ?? dotenv.env['API_BASE_URL'] ?? 'http://10.0.2.2:8000',
    predictEndpoint = predictEndpoint ?? dotenv.env['API_PREDICT_ENDPOINT'] ?? '/audio/predict',
    healthEndpoint = healthEndpoint ?? dotenv.env['API_HEALTH_ENDPOINT'] ?? '/health',
    evaluationsEndpoint = evaluationsEndpoint ?? dotenv.env['API_EVALUATIONS_ENDPOINT'] ?? '/evaluations/';
  
  // Token eklemek için yeni metot
  void setAuthToken(String token) {
    _authToken = token;
  }
  
  // Header oluşturma yardımcı metodu
  Map<String, String> _getHeaders({Map<String, String>? additionalHeaders}) {
    Map<String, String> headers = additionalHeaders ?? {};
    
    // Token varsa Authorization header'ı ekle
    if (_authToken != null) {
      headers['Authorization'] = 'Bearer $_authToken';
    }
    
    return headers;
  }

  Future<bool> checkHealth() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl$healthEndpoint'),
        headers: _getHeaders(),
      ).timeout(const Duration(seconds: 5));
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['status'] == 'ok';
      }
      return false;
    } catch (e) {
      print('Health check failed: $e');
      return false;
    }
  }

  Future<SoundDetectionResult> detectSound(File audioFile) async {
    try {
      // Create multipart request
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl$predictEndpoint'),
      );

      // Add file to request
      request.files.add(
        await http.MultipartFile.fromPath(
          'file',
          audioFile.path,
        ),
      );
      
      // Add auth headers if token exists
      if (_authToken != null) {
        request.headers['Authorization'] = 'Bearer $_authToken';
      }

      // Send request
      final streamedResponse = await request.send()
          .timeout(const Duration(seconds: 10));
      
      // Get response
      final response = await http.Response.fromStream(streamedResponse);
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data.containsKey('predictions')) {
          final predictions = data['predictions'] as Map<String, dynamic>;
          
          // Find highest confidence prediction
          String topClass = '';
          double topConfidence = 0;
          
          // Get current threshold from settings
          final settings = _settingsService.currentSettings;
          final threshold = settings.detectionThreshold;
          
          predictions.forEach((key, value) {
            final confidence = value as double;
            // Reset all predictions below threshold to 0 if enabled
            if (settings.filterLowConfidence && confidence < threshold) {
              predictions[key] = 0.0;
            }
            
            if (confidence > topConfidence) {
              topConfidence = confidence;
              topClass = key;
            }
          });
          
          // Check if the confidence is below the threshold
          if (topConfidence < threshold) {
            if (settings.filterLowConfidence) {
              // If filtering is on, return unknown with original detection stored
              return SoundDetectionResult(
                soundType: 'unknown',
                originalSoundType: topClass, // Store original detection
                confidence: topConfidence,
                timestamp: DateTime.now(),
                allPredictions: settings.showAllPredictions ? predictions : null,
              );
            } else if (topConfidence == 0) {
              // If all confidences are 0, return unknown
              return SoundDetectionResult(
                soundType: 'unknown',
                confidence: 0.0,
                timestamp: DateTime.now(),
                allPredictions: settings.showAllPredictions ? predictions : null,
              );
            }
          }
          
          return SoundDetectionResult(
            soundType: topClass,
            confidence: topConfidence,
            timestamp: DateTime.now(),
            allPredictions: settings.showAllPredictions ? predictions : null,
          );
        }
      }
      
      // Return error result if something went wrong
      return SoundDetectionResult(
        soundType: 'unknown',
        confidence: 0.0,
        timestamp: DateTime.now(),
        error: 'API error: ${response.statusCode} ${response.reasonPhrase}',
      );
    } catch (e) {
      print('API error: $e');
      return SoundDetectionResult(
        soundType: 'unknown',
        confidence: 0.0,
        timestamp: DateTime.now(),
        error: 'Request failed: $e',
      );
    }
  }

  Future<bool> submitEvaluation(SoundDetectionEvaluation evaluation) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl$evaluationsEndpoint'),
        headers: _getHeaders(additionalHeaders: {
          'Content-Type': 'application/json',
        }),
        body: jsonEncode(evaluation.toJson()),
      ).timeout(const Duration(seconds: 5));
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['status'] == 'success';
      }
      
      print('Error submitting evaluation: ${response.statusCode} ${response.reasonPhrase}');
      return false;
    } catch (e) {
      print('Failed to submit evaluation: $e');
      return false;
    }
  }
}
