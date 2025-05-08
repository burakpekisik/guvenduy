import 'dart:async';
import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:geolocator/geolocator.dart';
import 'package:device_info_plus/device_info_plus.dart';
import '../services/alerts_service.dart';
import '../services/location_service.dart';
import '../models/notifiable_class.dart';
import '../models/sound_detection_result.dart';

class CreateAlertScreen extends StatefulWidget {
  final SoundDetectionResult result;
  final NotifiableClass alertClass;

  const CreateAlertScreen({
    Key? key,
    required this.result,
    required this.alertClass,
  }) : super(key: key);

  @override
  _CreateAlertScreenState createState() => _CreateAlertScreenState();
}

class _CreateAlertScreenState extends State<CreateAlertScreen> {
  final AlertsService _alertsService = AlertsService();
  final LocationService _locationService = LocationService();
  
  GoogleMapController? _mapController;
  Position? _currentPosition;
  LatLng? _selectedPosition;
  String? _deviceId;
  
  bool _isLoading = true;
  bool _isSending = false;
  String? _errorMessage;
  bool _isSuccess = false;
  
  final _addressController = TextEditingController();
  bool _customAddress = false;
  
  @override
  void initState() {
    super.initState();
    _initializeLocation();
    _getDeviceId();
  }

  @override
  void dispose() {
    _addressController.dispose();
    super.dispose();
  }
  
  Future<void> _initializeLocation() async {
    try {
      // Initialize location service
      await _locationService.initLocationService();
      
      // Get current position
      _currentPosition = await _locationService.getCurrentPosition();
      
      if (_currentPosition != null) {
        setState(() {
          _selectedPosition = LatLng(
            _currentPosition!.latitude,
            _currentPosition!.longitude,
          );
          _isLoading = false;
        });
      } else {
        setState(() {
          _errorMessage = 'Konum bilgisi alınamadı';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Konum servisine erişilemiyor: $e';
        _isLoading = false;
      });
    }
  }
  
  Future<void> _getDeviceId() async {
    try {
      final deviceInfo = DeviceInfoPlugin();
      
      if (Theme.of(context).platform == TargetPlatform.android) {
        final androidInfo = await deviceInfo.androidInfo;
        _deviceId = androidInfo.id;
      } else if (Theme.of(context).platform == TargetPlatform.iOS) {
        final iosInfo = await deviceInfo.iosInfo;
        _deviceId = iosInfo.identifierForVendor;
      } else {
        // Generate a random ID for other platforms
        _deviceId = DateTime.now().millisecondsSinceEpoch.toString();
      }
    } catch (e) {
      // Fallback to timestamp if device ID couldn't be retrieved
      _deviceId = DateTime.now().millisecondsSinceEpoch.toString();
    }
  }
  
  Future<void> _submitAlert() async {
    if (_selectedPosition == null || _deviceId == null) {
      setState(() {
        _errorMessage = 'Konum ve cihaz bilgileri alınamadı';
      });
      return;
    }
    
    setState(() {
      _isSending = true;
      _errorMessage = null;
    });
    
    try {
      final alert = await _alertsService.createAlert(
        classId: widget.alertClass.id,
        latitude: _selectedPosition!.latitude,
        longitude: _selectedPosition!.longitude,
        confidence: widget.result.confidence,
        deviceId: _deviceId!,
      );
      
      if (alert != null) {
        setState(() {
          _isSending = false;
          _isSuccess = true;
        });
        
        // Show success message and go back after a delay
        Future.delayed(const Duration(seconds: 2), () {
          if (mounted) {
            Navigator.of(context).pop(true); // Success
          }
        });
      } else {
        setState(() {
          _isSending = false;
          _errorMessage = 'Alert gönderilirken bir hata oluştu';
        });
      }
    } catch (e) {
      setState(() {
        _isSending = false;
        _errorMessage = 'Alert gönderilirken bir hata oluştu: $e';
      });
    }
  }
  
  void _updateSelectedLocation(LatLng position) {
    setState(() {
      _selectedPosition = position;
      _customAddress = true;
    });
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Alert Oluştur'),
        backgroundColor: Colors.red,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _buildContent(),
      bottomNavigationBar: _buildBottomBar(),
    );
  }
  
