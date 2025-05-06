import 'package:flutter/material.dart';
import '../models/sound_detection_result.dart';
import '../services/evaluation_service.dart';

class SwipeableDetectionTile extends StatefulWidget {
  final SoundDetectionResult result;
  final VoidCallback? onEvaluationSubmitted;

  const SwipeableDetectionTile({
    Key? key,
    required this.result,
    this.onEvaluationSubmitted,
  }) : super(key: key);

  @override
  State<SwipeableDetectionTile> createState() => _SwipeableDetectionTileState();
}

class _SwipeableDetectionTileState extends State<SwipeableDetectionTile> {
  final EvaluationService _evaluationService = EvaluationService();
  bool _isEvaluating = false;
  String? _evaluationStatus;

  @override
  Widget build(BuildContext context) {
    return Dismissible(
      key: Key('${widget.result.timestamp.millisecondsSinceEpoch}-${widget.result.soundType}'),
      direction: DismissDirection.endToStart, // Right to left only
      confirmDismiss: (direction) async {
        // Show evaluation options
        await _showEvaluationOptions();
        // Never actually dismiss the item
        return false;
      },
      background: Container(
        color: Colors.red,
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        child: const Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            Text(
              'Evaluate',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
            SizedBox(width: 8),
            Icon(Icons.rate_review, color: Colors.white),
          ],
        ),
      ),
      child: Card(
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        child: Padding(
          padding: const EdgeInsets.all(12.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Status indicator if evaluating
              if (_isEvaluating || _evaluationStatus != null)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(6),
                  margin: const EdgeInsets.only(bottom: 8),
                  decoration: BoxDecoration(
                    color: _evaluationStatus?.contains('successfully') == true
                        ? Colors.green.shade100
                        : _evaluationStatus?.contains('Error') == true || _evaluationStatus?.contains('Failed') == true
                            ? Colors.red.shade100
                            : Colors.blue.shade100,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Row(
                    children: [
                      _isEvaluating
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                              ),
                            )
                          : Icon(
                              _evaluationStatus?.contains('successfully') == true
                                  ? Icons.check_circle
                                  : _evaluationStatus?.contains('Error') == true || _evaluationStatus?.contains('Failed') == true
                                      ? Icons.error
                                      : Icons.info,
                              size: 16,
                              color: _evaluationStatus?.contains('successfully') == true
                                  ? Colors.green
                                  : _evaluationStatus?.contains('Error') == true || _evaluationStatus?.contains('Failed') == true
                                      ? Colors.red
                                      : Colors.blue,
                            ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _isEvaluating
                              ? 'Submitting evaluation...'
                              : _evaluationStatus ?? '',
                          style: TextStyle(
                            fontSize: 12,
                            color: _evaluationStatus?.contains('successfully') == true
                                ? Colors.green.shade700
                                : _evaluationStatus?.contains('Error') == true || _evaluationStatus?.contains('Failed') == true
                                    ? Colors.red.shade700
                                    : Colors.blue.shade700,
                          ),
                        ),
                      ),
                      // Clear button for evaluation status
                      if (_evaluationStatus != null)
                        IconButton(
                          icon: const Icon(Icons.close, size: 14),
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(),
                          onPressed: () {
                            setState(() {
                              _evaluationStatus = null;
                            });
                          },
                        ),
                    ],
                  ),
                ),
                
              Row(
                children: [
                  _getIconForSoundType(widget.result.soundType),
                  const SizedBox(width: 12),
                  Text(
                    widget.result.soundType.toUpperCase(),
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  
                  // For low confidence results, show original type in parentheses
                  if (widget.result.isLowConfidence) ...[
                    const SizedBox(width: 6),
                    Text(
                      '(${widget.result.originalSoundType})',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.normal,
                        color: Colors.grey.shade700,
                        fontStyle: FontStyle.italic
                      ),
                    ),
                  ],
                  
                  const Spacer(),
                  Text(
                    '${(widget.result.confidence * 100).toStringAsFixed(1)}%',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: _getConfidenceColor(widget.result.confidence),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              
              // Show a message for low confidence results
              if (widget.result.isLowConfidence)
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade200,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    'Low confidence detection. Original classification: ${widget.result.originalSoundType}',
                    style: TextStyle(
                      fontSize: 13,
                      color: Colors.grey.shade700,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ),
                
              Text(
                'Detected at: ${_formatDateTime(widget.result.timestamp)}',
                style: TextStyle(
                  fontSize: 14, 
                  color: Colors.grey.shade700,
                ),
              ),
              
              // Hint text for evaluation
              Padding(
                padding: const EdgeInsets.only(top: 8.0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    Icon(
                      Icons.swipe_left,
                      size: 14,
                      color: Colors.grey.shade500,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'Swipe to evaluate',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey.shade500,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ],
                ),
              ),
              
              // Show all predictions if available
              if (widget.result.allPredictions != null) ...[
                const SizedBox(height: 8),
                const Text(
                  'All predictions:',
                  style: TextStyle(fontSize: 14, fontStyle: FontStyle.italic),
                ),
                ...widget.result.allPredictions!.entries.map((entry) => 
                  Padding(
                    padding: const EdgeInsets.only(left: 12.0, top: 4.0),
                    child: Text(
                      '${entry.key}: ${(entry.value * 100).toStringAsFixed(1)}%',
                      style: TextStyle(
                        fontSize: 13,
                        color: Colors.grey.shade800,
                      ),
                    ),
                  ),
                ).toList(),
              ],
            ],
          ),
        ),
      ),
    );
  }
  
  Future<void> _showEvaluationOptions() async {
    return showModalBottomSheet<void>(
      context: context,
      builder: (BuildContext context) {
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              const Padding(
                padding: EdgeInsets.all(16.0),
                child: Text(
                  'Evaluate Detection Result',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const Divider(),
              ListTile(
                leading: const Icon(Icons.check_circle, color: Colors.green),
                title: const Text('Successful'),
                subtitle: const Text('The sound type was correctly identified'),
                onTap: () {
                  Navigator.pop(context);
                  _submitEvaluation(true);
                },
              ),
              ListTile(
                leading: const Icon(Icons.cancel, color: Colors.red),
                title: const Text('Unsuccessful'),
                subtitle: const Text('The sound type was incorrectly identified'),
                onTap: () {
                  Navigator.pop(context);
                  _submitEvaluation(false);
                },
              ),
              const SizedBox(height: 16),
            ],
          ),
        );
      },
    );
  }
  
  Future<void> _submitEvaluation(bool success) async {
    if (_isEvaluating) return;
    
    setState(() {
      _isEvaluating = true;
      _evaluationStatus = null;
    });
    
    try {
      final submitted = await _evaluationService.submitEvaluation(widget.result, success);
      
      setState(() {
        _isEvaluating = false;
        _evaluationStatus = submitted 
            ? 'Evaluation submitted successfully'
            : 'Failed to submit evaluation';
      });
      
      if (submitted && widget.onEvaluationSubmitted != null) {
        widget.onEvaluationSubmitted!();
      }
    } catch (e) {
      setState(() {
        _isEvaluating = false;
        _evaluationStatus = 'Error: $e';
      });
    }
  }

  Widget _getIconForSoundType(String soundType) {
    switch (soundType.toLowerCase()) {
      case 'emergency_vehicle':
        return const Icon(Icons.emergency, color: Colors.red, size: 30);
      case 'horn':
        return const Icon(Icons.volume_up, color: Colors.orange, size: 30);
      case 'alarm_clock':
        return const Icon(Icons.alarm, color: Colors.blue, size: 30);
      case 'baby':
        return const Icon(Icons.child_care, color: Colors.pink, size: 30);
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
        return const Icon(Icons.question_mark, color: Colors.grey, size: 30);
    }
  }
  
  Color _getConfidenceColor(double confidence) {
    if (confidence > 0.8) {
      return Colors.green;
    } else if (confidence > 0.5) {
      return Colors.orange;
    } else {
      return Colors.red;
    }
  }

  String _formatDateTime(DateTime dateTime) {
    return '${_padZero(dateTime.hour)}:${_padZero(dateTime.minute)}:${_padZero(dateTime.second)}';
  }
  
  String _padZero(int number) {
    return number.toString().padLeft(2, '0');
  }
}