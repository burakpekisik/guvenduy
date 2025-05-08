from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class NotifiableClass(Base):
    """Sound classes that can trigger alerts"""
    __tablename__ = "notifiable_classes"
    
    id = Column(Integer, primary_key=True, index=True)
    class_name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(String(255), nullable=True)
    min_confidence = Column(Float, default=0.7, nullable=False)  # Minimum confidence to trigger an alert
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = relationship("User", backref="created_notifiable_classes")
    alerts = relationship("Alert", back_populates="alert_class")