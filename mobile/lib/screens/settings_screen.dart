import 'package:flutter/material.dart';
import '../models/app_settings.dart';
import '../services/settings_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final SettingsService _settingsService = SettingsService();
  late AppSettings _settings;
  
  @override
  void initState() {
    super.initState();
    _settings = _settingsService.currentSettings;
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ayarlar'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: ListView(
        children: [
          _buildSectionHeader('Ses Algılama Ayarları'),
          
          // Algılama eşik değeri (detection threshold)
          _buildThresholdSetting(
            title: 'Algılama Eşik Değeri',
            value: _settings.detectionThreshold,
            description: 'Bu değerin altındaki tüm sesler algılanmayacak veya "Bilinmeyen" olarak işaretlenecek.',
            onChanged: (value) {
              setState(() {
                _settings = _settings.copyWith(detectionThreshold: value);
              });
            },
            onChangeEnd: (value) async {
              await _settingsService.updateDetectionThreshold(value);
            },
          ),
          
          const Divider(),
          
          // Mikrofon eşik değeri (microphone threshold)
          _buildThresholdSetting(
            title: 'Mikrofon Eşik Değeri',
            value: _settings.microphoneThreshold,
            description: 'Bu seviyenin altındaki sesler kaydedilmeyecek ve işlenmeyecek.',
            onChanged: (value) {
              setState(() {
                _settings = _settings.copyWith(microphoneThreshold: value);
              });
            },
            onChangeEnd: (value) async {
              await _settingsService.updateMicrophoneThreshold(value);
            },
          ),
          
          const Divider(),
          
          // Düşük güvenirlikli sesleri filtrele
          SwitchListTile(
            title: const Text('Düşük Güvenirlikli Sesleri Filtrele'),
            subtitle: const Text('Eşik değerinin altındaki sesler "Bilinmeyen" olarak işaretlenir'),
            value: _settings.filterLowConfidence,
            onChanged: (value) async {
              await _settingsService.updateFilterLowConfidence(value);
              setState(() {
                _settings = _settingsService.currentSettings;
              });
            },
          ),
          
          const Divider(),
          
          // Tüm tahminleri göster
          SwitchListTile(
            title: const Text('Tüm Tahminleri Göster'),
            subtitle: const Text('Her algılama için tüm olası ses türlerinin yüzdelerini göster'),
            value: _settings.showAllPredictions,
            onChanged: (value) async {
              await _settingsService.updateShowAllPredictions(value);
              setState(() {
                _settings = _settingsService.currentSettings;
              });
            },
          ),
          
          const SizedBox(height: 16),
          _buildSectionHeader('Hakkında'),
          
          ListTile(
            title: const Text('Uygulama Versiyonu'),
            subtitle: const Text('1.0.0'),
            leading: const Icon(Icons.info_outline),
          ),
        ],
      ),
    );
  }
  
  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Text(
        title,
        style: TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.bold,
          color: Theme.of(context).colorScheme.primary,
        ),
      ),
    );
  }
  
  Widget _buildThresholdSetting({
    required String title, 
    required double value, 
    required String description,
    required Function(double) onChanged,
    required Function(double) onChangeEnd,
  }) {
    // Convert threshold to percentage
    int percentageValue = (value * 100).round();
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                title,
                style: const TextStyle(fontSize: 16),
              ),
              Text(
                '$percentageValue%',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
            ],
          ),
        ),
        Slider(
          value: value,
          min: 0.05,  // Minimum 5%
          max: 0.95,  // Maximum 95%
          divisions: 18,  // 18 divisions for 5% steps
          label: '$percentageValue%',
          onChanged: onChanged,
          onChangeEnd: onChangeEnd,
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Text(
            description,
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey[600],
              fontStyle: FontStyle.italic,
            ),
          ),
        ),
      ],
    );
  }
}