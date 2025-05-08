class NotifiableClass {
  final int id;
  final String className;
  final String? description;
  final double minConfidence;
  final bool isActive;
  final DateTime createdAt;

  NotifiableClass({
    required this.id,
    required this.className,
    this.description,
    required this.minConfidence,
    required this.isActive,
    required this.createdAt,
  });

  factory NotifiableClass.fromJson(Map<String, dynamic> json) {
    return NotifiableClass(
      id: json['id'],
      className: json['class_name'],
      description: json['description'],
      minConfidence: json['min_confidence'].toDouble(),
      isActive: json['is_active'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'class_name': className,
      'description': description,
      'min_confidence': minConfidence,
      'is_active': isActive,
      'created_at': createdAt.toIso8601String(),
    };
  }
}