  Widget _buildContent() {
    if (_isSuccess) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.check_circle, color: Colors.green, size: 80),
            const SizedBox(height: 16),
            const Text(
              'Alert başarıyla gönderildi!',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text('Katkınız için teşekkür ederiz.'),
          ],
        ),
      );
    }
    
    return Column(
      children: [
        // Alert info card
        Card(
          margin: const EdgeInsets.all(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    _getIconForSoundType(widget.result.soundType),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            widget.result.soundType.toUpperCase(),
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Text(
                            'Güven oranı: ${(widget.result.confidence * 100).toStringAsFixed(1)}%',
                            style: TextStyle(
                              color: Colors.grey.shade700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const Divider(height: 24),
                const Text(
                  'Alert Sınıfı:',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                Text(widget.alertClass.className),
                if (widget.alertClass.description != null) ...[
                  const SizedBox(height: 8),
                  Text(
                    widget.alertClass.description!,
                    style: TextStyle(
                      fontStyle: FontStyle.italic,
                      color: Colors.grey.shade700,
                      fontSize: 12,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
        
        // Map section
        Expanded(
          child: Stack(
            children: [
              // Map
              GoogleMap(
                initialCameraPosition: CameraPosition(
                  target: _selectedPosition ?? const LatLng(39.925533, 32.866287),
                  zoom: 15,
                ),
                myLocationEnabled: true,
                myLocationButtonEnabled: true,
                markers: _selectedPosition == null
                    ? {}
                    : {
                        Marker(
                          markerId: const MarkerId('selected_location'),
                          position: _selectedPosition!,
                          infoWindow: const InfoWindow(title: 'Alert Konumu'),
                        ),
                      },
                onMapCreated: (controller) {
                  _mapController = controller;
                },
                onTap: _updateSelectedLocation,
              ),
              
              // Instructions
              Positioned(
                top: 16,
                left: 16,
                right: 16,
                child: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.8),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Text(
                    'Harita üzerinde alert konumunu düzenleyebilirsiniz',
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
              
              // Error message
              if (_errorMessage != null)
                Positioned(
                  bottom: 16,
                  left: 16,
                  right: 16,
                  child: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.red.withOpacity(0.8),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.error, color: Colors.white),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            _errorMessage!,
                            style: const TextStyle(color: Colors.white),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
  
  Widget _buildBottomBar() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 5,
            offset: const Offset(0, -3),
          ),
        ],
      ),
      child: SafeArea(
        child: Row(
          children: [
            Expanded(
              child: ElevatedButton(
                onPressed: _isSending || _isSuccess ? null : _submitAlert,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.red,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
                child: _isSending
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          color: Colors.white,
                          strokeWidth: 2,
                        ),
                      )
                    : const Text('ALERT GÖNDER'),
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _getIconForSoundType(String soundType) {
    switch (soundType.toLowerCase()) {
      case 'siren':
        return const Icon(Icons.notifications_active, color: Colors.red, size: 30);
      case 'car_horn':
        return const Icon(Icons.car_rental, color: Colors.orange, size: 30);
      case 'ambulance':
        return const Icon(Icons.local_hospital, color: Colors.red, size: 30);
      case 'police':
        return const Icon(Icons.local_police, color: Colors.blue, size: 30);
      case 'fire_truck':
        return const Icon(Icons.fire_truck, color: Colors.red, size: 30);
      case 'cat':
        return const Icon(Icons.pets, color: Colors.amber, size: 30);
      case 'dog':
        return const Icon(Icons.pets, color: Colors.brown, size: 30);
      case 'fire_alarm':
        return const Icon(Icons.warning, color: Colors.red, size: 30);
      case 'thunder':
        return const Icon(Icons.flash_on, color: Colors.purple, size: 30);
      case 'car_crash':
        return const Icon(Icons.car_crash, color: Colors.red, size: 30);
      case 'explosion':
        return const Icon(Icons.local_fire_department, color: Colors.deepOrange, size: 30);
      case 'gun':
        return const Icon(Icons.gps_fixed, color: Colors.grey, size: 30);
      case 'background':
        return const Icon(Icons.surround_sound, color: Colors.grey, size: 30);
      case 'unknown':
        return const Icon(Icons.help_outline, color: Colors.grey, size: 30);
      default:
        return const Icon(Icons.notifications, color: Colors.blue, size: 30);
    }
  }
}