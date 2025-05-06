import 'dart:async';
import 'dart:math';
import 'dart:typed_data';
import 'dart:io';
import 'package:record/record.dart';
import 'package:audio_session/audio_session.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:path_provider/path_provider.dart';
import '../services/settings_service.dart';
import '../models/app_settings.dart';

class AudioService {
  late final AudioRecorder _audioRecorder;
  final StreamController<File> _audioFileController = StreamController<File>.broadcast();
  Stream<File> get audioFileStream => _audioFileController.stream;
  
  // Stream controller for recording status updates (seconds remaining)
  final StreamController<int> _recordingStatusController = StreamController<int>.broadcast();
  Stream<int> get recordingStatusStream => _recordingStatusController.stream;
  
  // Stream controller for audio level updates
  final StreamController<double> _audioLevelController = StreamController<double>.broadcast();
  Stream<double> get audioLevelStream => _audioLevelController.stream;
  
  final SettingsService _settingsService = SettingsService();
  bool _isRecorderInitialized = false;
  bool get isRecording => _isRecording;
  bool _isRecording = false;
  Timer? _recordingTimer;
  Timer? _autoRecordingTimer;
  Timer? _audioLevelTimer;
  
  // For RMS (Root Mean Square) audio level calculation
  List<double> _audioLevels = [];
  double _maxObservedLevel = 0.1; // Start with a reasonable initial value
  double _currentAudioLevel = 0.0;
  bool _isSilent = false;
  
  // Recording duration in seconds
  static const int recordingDurationSeconds = 5;
  
  AudioService() {
    _audioRecorder = AudioRecorder();
  }
  
  Future<void> init() async {
    final status = await Permission.microphone.request();
    if (status != PermissionStatus.granted) {
      throw Exception('Mikrofonıerişim izni verilmedi');
    }

    // Configure audio session
    final session = await AudioSession.instance;
    await session.configure(const AudioSessionConfiguration(
      avAudioSessionCategory: AVAudioSessionCategory.record,
      avAudioSessionCategoryOptions: AVAudioSessionCategoryOptions.allowBluetooth,
      avAudioSessionMode: AVAudioSessionMode.measurement,
      avAudioSessionRouteSharingPolicy: AVAudioSessionRouteSharingPolicy.defaultPolicy,
      avAudioSessionSetActiveOptions: AVAudioSessionSetActiveOptions.none,
      androidAudioAttributes: AndroidAudioAttributes(
        contentType: AndroidAudioContentType.speech,
        flags: AndroidAudioFlags.none,
        usage: AndroidAudioUsage.voiceCommunication,
      ),
      androidAudioFocusGainType: AndroidAudioFocusGainType.gain,
      androidWillPauseWhenDucked: true,
    ));

    _isRecorderInitialized = true;
  }

  Future<void> startContinuousRecording() async {
    if (!_isRecorderInitialized) {
      await init();
    }
    
    // Start the first recording immediately
    await startRecording();
    
    // Setup timer to periodically record
    _autoRecordingTimer = Timer.periodic(
      const Duration(seconds: recordingDurationSeconds + 1), // Add 1 second gap between recordings
      (timer) async {
        if (!_isRecording) {
          await startRecording();
        }
      }
    );
  }
  
  Future<void> stopContinuousRecording() async {
    _autoRecordingTimer?.cancel();
    _autoRecordingTimer = null;
    _stopAudioLevelMonitoring();
    await stopRecording();
  }

