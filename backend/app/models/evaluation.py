from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class Evaluation(Base):
    """Model for user evaluations of sound classifications"""
    __tablename__ = "evaluations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for backward compatibility
    device_id = Column(String(255), nullable=False)
    recording_date = Column(DateTime, nullable=False)
    recording_name = Column(String(255), nullable=False)
    detection_class = Column(String(100), nullable=False)
    detection_confidence = Column(Float, nullable=False)
    success = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="evaluations")