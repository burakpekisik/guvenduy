import 'dart:io';

class PlatformHelper {
  /// Determines if the app is running in a debug or release mode
  static bool get isDebugMode {
    bool debugMode = false;
    assert(() {
      debugMode = true;
      return true;
    }());
    return debugMode;
  }
  
  /// Determines if the app is running on a mobile device
  static bool get isMobile => Platform.isAndroid || Platform.isIOS;
  
  /// Determines if the app is running on a desktop device
  static bool get isDesktop => 
      Platform.isWindows || Platform.isMacOS || Platform.isLinux;
  
  /// Helper method to reshape tensor data for TensorFlow models
  /// Reshapes a flat list into the proper shape needed by the model
  static List<List<List<List<double>>>> reshape4D(
    List<double> flatData, 
    int batchSize, 
    int height, 
    int width, 
    int channels
  ) {
    final result = List.generate(
      batchSize,
      (_) => List.generate(
        height,
        (_) => List.generate(
          width,
          (_) => List.generate(
            channels,
            (_) => 0.0,
          ),
        ),
      ),
    );
    
    int flatIndex = 0;
    for (int b = 0; b < batchSize; b++) {
      for (int h = 0; h < height; h++) {
        for (int w = 0; w < width; w++) {
          for (int c = 0; c < channels; c++) {
            if (flatIndex < flatData.length) {
              result[b][h][w][c] = flatData[flatIndex++];
            }
          }
        }
      }
    }
    
    return result;
  }
  
  /// Flattens a 4D nested list into a 1D list
  static List<double> flatten4D(List<List<List<List<double>>>> data) {
    final result = <double>[];
    
    for (final batch in data) {
      for (final height in batch) {
        for (final width in height) {
          result.addAll(width);
        }
      }
    }
    
    return result;
  }
}