  Future<void> startRecording() async {
    if (!_isRecorderInitialized) {
      await init();
    }
    
    if (_isRecording) {
      return; // Don't start if already recording
    }
    
    // Reset audio levels for new recording
    _audioLevels = [];
    _currentAudioLevel = 0.0;
    _isSilent = false;
    
    // Create a temporary file path for the recording
    final tempDir = await getTemporaryDirectory();
    final tempPath = '${tempDir.path}/temp_audio_${DateTime.now().millisecondsSinceEpoch}.wav';
    
    // Start actual recording
    await _audioRecorder.start(
      RecordConfig(
        encoder: AudioEncoder.wav,    // Use WAV format for API compatibility
        bitRate: 128000,
        sampleRate: 16000,
        numChannels: 1,
      ),
      path: tempPath,
    );
    
    _isRecording = true;
    
    // Start monitoring audio levels
    _startAudioLevelMonitoring();
    
    // Start a countdown timer for 5 seconds
    int secondsRemaining = recordingDurationSeconds;
    _recordingStatusController.add(secondsRemaining);
    
    _recordingTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      secondsRemaining--;
      _recordingStatusController.add(secondsRemaining);
      
      if (secondsRemaining <= 0) {
        // Recording complete
        _finishRecording(tempPath);
      }
    });
  }

  void _startAudioLevelMonitoring() {
    // Check audio levels 10 times per second
    _audioLevelTimer = Timer.periodic(
      const Duration(milliseconds: 100), 
      (timer) async {
        if (_isRecording) {
          try {
            final amplitude = await _audioRecorder.getAmplitude();
            final level = amplitude.current;
            
            // Update max observed level (for normalization)
            if (level > _maxObservedLevel && level < 1.0) {
              _maxObservedLevel = level;
            }
            
            // Normalize level between 0 and 1
            final normalizedLevel = level / max(_maxObservedLevel, 0.1);
            _currentAudioLevel = normalizedLevel;
            
            // Add to levels history for RMS calculation
            _audioLevels.add(normalizedLevel);
            if (_audioLevels.length > 30) { // Keep last 3 seconds (at 10 samples/sec)
              _audioLevels.removeAt(0);
            }
            
            // Notify listeners
            _audioLevelController.add(normalizedLevel);
            
            // Check against microphone threshold
            final settings = _settingsService.currentSettings;
            final thresholdLevel = settings.microphoneThreshold;
            
            // Set silent flag if audio level is below threshold
            _isSilent = normalizedLevel < thresholdLevel;
          } catch (e) {
            print('Error getting audio level: $e');
          }
        }
      }
    );
  }
  
  void _stopAudioLevelMonitoring() {
    _audioLevelTimer?.cancel();
    _audioLevelTimer = null;
  }

  Future<void> _finishRecording(String filePath) async {
    if (!_isRecording) return;
    
    _recordingTimer?.cancel();
    _recordingTimer = null;
    _stopAudioLevelMonitoring();
    
    // Stop the actual recording
    final path = await _audioRecorder.stop();
    _isRecording = false;
    
    if (path != null) {
      final audioFile = File(path);
      if (await audioFile.exists()) {
        // Calculate RMS (Root Mean Square) of audio levels during recording
        double rmsLevel = 0;
        if (_audioLevels.isNotEmpty) {
          final sumSquares = _audioLevels.fold(0.0, (sum, level) => sum + (level * level));
          rmsLevel = sqrt(sumSquares / _audioLevels.length);
        }
        
        // Get current microphone threshold
        final settings = _settingsService.currentSettings;
        final thresholdLevel = settings.microphoneThreshold;
        
        // Only process if RMS level is above threshold (skip silent recordings)
        if (rmsLevel >= thresholdLevel) {
          // Send the audio file through the stream
          _audioFileController.add(audioFile);
        } else {
          print('Audio level below threshold (${(rmsLevel * 100).toStringAsFixed(1)}% < ${(thresholdLevel * 100).toStringAsFixed(1)}%), skipping processing');
          
          // Delete the file since we're not using it
          try {
            await audioFile.delete();
          } catch (e) {
            print('Error deleting silent audio file: $e');
          }
        }
      }
    }
  }

  Future<void> stopRecording() async {
    // Cancel the timer if it's running
    _recordingTimer?.cancel();
    _recordingTimer = null;
    _stopAudioLevelMonitoring();
    
    if (!_isRecorderInitialized || !_isRecording) return;
    
    await _audioRecorder.stop();
    _isRecording = false;
  }

  Future<void> dispose() async {
    _audioLevelTimer?.cancel();
    _autoRecordingTimer?.cancel();
    _recordingTimer?.cancel();
    await stopRecording();
    await _audioFileController.close();
    await _recordingStatusController.close();
    await _audioLevelController.close();
    _audioRecorder.dispose();
  }
}
