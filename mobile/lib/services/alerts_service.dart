import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/alert.dart';
import '../models/notifiable_class.dart';

class AlertsService {
  final String baseUrl;
  final String alertsBaseUrl;
  
  // Endpoints
  final String createAlertEndpoint;
  final String nearbyAlertsEndpoint;
  final String notifiableClassesEndpoint;
  final String updateLocationEndpoint;
  
  // Streams for real-time updates
  final _alertClassesController = StreamController<List<NotifiableClass>>.broadcast();
  Stream<List<NotifiableClass>> get alertClassesStream => _alertClassesController.stream;
  
  // Cache for notifiable classes
  List<NotifiableClass> _cachedClasses = [];
  List<NotifiableClass> get cachedClasses => _cachedClasses;
  
  // Auth token
  String? _authToken;
  
  // Singleton pattern
  static final AlertsService _instance = AlertsService._internal();
  factory AlertsService() => _instance;
  
  AlertsService._internal({
    String? baseUrl,
    String? alertsBaseUrl,
    String? createAlertEndpoint,
    String? nearbyAlertsEndpoint,
    String? notifiableClassesEndpoint,
    String? updateLocationEndpoint,
  }) :
    baseUrl = baseUrl ?? dotenv.env['API_BASE_URL'] ?? 'http://10.0.2.2:8000',
    alertsBaseUrl = alertsBaseUrl ?? dotenv.env['ALERTS_BASE_URL'] ?? '/alerts',
    createAlertEndpoint = createAlertEndpoint ?? dotenv.env['ALERTS_CREATE_ENDPOINT'] ?? '/create',
    nearbyAlertsEndpoint = nearbyAlertsEndpoint ?? dotenv.env['ALERTS_NEARBY_ENDPOINT'] ?? '/nearby',
    notifiableClassesEndpoint = notifiableClassesEndpoint ?? dotenv.env['ALERTS_CLASSES_ENDPOINT'] ?? '/classes',
    updateLocationEndpoint = updateLocationEndpoint ?? dotenv.env['ALERTS_LOCATION_ENDPOINT'] ?? '/location';
  
  // Set auth token
  void setAuthToken(String? token) {
    _authToken = token;
  }
  
  // Get URL helper
  String _getUrl(String endpoint) {
    return '$baseUrl$alertsBaseUrl$endpoint';
  }
  
  // Headers helper
  Map<String, String> _getHeaders({Map<String, String>? additionalHeaders}) {
    Map<String, String> headers = additionalHeaders ?? {'Content-Type': 'application/json'};
    
    if (_authToken != null && _authToken!.isNotEmpty) {
      headers['Authorization'] = 'Bearer $_authToken';
    }
    
    return headers;
  }
  
