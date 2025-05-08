from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime

class EvaluationRequest(BaseModel):
    """Request model for submitting a user evaluation"""
    device_id: str
    recording_date: str  # ISO format date-time string
    recording_name: str
    detection_class: str
    detection_confidence: float
    success: bool  # True for successful prediction, False for unsuccessful

class PredictionResponse(BaseModel):
    """Model for prediction response"""
    predictions: Dict[str, float]