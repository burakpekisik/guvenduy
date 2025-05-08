from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class LocationBase(BaseModel):
    """Base model for location data"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = Field(None, ge=0)

class UserLocationUpdate(LocationBase):
    """Model for updating user location"""
    pass

class NotifiableClassCreate(BaseModel):
    """Model for creating a notifiable sound class"""
    class_name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    min_confidence: float = Field(0.7, ge=0.0, le=1.0)

class NotifiableClassUpdate(BaseModel):
    """Model for updating a notifiable sound class"""
    description: Optional[str] = Field(None, max_length=255)
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None

class NotifiableClassResponse(BaseModel):
    """Response model for notifiable sound class"""
    id: int
    class_name: str
    description: Optional[str]
    min_confidence: float
    is_active: bool
    created_at: datetime
    
    class Config:
        orm_mode = True

class AlertCreate(BaseModel):
    """Model for creating an alert"""
    class_id: int
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    confidence: float = Field(..., ge=0.0, le=1.0)
    device_id: str

class AlertResponse(BaseModel):
    """Response model for an alert"""
    id: int
    class_id: int
    latitude: float
    longitude: float
    confidence: float
    device_id: str
    is_verified: bool
    created_at: datetime
    alert_class: NotifiableClassResponse
    distance_km: Optional[float] = None
    
    class Config:
        orm_mode = True

class AlertQueryParams(LocationBase):
    """Query parameters for getting nearby alerts"""
    radius_km: float = Field(1.0, gt=0)
    class_ids: Optional[List[int]] = None
    hours_ago: Optional[int] = Field(None, ge=0)