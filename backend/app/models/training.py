from pydantic import BaseModel
from typing import Dict, List, Optional, Any

class TrainingRequest(BaseModel):
    """Request model for training a sound classification model"""
    class_names: List[str]
    output_model_name: Optional[str] = None
    epochs: Optional[int] = 100
    batch_size: Optional[int] = 8

class TrainingResponse(BaseModel):
    """Response model for training status and results"""
    status: str
    task_id: Optional[str] = None
    message: str
    details: Optional[Dict] = None