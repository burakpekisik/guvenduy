import 'dart:async';
import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:geolocator/geolocator.dart';
import 'package:device_info_plus/device_info_plus.dart';
import '../services/alerts_service.dart';
import '../services/location_service.dart';
import '../models/alert.dart';
import '../models/notifiable_class.dart';

class AlertsMapScreen extends StatefulWidget {
  const AlertsMapScreen({Key? key}) : super(key: key);

  @override
  _AlertsMapScreenState createState() => _AlertsMapScreenState();
}

class _AlertsMapScreenState extends State<AlertsMapScreen> {
  final AlertsService _alertsService = AlertsService();
  final LocationService _locationService = LocationService();
  
  GoogleMapController? _mapController;
  final Set<Marker> _markers = {};
  final Map<int, BitmapDescriptor> _markerIcons = {};
  final Map<int, NotifiableClass> _classesById = {};
  
  // Location data
  Position? _currentPosition;
  bool _loadingLocation = true;
  bool _locationPermissionDenied = false;
  
  // Alerts data
  List<Alert> _nearbyAlerts = [];
  bool _loadingAlerts = false;
  String? _errorMessage;
  
  // Map settings
  double _currentZoom = 15.0;
  final double _initialZoom = 15.0;
  final double _defaultSearchRadius = 2.0; // in km
  
  // Map update timer
  Timer? _mapUpdateTimer;
  
  @override
  void initState() {
    super.initState();
    
    // Initialize
    _initializeMap();
    
    // Start periodic refresh
    _alertsService.startPeriodicClassRefresh();
  }
  
  @override
  void dispose() {
    _mapUpdateTimer?.cancel();
    super.dispose();
  }
  
  Future<void> _initializeMap() async {
    // Load custom marker icons
    await _loadMarkerIcons();
    
    // Initialize location service
    final locationInitialized = await _locationService.initLocationService();
    
    if (!locationInitialized) {
      setState(() {
        _loadingLocation = false;
        _locationPermissionDenied = true;
      });
      return;
    }
    
    // Get initial position
    _currentPosition = await _locationService.getCurrentPosition();
    
    if (_currentPosition != null) {
      setState(() {
        _loadingLocation = false;
      });
      
      // Start location updates
      _locationService.startLocationUpdates();
      
      // Subscribe to location updates
      _locationService.locationStream.listen((position) {
        setState(() {
          _currentPosition = position;
        });
        
        if (_mapController != null) {
          _updateMapPosition();
        }
      });
      
      // Load nearby alerts
      _loadNearbyAlerts();
      
      // Setup periodic alerts refresh
      _mapUpdateTimer = Timer.periodic(const Duration(minutes: 2), (_) {
        _loadNearbyAlerts();
      });
    } else {
      setState(() {
        _loadingLocation = false;
        _errorMessage = 'Konum bilgisi alınamadı';
      });
    }
    
    // Load notifiable classes
    await _loadNotifiableClasses();
  }
  
  Future<void> _loadNotifiableClasses() async {
    try {
      final classes = await _alertsService.getNotifiableClasses();
      setState(() {
        _classesById.clear();
        for (var alertClass in classes) {
          _classesById[alertClass.id] = alertClass;
        }
      });
    } catch (e) {
      print('Error loading notifiable classes: $e');
    }
  }

  Future<void> _loadMarkerIcons() async {
    try {
      // You can customize marker icons based on alert type
      // Default uses standard marker
      
      // Example of custom marker for fire_alarm type
      final customIcon = await BitmapDescriptor.fromAssetImage(
        const ImageConfiguration(size: Size(48, 48)),
        'assets/images/alert_marker.png',
      );
      
      setState(() {
        // Store custom marker by class ID if you have it
        // For now, just use a default one
        _markerIcons[-1] = customIcon; // Default marker
      });
    } catch (e) {
      print('Error loading marker icons: $e');
    }
  }
  
  Future<void> _loadNearbyAlerts() async {
    if (_currentPosition == null || _loadingAlerts) {
      return;
    }
    
    setState(() {
      _loadingAlerts = true;
      _errorMessage = null;
    });
    
    try {
      final alerts = await _alertsService.getNearbyAlerts(
        latitude: _currentPosition!.latitude,
        longitude: _currentPosition!.longitude,
        radiusKm: _defaultSearchRadius,
        hoursAgo: 24, // Show alerts from the last 24 hours
      );
      
      setState(() {
        _nearbyAlerts = alerts;
        _loadingAlerts = false;
        _updateMarkers();
      });
    } catch (e) {
      setState(() {
        _loadingAlerts = false;
        _errorMessage = 'Yakındaki alertler yüklenirken hata oluştu: $e';
      });
    }
  }
  
