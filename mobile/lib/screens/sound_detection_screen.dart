import 'dart:async';
import 'package:flutter/material.dart';
import '../models/sound_detection_result.dart';
import '../services/audio_service.dart';
import '../services/sound_detection_service.dart';
import '../services/settings_service.dart';
import '../services/evaluation_service.dart';
import '../services/auth_service.dart';
import '../services/alerts_service.dart';
import '../services/location_service.dart';
import '../models/app_settings.dart';
import '../screens/settings_screen.dart';
import '../screens/alerts_map_screen.dart';
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
  final AlertsService _alertsService = AlertsService();
  final LocationService _locationService = LocationService();
  
  late TabController _tabController;
  bool _isListening = false;
  bool _isProcessing = false;
  bool _apiConnected = false;
  int _secondsRemaining = 0;
  
  double _currentAudioLevel = 0.0;
  double _maxAudioLevel = 0.0;
  double _minThreshold = 0.1;
  
  late List<SoundDetectionResult> _detectionResults = [];
  List<SoundDetectionResult> _savedResults = [];
  String? _currentError;
  bool _isLoggedIn = false;
  bool _locationInitialized = false;
  
  StreamSubscription? _detectionSubscription;
  StreamSubscription? _recordingStatusSubscription;
  StreamSubscription? _evaluationStatusSubscription;
  StreamSubscription? _audioLevelSubscription;
  
  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _checkApiConnection();
    _checkLoginStatus();
    _setupStreams();
    _initializeLocation();
    _initializeAlertSystem();
  }

  Future<void> _initializeAlertSystem() async {
    final token = await _authService.getToken();
    _alertsService.setAuthToken(token);
    _alertsService.startPeriodicClassRefresh();
  }
  
  Future<void> _initializeLocation() async {
    try {
      final locationInitialized = await _locationService.initLocationService();
      setState(() {
        _locationInitialized = locationInitialized;
      });
      
      if (locationInitialized) {
        _locationService.startLocationUpdates();
      }
    } catch (e) {
      print('Error initializing location: $e');
      setState(() {
        _locationInitialized = false;
      });
    }
  }
  
  @override
  void dispose() {
    _detectionSubscription?.cancel();
    _recordingStatusSubscription?.cancel();
    _evaluationStatusSubscription?.cancel();
    _audioLevelSubscription?.cancel();
    _tabController.dispose();
    _alertsService.stopPeriodicClassRefresh();
    _locationService.stopLocationUpdates();
    super.dispose();
  }
  
  Future<void> _checkLoginStatus() async {
    final isLoggedIn = await _authService.isLoggedIn();
    setState(() {
      _isLoggedIn = isLoggedIn;
    });
    
    final token = await _authService.getToken();
    
    if (token != null) {
      _detectionService.setAuthToken(token);
      _evaluationService.setAuthToken(token);
      _alertsService.setAuthToken(token);
    } else {
      _detectionService.setAuthToken("");
      _evaluationService.setAuthToken("");
      _alertsService.setAuthToken("");
    }
    
    await _evaluationService.loadPreviousResults();
  }
  
  void _setupStreams() {
    _setupDetectionStream();
    _setupRecordingStatusStream();
    _setupEvaluationStatusStream();
    _setupAudioLevelStream();
  }
  
  void _setupEvaluationStatusStream() {
    _evaluationStatusSubscription = _evaluationService.evaluationStatusStream.listen((status) {
      setState(() {});
    });
  }
  
  void _setupAudioLevelStream() {
    _audioLevelSubscription = _audioService.audioLevelStream.listen((level) {
      setState(() {
        _currentAudioLevel = level;
        if (level > _maxAudioLevel) {
          _maxAudioLevel = level;
        }
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
    _detectionSubscription = _detectionService.detectionResultStream.listen(
      (result) {
        setState(() {
          _detectionResults.insert(0, result);
          _isProcessing = false;
        });
      },
      onError: (e) {
        setState(() {
          _isProcessing = false;
          _currentError = 'Error processing audio: $e';
        });
      }
    );
  }
  
  void _startContinuousListening() async {
    try {
      final settings = SettingsService().currentSettings;
      _minThreshold = settings.microphoneThreshold;
      
      await _audioService.startContinuousRecording();
      setState(() {
        _isListening = true;
        _currentError = null;
      });
    } catch (e) {
      setState(() {
        _currentError = 'Error starting recording: $e';
      });
    }
  }
  
  void _stopContinuousListening() async {
    await _audioService.stopRecording();
    setState(() {
      _isListening = false;
      _maxAudioLevel = 0;
    });
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ses Tanıma'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          IconButton(
            icon: const Icon(Icons.map),
            tooltip: 'Alertler Haritası',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const AlertsMapScreen()),
              );
            },
          ),
          PopupMenuButton<String>(
            onSelected: (value) async {
              if (value == 'login') {
                Navigator.pushNamed(context, '/login');
              } else if (value == 'register') {
                Navigator.pushNamed(context, '/register');
              } else if (value == 'profile') {
              } else if (value == 'logout') {
                await _authService.logout();
                _checkLoginStatus();
              }
            },
            itemBuilder: (BuildContext context) {
              if (_isLoggedIn) {
                return [
                  const PopupMenuItem<String>(
                    value: 'profile',
                    child: Row(
                      children: [
                        Icon(Icons.person, color: Colors.blue),
                        SizedBox(width: 8),
                        Text('Profilim'),
                      ],
                    ),
                  ),
                  const PopupMenuItem<String>(
                    value: 'logout',
                    child: Row(
                      children: [
                        Icon(Icons.logout, color: Colors.red),
                        SizedBox(width: 8),
                        Text('Çıkış Yap'),
                      ],
                    ),
                  ),
                ];
              } else {
                return [
                  const PopupMenuItem<String>(
                    value: 'login',
                    child: Row(
                      children: [
                        Icon(Icons.login, color: Colors.green),
                        SizedBox(width: 8),
                        Text('Giriş Yap'),
                      ],
                    ),
                  ),
                  const PopupMenuItem<String>(
                    value: 'register',
                    child: Row(
                      children: [
                        Icon(Icons.person_add, color: Colors.blue),
                        SizedBox(width: 8),
                        Text('Kayıt Ol'),
                      ],
                    ),
                  ),
                ];
              }
            },
          ),
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
    );
  }
  
  Widget _buildLiveTab() {
    return Column(
      children: [
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
                  color: _apiConnected ? Colors.green.shade700 : Colors.red.shade700,
                ),
              ),
              if (!_apiConnected) ...[
                const Spacer(),
                ElevatedButton.icon(
                  onPressed: _checkApiConnection,
                  icon: const Icon(Icons.refresh, size: 16),
                  label: const Text('Tekrar Dene'),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 0),
                    minimumSize: const Size(0, 30),
                  ),
                ),
              ],
            ],
          ),
        ),
        
        Container(
          padding: const EdgeInsets.all(8),
          margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 0),
          decoration: BoxDecoration(
            color: _locationInitialized ? Colors.green.shade100 : Colors.orange.shade100,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: _locationInitialized ? Colors.green : Colors.orange),
          ),
          child: Row(
            children: [
              Icon(
                _locationInitialized ? Icons.location_on : Icons.location_off,
                color: _locationInitialized ? Colors.green : Colors.orange,
              ),
              const SizedBox(width: 8),
              Text(
                _locationInitialized ? 'Konum Servisi Aktif' : 'Konum Servisi Devre Dışı',
                style: TextStyle(
                  color: _locationInitialized ? Colors.green.shade700 : Colors.orange.shade700,
                ),
              ),
              if (!_locationInitialized) ...[
                const Spacer(),
                ElevatedButton.icon(
                  onPressed: _initializeLocation,
                  icon: const Icon(Icons.refresh, size: 16),
                  label: const Text('Aktifleştir'),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 0),
                    minimumSize: const Size(0, 30),
                  ),
                ),
              ],
            ],
          ),
        ),
        
        if (_isListening)
          Container(
            padding: const EdgeInsets.all(8),
            margin: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.blue.shade100,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.blue),
            ),
            child: Column(
              children: [
                Row(
                  children: [
                    const Icon(Icons.mic, color: Colors.blue),
                    const SizedBox(width: 8),
                    Text(
                      _secondsRemaining > 0 
                        ? 'Dinleniyor... $_secondsRemaining sn kaldı' 
                        : 'Dinleniyor...',
                      style: TextStyle(
                        color: Colors.blue.shade700,
                      ),
                    ),
                    const Spacer(),
                    _isProcessing
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(Colors.blue),
                          ),
                        )
                      : const Icon(Icons.hearing, color: Colors.blue),
                  ],
                ),
                
                const SizedBox(height: 8),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: _currentAudioLevel,
                    backgroundColor: Colors.grey.shade300,
                    valueColor: AlwaysStoppedAnimation<Color>(
                      _currentAudioLevel > _minThreshold
                        ? Colors.green
                        : Colors.grey
                    ),
                    minHeight: 8,
                  ),
                ),
              ],
            ),
          ),
          
        if (_currentError != null)
          Container(
            padding: const EdgeInsets.all(8),
            margin: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.red.shade100,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.red),
            ),
            child: Row(
              children: [
                const Icon(Icons.error, color: Colors.red),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _currentError!,
                    style: TextStyle(
                      color: Colors.red.shade700,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, color: Colors.red),
                  onPressed: () {
                    setState(() {
                      _currentError = null;
                    });
                  },
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(
                    minWidth: 30,
                    minHeight: 30,
                  ),
                ),
              ],
            ),
          ),
        
        if (!_isListening && _detectionResults.isEmpty)
          Container(
            padding: const EdgeInsets.all(16),
            margin: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.blue.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.blue.shade200),
            ),
            child: Column(
              children: [
                const Icon(Icons.info, color: Colors.blue, size: 32),
                const SizedBox(height: 8),
                const Text(
                  'Ses tanıma özelliğini kullanmak için "Dinle" butonuna basın',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Tanınan sesleri soldan sağa çekerek alert oluşturabilir veya değerlendirebilirsiniz',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.grey,
                  ),
                ),
              ],
            ),
          ),
          
        Expanded(
          child: _detectionResults.isEmpty
              ? const Center(
                  child: Text('Henüz ses tespit edilmedi'),
                )
              : ListView.builder(
                  itemCount: _detectionResults.length,
                  itemBuilder: (context, index) {
                    return SwipeableDetectionTile(
                      result: _detectionResults[index],
                      onEvaluationSubmitted: () {},
                      onAlertCreated: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Alert başarıyla oluşturuldu!'),
                            backgroundColor: Colors.green,
                          ),
                        );
                      },
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildHistoryTab() {
    return FutureBuilder<List<SoundDetectionResult>>(
      future: _evaluationService.getEvaluatedResults(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        
        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, size: 48, color: Colors.red),
                const SizedBox(height: 16),
                Text('Hata: ${snapshot.error}'),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: () {
                    setState(() {});
                  },
                  icon: const Icon(Icons.refresh),
                  label: const Text('Tekrar Dene'),
                ),
              ],
            ),
          );
        }
        
        if (!snapshot.hasData || snapshot.data!.isEmpty) {
          return const Center(
            child: Text('Henüz değerlendirilmiş ses kaydı bulunmuyor'),
          );
        }
        
        _savedResults = snapshot.data!;
        
        return ListView.builder(
          itemCount: _savedResults.length,
          itemBuilder: (context, index) {
            return SwipeableDetectionTile(
              result: _savedResults[index],
              onEvaluationSubmitted: () {
                setState(() {});
              },
              onAlertCreated: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Alert başarıyla oluşturuldu!'),
                    backgroundColor: Colors.green,
                  ),
                );
              },
            );
          },
        );
      },
    );
  }
}
