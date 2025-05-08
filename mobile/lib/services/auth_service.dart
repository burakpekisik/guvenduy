import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import '../models/user.dart';

class AuthService {
  // API URL ve endpoint'ler
  final String baseUrl;
  final String authBaseUrl;
  final String loginEndpoint;
  final String registerEndpoint;
  final String meEndpoint;

  // Token saklama için anahtar
  static const String tokenKey = 'auth_token';
  static const String userDataKey = 'user_data';
  
  AuthService({
    String? baseUrl,
    String? authBaseUrl,
    String? loginEndpoint,
    String? registerEndpoint,
    String? meEndpoint,
  }) : 
    baseUrl = baseUrl ?? dotenv.env['API_BASE_URL'] ?? 'http://localhost:8000',
    authBaseUrl = authBaseUrl ?? dotenv.env['AUTH_BASE_URL'] ?? '/auth',
    loginEndpoint = loginEndpoint ?? dotenv.env['AUTH_LOGIN_ENDPOINT'] ?? '/token',
    registerEndpoint = registerEndpoint ?? dotenv.env['AUTH_REGISTER_ENDPOINT'] ?? '/register',
    meEndpoint = meEndpoint ?? dotenv.env['AUTH_ME_ENDPOINT'] ?? '/me';

  // URL oluşturma yardımcı metodu
  String _getUrl(String endpoint) {
    return '$baseUrl$authBaseUrl$endpoint';
  }

  // Giriş yapma metodu
  Future<User> login(String username, String password) async {
    final response = await http.post(
      Uri.parse(_getUrl(loginEndpoint)),
      body: {
        'username': username,
        'password': password,
      },
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    );

    if (response.statusCode == 200) {
      // Yanıtı JSON olarak ayrıştır
      final Map<String, dynamic> data = json.decode(response.body);
      
      // Token'ı al
      final String token = data['access_token'];
      
      // Kullanıcı bilgilerini al
      final userResponse = await http.get(
        Uri.parse(_getUrl(meEndpoint)),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
      );
      
      if (userResponse.statusCode == 200) {
        final Map<String, dynamic> userData = json.decode(userResponse.body);
        
        // User nesnesini oluştur
        final user = User(
          id: userData['id'],
          username: userData['username'],
          email: userData['email'],
          token: token,
        );
        
        // Token ve kullanıcı bilgilerini lokalde sakla
        await _saveToken(token);
        await _saveUserData(user);
        
        return user;
      } else {
        throw Exception('Failed to get user details');
      }
    } else {
      throw Exception('Failed to login: ${response.statusCode}');
    }
  }

  // Kayıt olma metodu
  Future<User> register(String username, String email, String password) async {
    final response = await http.post(
      Uri.parse(_getUrl(registerEndpoint)),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'username': username,
        'email': email,
        'password': password,
      }),
    );

    if (response.statusCode == 200 || response.statusCode == 201) {
      // Kayıt başarılı, şimdi giriş yap
      return login(username, password);
    } else {
      throw Exception('Failed to register: ${response.body}');
    }
  }

  // Çıkış yapma metodu
  Future<void> logout() async {
    // Yerel depolamadan token ve kullanıcı verilerini sil
    SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.remove(tokenKey);
    await prefs.remove(userDataKey);
  }

  // Token'ı kaydetme
  Future<void> _saveToken(String token) async {
    SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setString(tokenKey, token);
  }

  // Kullanıcı verilerini kaydetme
  Future<void> _saveUserData(User user) async {
    SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setString(userDataKey, json.encode(user.toJson()));
  }

  // Token'ı alma
  Future<String?> getToken() async {
    SharedPreferences prefs = await SharedPreferences.getInstance();
    return prefs.getString(tokenKey);
  }

  // Kullanıcı verilerini alma
  Future<User?> getCurrentUser() async {
    SharedPreferences prefs = await SharedPreferences.getInstance();
    String? userData = prefs.getString(userDataKey);
    
    if (userData != null) {
      Map<String, dynamic> userMap = json.decode(userData);
      return User.fromJson(userMap);
    }
    
    return null;
  }

  // Token kontrolü ile kullanıcının giriş durumunu kontrol etme
  Future<bool> isLoggedIn() async {
    String? token = await getToken();
    return token != null && token.isNotEmpty;
  }
}