import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'screens/auth_wrapper.dart';
import 'screens/login_screen.dart';
import 'screens/register_screen.dart';
import 'screens/sound_detection_screen.dart';
import 'services/settings_service.dart';

void main() async {
  // Ensure Flutter is initialized
  WidgetsFlutterBinding.ensureInitialized();
  
  // Load environment variables
  await dotenv.load(fileName: ".env");
  
  // Initialize settings service
  final settingsService = SettingsService();
  await settingsService.init();
  
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Ses Tanıma Uygulaması',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
        useMaterial3: true,
      ),
      // Doğrudan ses tanıma ekranıyla başla
      initialRoute: '/sound_detection',
      routes: {
        '/': (context) => const AuthWrapper(),
        '/login': (context) => LoginScreen(onLoginSuccess: () {
          Navigator.pushReplacementNamed(context, '/sound_detection');
        }),
        '/register': (context) => const RegisterScreen(),
        '/sound_detection': (context) => const SoundDetectionScreen(),
      },
    );
  }
}
