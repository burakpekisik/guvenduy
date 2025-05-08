from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class Prediction(Base):
    """Model for storing prediction results"""
    __tablename__ = "last_predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for guest predictions
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    highest_class = Column(String(100), nullable=False)
    highest_confidence = Column(Float, nullable=False)
    all_predictions = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="predictions")