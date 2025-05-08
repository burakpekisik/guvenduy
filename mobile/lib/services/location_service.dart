import 'dart:async';
import 'package:geolocator/geolocator.dart';

class LocationService {
  // Singleton pattern
  static final LocationService _instance = LocationService._internal();
  factory LocationService() => _instance;
  LocationService._internal();
  
  // Stream controllers
  final _locationController = StreamController<Position>.broadcast();
  Stream<Position> get locationStream => _locationController.stream;
  
  // Last known location
  Position? _lastKnownLocation;
  Position? get lastKnownLocation => _lastKnownLocation;
  
  // Location update timer
  Timer? _locationUpdateTimer;
  
  // Initialize and start location updates
  Future<bool> initLocationService() async {
    bool serviceEnabled;
    LocationPermission permission;

    // Test if location services are enabled
    serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      // Location services are not enabled
      return false;
    }

    // Check location permission
    permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        // Permissions are denied
        return false;
      }
    }
    
    if (permission == LocationPermission.deniedForever) {
      // Permissions are permanently denied
      return false;
    }
    
    // Get current position once
    try {
      _lastKnownLocation = await Geolocator.getCurrentPosition();
      _locationController.add(_lastKnownLocation!);
    } catch (e) {
      print('Error getting current position: $e');
      return false;
    }

    return true;
  }
  
  // Start listening to location updates 
  void startLocationUpdates({Duration interval = const Duration(seconds: 30)}) {
    // Stop any existing timer
    stopLocationUpdates();
    
    // Update location immediately
    _updateLocation();
    
    // Set up periodic updates
    _locationUpdateTimer = Timer.periodic(interval, (_) {
      _updateLocation();
    });
  }
  
  // Update location
  Future<void> _updateLocation() async {
    try {
      final position = await Geolocator.getCurrentPosition();
      _lastKnownLocation = position;
      _locationController.add(position);
    } catch (e) {
      print('Error updating location: $e');
    }
  }
  
  // Stop listening to location updates
  void stopLocationUpdates() {
    _locationUpdateTimer?.cancel();
    _locationUpdateTimer = null;
  }
  
  // Get current position once
  Future<Position?> getCurrentPosition() async {
    try {
      final position = await Geolocator.getCurrentPosition();
      _lastKnownLocation = position;
      return position;
    } catch (e) {
      print('Error getting current position: $e');
      return null;
    }
  }
  
  // Calculate distance between two coordinates in kilometers
  double calculateDistance(double startLat, double startLng, double endLat, double endLng) {
    return Geolocator.distanceBetween(startLat, startLng, endLat, endLng) / 1000;
  }
  
  // Dispose resources
  void dispose() {
    stopLocationUpdates();
    _locationController.close();
  }
}