  void _updateMarkers() {
    final Set<Marker> newMarkers = {};
    
    // Add marker for current position
    if (_currentPosition != null) {
      newMarkers.add(
        Marker(
          markerId: const MarkerId('current_location'),
          position: LatLng(_currentPosition!.latitude, _currentPosition!.longitude),
          infoWindow: const InfoWindow(title: 'Konumunuz'),
          icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueAzure),
        ),
      );
    }
    
    // Add markers for alerts
    for (final alert in _nearbyAlerts) {
      final alertClass = _classesById[alert.classId];
      final String title = alertClass?.className ?? 'Alert';
      
      newMarkers.add(
        Marker(
          markerId: MarkerId('alert_${alert.id}'),
          position: LatLng(alert.latitude, alert.longitude),
          infoWindow: InfoWindow(
            title: title,
            snippet: '${(alert.confidence * 100).toStringAsFixed(0)}% güven oranı - ${_formatTimeAgo(alert.createdAt)}',
          ),
          icon: _markerIcons[-1] ?? BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueRed),
        ),
      );
    }
    
    setState(() {
      _markers.clear();
      _markers.addAll(newMarkers);
    });
  }
  
  void _updateMapPosition() {
    if (_currentPosition != null && _mapController != null) {
      _mapController!.animateCamera(
        CameraUpdate.newLatLng(
          LatLng(_currentPosition!.latitude, _currentPosition!.longitude),
        ),
      );
    }
  }
  
  String _formatTimeAgo(DateTime dateTime) {
    final now = DateTime.now();
    final difference = now.difference(dateTime);
    
    if (difference.inMinutes < 1) {
      return 'Şimdi';
    } else if (difference.inMinutes < 60) {
      return '${difference.inMinutes} dakika önce';
    } else if (difference.inHours < 24) {
      return '${difference.inHours} saat önce';
    } else {
      return '${difference.inDays} gün önce';
    }
  }
  
  @override
  Widget build(BuildContext context) {
    if (_loadingLocation) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('Yakındaki Alertler'),
        ),
        body: const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Konum alınıyor...'),
            ],
          ),
        ),
      );
    }
    
    if (_locationPermissionDenied) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('Yakındaki Alertler'),
        ),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.location_off, size: 70, color: Colors.red),
              const SizedBox(height: 16),
              const Text(
                'Konum izni verilmedi',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              const Text(
                'Alertleri görebilmek için konum izni vermeniz gerekiyor.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () async {
                  // Try to request permission again
                  final permission = await Geolocator.requestPermission();
                  if (permission != LocationPermission.denied && 
                      permission != LocationPermission.deniedForever) {
                    // Reinitialize map
                    _initializeMap();
                  }
                },
                child: const Text('Konum İzni Ver'),
              ),
            ],
          ),
        ),
      );
    }
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('Yakındaki Alertler'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadNearbyAlerts,
          ),
        ],
      ),
      body: Stack(
        children: [
          // Map
          GoogleMap(
            initialCameraPosition: CameraPosition(
              target: _currentPosition != null
                  ? LatLng(_currentPosition!.latitude, _currentPosition!.longitude)
                  : const LatLng(39.925533, 32.866287), // Ankara default
              zoom: _initialZoom,
            ),
            myLocationEnabled: true,
            myLocationButtonEnabled: true,
            markers: _markers,
            onMapCreated: (controller) {
              _mapController = controller;
            },
            onCameraMove: (position) {
              _currentZoom = position.zoom;
            },
          ),
          
          // Loading indicator
          if (_loadingAlerts)
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: Container(
                padding: const EdgeInsets.all(8.0),
                color: Colors.black54,
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    ),
                    SizedBox(width: 8),
                    Text(
                      'Alertler yükleniyor...',
                      style: TextStyle(color: Colors.white),
                    ),
                  ],
                ),
              ),
            ),
          
          // Error message
          if (_errorMessage != null)
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: Container(
                padding: const EdgeInsets.all(8.0),
                color: Colors.red,
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
                    IconButton(
                      icon: const Icon(Icons.close, color: Colors.white),
                      onPressed: () {
                        setState(() {
                          _errorMessage = null;
                        });
                      },
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                  ],
                ),
              ),
            ),
            
          // Alert count
          Positioned(
            bottom: 16,
            left: 16,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.1),
                    spreadRadius: 1,
                    blurRadius: 3,
                    offset: const Offset(0, 1),
                  ),
                ],
              ),
              child: Text(
                '${_nearbyAlerts.length} alert bulundu',
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _centerOnCurrentLocation,
        child: const Icon(Icons.my_location),
      ),
    );
  }
  
  void _centerOnCurrentLocation() {
    if (_currentPosition != null && _mapController != null) {
      _mapController!.animateCamera(
        CameraUpdate.newLatLngZoom(
          LatLng(_currentPosition!.latitude, _currentPosition!.longitude),
          _initialZoom,
        ),
      );
    }
  }
}