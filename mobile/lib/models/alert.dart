import 'notifiable_class.dart';

class Alert {
  final int id;
  final int classId;
  final double latitude;
  final double longitude;
  final double confidence;
  final String deviceId;
  final bool isVerified;
  final DateTime createdAt;
  final NotifiableClass alertClass;
  final double? distanceKm;

  Alert({
    required this.id,
    required this.classId,
    required this.latitude,
    required this.longitude,
    required this.confidence,
    required this.deviceId,
    required this.isVerified,
    required this.createdAt,
    required this.alertClass,
    this.distanceKm,
  });

  factory Alert.fromJson(Map<String, dynamic> json) {
    return Alert(
      id: json['id'],
      classId: json['class_id'],
      latitude: json['latitude'].toDouble(),
      longitude: json['longitude'].toDouble(),
      confidence: json['confidence'].toDouble(),
      deviceId: json['device_id'],
      isVerified: json['is_verified'],
      createdAt: DateTime.parse(json['created_at']),
      alertClass: NotifiableClass.fromJson(json['alert_class']),
      distanceKm: json['distance_km']?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'class_id': classId,
      'latitude': latitude,
      'longitude': longitude,
      'confidence': confidence,
      'device_id': deviceId,
      'is_verified': isVerified,
      'created_at': createdAt.toIso8601String(),
      'alert_class': alertClass.toJson(),
      'distance_km': distanceKm,
    };
  }
}