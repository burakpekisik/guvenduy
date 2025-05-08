import 'dart:async';
import 'package:flutter/material.dart';
import '../models/sound_detection_result.dart';
import '../services/audio_service.dart';
import '../services/sound_detection_service.dart';
import '../services/settings_service.dart';
import '../services/evaluation_service.dart';
import '../services/auth_service.dart';
import '../models/app_settings.dart';
import '../screens/settings_screen.dart';
import '../widgets/swipeable_detection_tile.dart';

class SoundDetectionScreen extends StatefulWidget {
  const SoundDetectionScreen({super.key});

  @override
  State<SoundDetectionScreen> createState() => _SoundDetectionScreenState();
}

class _SoundDetectionScreenState extends State<SoundDetectionScreen> with SingleTickerProviderStateMixin {
  final AudioService _audioService = AudioService();
  final SoundDetectionService _detectionService = SoundDetectionService();
  final EvaluationService _evaluationService = EvaluationService();
  final AuthService _authService = AuthService();
  
  late TabController _tabController;
  bool _isListening = false;
  bool _isProcessing = false;
  bool _apiConnected = false;
  int _secondsRemaining = 0;
  final List<SoundDetectionResult> _detectionResults = [];
  String? _currentError;
  String? _evaluationStatus;
  StreamSubscription? _recordingStatusSubscription;
  StreamSubscription? _evaluationStatusSubscription;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _setupServices();
    _setupStreams();
    _checkApiConnection();
  }
  
  Future<void> _setupServices() async {
    await _audioService.init();
    await _detectionService.init();
    
    // Get auth token and add it to services that make API calls
    final String? token = await _authService.getToken();
    if (token != null) {
      _detectionService.setAuthToken(token);
      _evaluationService.setAuthToken(token);
    }
    
    await _evaluationService.loadPreviousResults();
  }
  
  void _setupStreams() {
    _setupDetectionStream();
    _setupRecordingStatusStream();
    _setupEvaluationStatusStream();
  }
  
  void _setupEvaluationStatusStream() {
    _evaluationStatusSubscription = _evaluationService.evaluationStatusStream.listen((status) {
      setState(() {
        _evaluationStatus = status;
      });
    });
  }
  
  Future<void> _checkApiConnection() async {
    final isConnected = await _detectionService.checkApiConnection();
    setState(() {
      _apiConnected = isConnected;
      if (!isConnected) {
        _currentError = 'Cannot connect to API. Please check your connection.';
      }
    });
  }
  
  void _setupRecordingStatusStream() {
    _recordingStatusSubscription = _audioService.recordingStatusStream.listen((seconds) {
      setState(() {
        _secondsRemaining = seconds;
      });
    });
  }

  void _setupDetectionStream() {
    _detectionService.detectionStream.listen((result) {
      setState(() {
        if (result.soundType == 'processing') {
          _isProcessing = true;
          return;
        }
        
        _isProcessing = false;
        
        // Check if result has an error
        if (result.hasError) {
          _currentError = result.error;
        } else {
          _currentError = null;
          _detectionResults.add(result);
          // Keep last 10 results only (for the live tab)
          if (_detectionResults.length > 10) {
            _detectionResults.removeAt(0);
          }
        }
      });
    });
  }

  Future<void> _startContinuousListening() async {
    if (_isListening) return;
    
    setState(() {
      _isListening = true;
      _currentError = null; // Clear any previous errors
      _isProcessing = false; // Reset processing state
    });
    
    // Start the detection service first
    _detectionService.startDetection(_audioService.audioFileStream);
    
    try {
      // Then start continuous recording
      await _audioService.startContinuousRecording();
    } catch (e) {
      setState(() {
        _isListening = false;
        _currentError = 'Failed to start recording: $e';
      });
      _detectionService.stopDetection();
    }
  }
  
  Future<void> _stopContinuousListening() async {
    setState(() {
      _isListening = false;
    });
    
    await _audioService.stopContinuousRecording();
    _detectionService.stopDetection();
  }
  
  void _refreshUI() {
    // Force a UI refresh
    setState(() {});
  }

  @override
  void dispose() {
    _recordingStatusSubscription?.cancel();
    _evaluationStatusSubscription?.cancel();
    _tabController.dispose();
    _audioService.dispose();
    _detectionService.dispose();
    _evaluationService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return WillPopScope(
      onWillPop: () async {
        // Eğer kayıt yapılıyorsa, kullanıcı geri tuşuna bastığında kayıt durdurulsun
        if (_isListening) {
          await _stopContinuousListening();
          return false; // Sayfanın kapatılmasını engelle
        }
        return true; // Sayfanın kapatılmasına izin ver
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Ses Tanıma'),
          backgroundColor: Theme.of(context).colorScheme.inversePrimary,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () async {
              // Eğer kayıt yapılıyorsa, önce kaydı durdur
              if (_isListening) {
                await _stopContinuousListening();
              }
              if (!mounted) return;
              Navigator.pop(context); // Geri dön
            },
          ),
          actions: [
            IconButton(
              icon: const Icon(Icons.settings),
              tooltip: 'Ayarlar',
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (context) => const SettingsScreen()),
                );
              },
            ),
          ],
          bottom: TabBar(
            controller: _tabController,
            tabs: const [
              Tab(text: 'Canlı'),
              Tab(text: 'Geçmiş'),
            ],
          ),
        ),
        body: TabBarView(
          controller: _tabController,
          children: [
            _buildLiveTab(),
            _buildHistoryTab(),
          ],
        ),
        floatingActionButton: _tabController.index == 0 ? FloatingActionButton.extended(
          onPressed: _isListening ? _stopContinuousListening : _apiConnected ? _startContinuousListening : null,
          backgroundColor: _isListening ? Colors.red : Colors.green,
          icon: Icon(_isListening ? Icons.stop : Icons.hearing),
          label: Text(_isListening ? 'Durdur' : 'Dinle'),
        ) : null,
        floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      ),
    );
  }
  
  Widget _buildLiveTab() {
    return Column(
      children: [
        // API connection status
        Container(
          padding: const EdgeInsets.all(8),
          margin: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: _apiConnected ? Colors.green.shade100 : Colors.red.shade100,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: _apiConnected ? Colors.green : Colors.red),
          ),
          child: Row(
            children: [
              Icon(
                _apiConnected ? Icons.cloud_done : Icons.cloud_off,
                color: _apiConnected ? Colors.green : Colors.red,
              ),
              const SizedBox(width: 8),
              Text(
                _apiConnected ? 'API Bağlı' : 'API Bağlı Değil',
                style: TextStyle(
                  color: _apiConnected ? Colors.green : Colors.red,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.refresh),
                onPressed: _checkApiConnection,
                tooltip: 'Bağlantıyı kontrol et',
              ),
            ],
          ),
        ),
        
        // Recording status indicator
        if (_isListening)
          Container(
            padding: const EdgeInsets.all(12),
            margin: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.blue.shade100,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.blue),
            ),
            child: Row(
              children: [
                const Icon(Icons.mic, color: Colors.blue),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Kayıt: $_secondsRemaining saniye kaldı',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ),
          
        // Processing indicator
        if (_isProcessing)
          Container(
            padding: const EdgeInsets.all(12),
            margin: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.amber.shade100,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.amber),
            ),
            child: Row(
              children: [
                const SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation<Color>(Colors.amber),
                  ),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Text(
                    'Ses işleniyor...',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ),
          
        // Evaluation status
        if (_evaluationStatus != null)
          Container(
            padding: const EdgeInsets.all(12),
            margin: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: _evaluationStatus!.contains('successfully')
                  ? Colors.green.shade100
                  : _evaluationStatus!.contains('Error') || _evaluationStatus!.contains('Failed')
                      ? Colors.red.shade100
                      : Colors.blue.shade100,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: _evaluationStatus!.contains('successfully')
                    ? Colors.green
                    : _evaluationStatus!.contains('Error') || _evaluationStatus!.contains('Failed')
                        ? Colors.red
                        : Colors.blue,
              ),
            ),
            child: Row(
              children: [
                Icon(
                  _evaluationStatus!.contains('successfully')
                      ? Icons.check_circle
                      : _evaluationStatus!.contains('Error') || _evaluationStatus!.contains('Failed')
                          ? Icons.error
                          : Icons.info,
                  color: _evaluationStatus!.contains('successfully')
                      ? Colors.green
                      : _evaluationStatus!.contains('Error') || _evaluationStatus!.contains('Failed')
                          ? Colors.red
                          : Colors.blue,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    _evaluationStatus!,
                    style: TextStyle(
                      color: _evaluationStatus!.contains('successfully')
                          ? Colors.green
                          : _evaluationStatus!.contains('Error') || _evaluationStatus!.contains('Failed')
                              ? Colors.red
                              : Colors.blue,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () {
                    setState(() {
                      _evaluationStatus = null;
                    });
                  },
                ),
              ],
            ),
          ),
          
        // Error display
        if (_currentError != null)
          Container(
            padding: const EdgeInsets.all(12),
            margin: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.red.shade100,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.red),
            ),
            child: Row(
              children: [
                const Icon(Icons.error, color: Colors.red),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    _currentError!,
                    style: const TextStyle(color: Colors.red),
                  ),
                ),
              ],
            ),
          ),
        
        // Results list
        Expanded(
          child: _detectionResults.isEmpty
              ? Center(
                  child: Text(
                    _currentError != null 
                        ? 'Bir hata oluştu. Lütfen kontrol edip tekrar deneyin.'
                        : 'Henüz ses algılanmadı.\nAnalize başlamak için Dinle butonuna basın.',
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 16),
                  ),
                )
              : ListView.builder(
                  itemCount: _detectionResults.length,
                  itemBuilder: (context, index) {
                    final result = _detectionResults[_detectionResults.length - 1 - index];
                    return SwipeableDetectionTile(
                      result: result,
                      onEvaluationSubmitted: _refreshUI,
                    );
                  },
                ),
        ),
        const Divider(),
        Padding(
          padding: const EdgeInsets.all(16.0),
          child: Text(
            _isListening
                ? 'Acil durum seslerini dinliyor...'
                : 'Sürekli algılamayı başlatmak için Dinle butonuna basın',
            style: const TextStyle(fontSize: 16),
          ),
        ),
      ],
    );
  }
  
  Widget _buildHistoryTab() {
    final recentResults = _evaluationService.recentResults;
    
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          alignment: Alignment.centerLeft,
          child: const Text(
            'Son Algılama Geçmişi',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        
        // Evaluation status
        if (_evaluationStatus != null)
          Container(
            padding: const EdgeInsets.all(12),
            margin: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              color: _evaluationStatus!.contains('successfully')
                  ? Colors.green.shade100
                  : _evaluationStatus!.contains('Error') || _evaluationStatus!.contains('Failed')
                      ? Colors.red.shade100
                      : Colors.blue.shade100,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: _evaluationStatus!.contains('successfully')
                    ? Colors.green
                    : _evaluationStatus!.contains('Error') || _evaluationStatus!.contains('Failed')
                        ? Colors.red
                        : Colors.blue,
              ),
            ),
            child: Row(
              children: [
                Icon(
                  _evaluationStatus!.contains('successfully')
                      ? Icons.check_circle
                      : _evaluationStatus!.contains('Error') || _evaluationStatus!.contains('Failed')
                          ? Icons.error
                          : Icons.info,
                  color: _evaluationStatus!.contains('successfully')
                      ? Colors.green
                      : _evaluationStatus!.contains('Error') || _evaluationStatus!.contains('Failed')
                          ? Colors.red
                          : Colors.blue,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    _evaluationStatus!,
                    style: TextStyle(
                      color: _evaluationStatus!.contains('successfully')
                          ? Colors.green
                          : _evaluationStatus!.contains('Error') || _evaluationStatus!.contains('Failed')
                              ? Colors.red
                              : Colors.blue,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () {
                    setState(() {
                      _evaluationStatus = null;
                    });
                  },
                ),
              ],
            ),
          ),
          
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
          child: Text(
            'Algılama doğruluğunu değerlendirmek için herhangi bir sonucu sola kaydırın. '
            'Geri bildiriminiz modelin iyileştirilmesine yardımcı olur.',
            style: TextStyle(
              fontStyle: FontStyle.italic,
            ),
          ),
        ),
        
        Expanded(
          child: recentResults.isEmpty
              ? const Center(
                  child: Text(
                    'Algılama geçmişi mevcut değil.\n'
                    'Geçmiş oluşturmak için algılamayı başlatın.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 16),
                  ),
                )
              : ListView.builder(
                  itemCount: recentResults.length,
                  itemBuilder: (context, index) {
                    return SwipeableDetectionTile(
                      result: recentResults[index],
                      onEvaluationSubmitted: _refreshUI,
                    );
                  },
                ),
        ),
      ],
    );
  }
}