  // Fetch nearby alerts
  Future<List<Alert>> getNearbyAlerts({
    required double latitude,
    required double longitude,
    double radiusKm = 1.0,
    List<int>? classIds,
    int? hoursAgo,
  }) async {
    final queryParams = {
      'latitude': latitude.toString(),
      'longitude': longitude.toString(),
      'radius_km': radiusKm.toString(),
    };
    
    if (classIds != null && classIds.isNotEmpty) {
      queryParams['class_ids'] = classIds.join(',');
    }
    
    if (hoursAgo != null) {
      queryParams['hours_ago'] = hoursAgo.toString();
    }
    
    final url = Uri.parse(_getUrl(nearbyAlertsEndpoint)).replace(queryParameters: queryParams);
    
    try {
      final response = await http.get(
        url,
        headers: _getHeaders(),
      );
      
      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.map((item) => Alert.fromJson(item)).toList();
      } else {
        print('Failed to get nearby alerts: ${response.statusCode} - ${response.body}');
        return [];
      }
    } catch (e) {
      print('Error getting nearby alerts: $e');
      return [];
    }
  }
  
  // Create a new alert
  Future<Alert?> createAlert({
    required int classId,
    required double latitude,
    required double longitude,
    required double confidence,
    required String deviceId,
  }) async {
    try {
      final response = await http.post(
        Uri.parse(_getUrl(createAlertEndpoint)),
        headers: _getHeaders(),
        body: json.encode({
          'class_id': classId,
          'latitude': latitude,
          'longitude': longitude,
          'confidence': confidence,
          'device_id': deviceId,
        }),
      );
      
      if (response.statusCode == 201) {
        final data = json.decode(response.body);
        return Alert.fromJson(data);
      } else {
        print('Failed to create alert: ${response.statusCode} - ${response.body}');
        return null;
      }
    } catch (e) {
      print('Error creating alert: $e');
      return null;
    }
  }
  
  // Update user location
  Future<bool> updateLocation({
    required double latitude,
    required double longitude,
    double? accuracy,
  }) async {
    try {
      final Map<String, dynamic> data = {
        'latitude': latitude,
        'longitude': longitude,
      };
      
      if (accuracy != null) {
        data['accuracy'] = accuracy;
      }
      
      final response = await http.post(
        Uri.parse(_getUrl(updateLocationEndpoint)),
        headers: _getHeaders(),
        body: json.encode(data),
      );
      
      return response.statusCode == 200;
    } catch (e) {
      print('Error updating location: $e');
      return false;
    }
  }
  
  // Get all notifiable classes (for alert selection)
  Future<List<NotifiableClass>> getNotifiableClasses({bool forceRefresh = false}) async {
    if (_cachedClasses.isNotEmpty && !forceRefresh) {
      return _cachedClasses;
    }
    
    try {
      final response = await http.get(
        Uri.parse(_getUrl(notifiableClassesEndpoint)),
        headers: _getHeaders(),
      );
      
      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        _cachedClasses = data.map((item) => NotifiableClass.fromJson(item)).toList();
        
        // Update stream
        _alertClassesController.add(_cachedClasses);
        
        // Cache to shared preferences
        _saveClassesToCache();
        
        return _cachedClasses;
      } else {
        print('Failed to get notifiable classes: ${response.statusCode} - ${response.body}');
        
        // Try to load from cache
        await _loadClassesFromCache();
        return _cachedClasses;
      }
    } catch (e) {
      print('Error getting notifiable classes: $e');
      
      // Try to load from cache
      await _loadClassesFromCache();
      return _cachedClasses;
    }
  }
  
  // Start periodic fetching of notifiable classes
  Timer? _classRefreshTimer;
  
  void startPeriodicClassRefresh({Duration refreshInterval = const Duration(minutes: 15)}) {
    // Cancel any existing timer
    _classRefreshTimer?.cancel();
    
    // Initial fetch
    getNotifiableClasses(forceRefresh: true);
    
    // Set up periodic refresh
    _classRefreshTimer = Timer.periodic(refreshInterval, (_) {
      getNotifiableClasses(forceRefresh: true);
    });
  }
  
  void stopPeriodicClassRefresh() {
    _classRefreshTimer?.cancel();
    _classRefreshTimer = null;
  }
  
  // Cache management
  Future<void> _saveClassesToCache() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final classesJson = _cachedClasses.map((c) => c.toJson()).toList();
      await prefs.setString('cached_notifiable_classes', json.encode(classesJson));
    } catch (e) {
      print('Error saving classes to cache: $e');
    }
  }
  
  Future<void> _loadClassesFromCache() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cachedData = prefs.getString('cached_notifiable_classes');
      
      if (cachedData != null) {
        final List<dynamic> classesJson = json.decode(cachedData);
        _cachedClasses = classesJson.map((item) => NotifiableClass.fromJson(item)).toList();
        _alertClassesController.add(_cachedClasses);
      }
    } catch (e) {
      print('Error loading classes from cache: $e');
      _cachedClasses = [];
    }
  }
  
  // Dispose resources
  void dispose() {
    _classRefreshTimer?.cancel();
    _alertClassesController.close();
  }
}