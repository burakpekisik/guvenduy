import os
import logging
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker, Session
from typing import List, Optional, Dict, Any
from passlib.context import CryptContext
from math import radians, cos, sin, asin, sqrt

from app.config import DATABASE_URL, UserPrivilege
from app.models import (
    Base, User, Evaluation, Prediction, NotifiableClass, UserLocation, Alert
)

# Setup logging
logger = logging.getLogger("sound-api")

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database initialization
def init_database():
    """Initialize the database and create tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully")
        
        # Create default admin user if no users exist
        db = get_db()
        try:
            user_count = db.query(User).count()
            if user_count == 0:
                create_default_admin(db)
            db.close()
        except Exception as e:
            db.close()
            logger.error(f"Failed to create default admin: {str(e)}")
                
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        return False

def create_default_admin(db: Session):
    """Create a default admin user"""
    try:
        default_admin = User(
            username="admin",
            email="admin@example.com",
            hashed_password=pwd_context.hash("admin123"),  # Change in production
            privilege=UserPrivilege.ADMIN
        )
        db.add(default_admin)
        db.commit()
        logger.info("Default admin user created")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create default admin: {str(e)}")

# Database session context manager
def get_db_session():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Database context helper for non-dependency contexts
def get_db():
    """Get database session as a regular function (not a generator)"""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db.close()
        raise e

# User operations
def create_user(db: Session, username: str, email: str, password: str, privilege: str = UserPrivilege.USER) -> Optional[User]:
    """Create a new user"""
    try:
        user = User(
            username=username,
            email=email,
            hashed_password=pwd_context.hash(password),
            privilege=privilege
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create user: {str(e)}")
        return None

def update_user(db: Session, user_id: int, username: Optional[str] = None, 
               email: Optional[str] = None, password: Optional[str] = None) -> Optional[User]:
    """Update a user's information"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
            
        # Update username if provided and different
        if username is not None and username != user.username:
            # Check if new username already exists
            existing_user = get_user_by_username(db, username)
            if existing_user and existing_user.id != user_id:
                raise ValueError("Username already exists")
            user.username = username
            
        # Update email if provided and different
        if email is not None and email != user.email:
            # Check if new email already exists
            existing_user = get_user_by_email(db, email)
            if existing_user and existing_user.id != user_id:
                raise ValueError("Email already exists")
            user.email = email
            
        # Update password if provided
        if password is not None:
            user.hashed_password = pwd_context.hash(password)
            
        db.commit()
        db.refresh(user)
        logger.info(f"Updated user: {user.username}")
        return user
    except ValueError as ve:
        db.rollback()
        logger.error(f"Validation error updating user: {str(ve)}")
        raise ve
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update user: {str(e)}")
        return None

def delete_user(db: Session, user_id: int) -> bool:
    """Delete a user"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
            
        # You might want to handle cascading deletes depending on your model relationships
        db.delete(user)
        db.commit()
        logger.info(f"Deleted user: {user.username}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete user: {str(e)}")
        return False

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username"""
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hashed password"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

# Evaluation operations
def add_evaluation(db: Session, user_id: Optional[int], device_id: str, recording_date: datetime, 
                  recording_name: str, detection_class: str, detection_confidence: float, success: bool) -> Optional[Evaluation]:
    """Add a user evaluation to the database"""
    try:
        evaluation = Evaluation(
            user_id=user_id,
            device_id=device_id,
            recording_date=recording_date,
            recording_name=recording_name,
            detection_class=detection_class,
            detection_confidence=detection_confidence,
            success=success
        )
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)
        logger.info(f"Added evaluation for {recording_name} with success={success}")
        return evaluation
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to add evaluation: {str(e)}")
        return None

def get_evaluation_stats(db: Session) -> Optional[Dict[str, Any]]:
    """Get statistics about evaluations"""
    try:
        # Get total evaluations count
        total_evaluations = db.query(func.count(Evaluation.id)).scalar() or 0
        
        # Get successful evaluations count
        successful_evaluations = db.query(func.count(Evaluation.id)).filter(Evaluation.success == True).scalar() or 0
        
        # Get unsuccessful evaluations count
        unsuccessful_evaluations = db.query(func.count(Evaluation.id)).filter(Evaluation.success == False).scalar() or 0
        
        # Calculate success rate
        overall_success_rate = successful_evaluations / total_evaluations if total_evaluations > 0 else 0
        
        # Get average confidence
        avg_confidence = db.query(func.avg(Evaluation.detection_confidence)).scalar() or 0.0
        
        # Get distribution by class
        class_distribution_query = db.query(
            Evaluation.detection_class.label("class_name"),
            func.count(Evaluation.id).label("count")
        ).group_by(Evaluation.detection_class).order_by(func.count(Evaluation.id).desc())
        
        class_distribution = []
        for row in class_distribution_query:
            class_distribution.append({
                "class_name": row.class_name,
                "count": row.count
            })
        
        # Get success rate by class
        class_success_rates = []
        for class_item in class_distribution:
            class_name = class_item["class_name"]
            
            # Get total count for this class
            total_for_class = class_item["count"]
            
            # Get successful count for this class
            successful_for_class = db.query(func.count(Evaluation.id))\
                .filter(Evaluation.detection_class == class_name)\
                .filter(Evaluation.success == True)\
                .scalar() or 0
            
            # Calculate success rate
            success_rate = successful_for_class / total_for_class if total_for_class > 0 else 0
            
            class_success_rates.append({
                "class_name": class_name,
                "success_rate": success_rate,
                "total": total_for_class,
                "successful": successful_for_class
            })
        
        # Sort by success rate descending
        class_success_rates.sort(key=lambda x: x["success_rate"], reverse=True)
        
        return {
            "total_evaluations": total_evaluations,
            "overall_success_rate": overall_success_rate,
            "avg_confidence": avg_confidence,
            "class_distribution": class_distribution,
            "class_success_rates": class_success_rates
        }
    except Exception as e:
        logger.error(f"Failed to get evaluation stats: {str(e)}")
        return None

# Prediction operations
def add_prediction(db: Session, user_id: Optional[int], file_name: str, file_path: str, 
                  highest_class: str, highest_confidence: float, all_predictions: Dict) -> Optional[Prediction]:
    """Add a prediction to the database and maintain only the last 100 predictions"""
    try:
        # Convert predictions dict to JSON string if needed
        prediction = Prediction(
            user_id=user_id,
            file_name=file_name,
            file_path=file_path,
            highest_class=highest_class,
            highest_confidence=highest_confidence,
            all_predictions=all_predictions
        )
        db.add(prediction)
        
        # Delete older predictions to keep only the latest 100
        subquery = db.query(Prediction.id).order_by(Prediction.created_at.desc()).limit(100).subquery()
        db.query(Prediction).filter(~Prediction.id.in_(subquery)).delete(synchronize_session=False)
        
        db.commit()
        db.refresh(prediction)
        logger.info(f"Added prediction for {file_name}")
        return prediction
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to add prediction: {str(e)}")
        return None

def get_latest_predictions(db: Session, limit: int = 100) -> List[Dict[str, Any]]:
    """Get the latest predictions from the database"""
    try:
        # Query only the columns we know exist
        predictions = db.query(Prediction).order_by(Prediction.created_at.desc()).limit(limit).all()
        
        # Convert SQLAlchemy objects to dictionaries
        result = []
        for pred in predictions:
            pred_dict = {
                "id": pred.id,
                "file_name": pred.file_name,
                "file_path": pred.file_path,
                "highest_class": pred.highest_class,
                "highest_confidence": pred.highest_confidence,
                "created_at": pred.created_at
            }
            # Only add user_id if it exists on the model
            if hasattr(pred, 'user_id'):
                pred_dict["user_id"] = pred.user_id
            
            # Handle all_predictions specially - make sure it's a dict
            if hasattr(pred, 'all_predictions'):
                if isinstance(pred.all_predictions, dict):
                    pred_dict["all_predictions"] = pred.all_predictions
                else:
                    # Try to convert from JSON string if needed
                    try:
                        import json
                        pred_dict["all_predictions"] = json.loads(pred.all_predictions)
                    except:
                        pred_dict["all_predictions"] = {}
            
            result.append(pred_dict)
        
        return result
    except Exception as e:
        logger.error(f"Failed to get latest predictions: {str(e)}")
        
        # Fallback query if there's a schema mismatch
        try:
            # Try a more selective query that excludes potentially problematic columns
            rows = db.query(
                Prediction.id,
                Prediction.file_name,
                Prediction.file_path,
                Prediction.highest_class,
                Prediction.highest_confidence,
                Prediction.created_at
            ).order_by(Prediction.created_at.desc()).limit(limit).all()
            
            # Convert the results to dictionaries
            result = []
            for row in rows:
                # Create a dictionary from the row
                pred_dict = {
                    "id": row.id,
                    "file_name": row.file_name, 
                    "file_path": row.file_path,
                    "highest_class": row.highest_class,
                    "highest_confidence": row.highest_confidence,
                    "created_at": row.created_at
                }
                result.append(pred_dict)
            
            logger.info("Successfully retrieved predictions with selective query")
            return result
        except Exception as fallback_error:
            logger.error(f"Fallback prediction query also failed: {str(fallback_error)}")
            return []

# Notifiable class operations
def create_notifiable_class(db: Session, class_name: str, description: Optional[str], 
                          min_confidence: float, created_by: Optional[int]) -> Optional[NotifiableClass]:
    """Create a new notifiable sound class"""
    try:
        notifiable_class = NotifiableClass(
            class_name=class_name,
            description=description,
            min_confidence=min_confidence,
            created_by=created_by
        )
        db.add(notifiable_class)
        db.commit()
        db.refresh(notifiable_class)
        logger.info(f"Created notifiable class: {class_name}")
        return notifiable_class
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create notifiable class: {str(e)}")
        return None

def get_notifiable_class_by_name(db: Session, class_name: str) -> Optional[NotifiableClass]:
    """Get a notifiable class by name"""
    return db.query(NotifiableClass).filter(NotifiableClass.class_name == class_name).first()

def get_notifiable_class_by_id(db: Session, class_id: int) -> Optional[NotifiableClass]:
    """Get a notifiable class by ID"""
    return db.query(NotifiableClass).filter(NotifiableClass.id == class_id).first()

def get_active_notifiable_classes(db: Session) -> List[NotifiableClass]:
    """Get all active notifiable classes"""
    return db.query(NotifiableClass).filter(NotifiableClass.is_active == True).all()

def update_notifiable_class(db: Session, class_id: int, min_confidence: Optional[float] = None,
                          description: Optional[str] = None, is_active: Optional[bool] = None) -> Optional[NotifiableClass]:
    """Update a notifiable class"""
    try:
        notifiable_class = get_notifiable_class_by_id(db, class_id)
        if not notifiable_class:
            return None
            
        if min_confidence is not None:
            notifiable_class.min_confidence = min_confidence
        if description is not None:
            notifiable_class.description = description
        if is_active is not None:
            notifiable_class.is_active = is_active
            
        db.commit()
        db.refresh(notifiable_class)
        logger.info(f"Updated notifiable class: {notifiable_class.class_name}")
        return notifiable_class
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update notifiable class: {str(e)}")
        return None

# User location operations
def update_user_location(db: Session, user_id: int, latitude: float, longitude: float, accuracy: Optional[float] = None) -> Optional[UserLocation]:
    """Update or create a user's location"""
    try:
        # Check if location exists
        location = db.query(UserLocation).filter(UserLocation.user_id == user_id).first()
        
        if location:
            # Update existing location
            location.latitude = latitude
            location.longitude = longitude
            if accuracy is not None:
                location.accuracy = accuracy
        else:
            # Create new location
            location = UserLocation(
                user_id=user_id,
                latitude=latitude,
                longitude=longitude,
                accuracy=accuracy
            )
            db.add(location)
            
        db.commit()
        db.refresh(location)
        logger.info(f"Updated location for user_id: {user_id}")
        return location
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update user location: {str(e)}")
        return None

def get_user_location(db: Session, user_id: int) -> Optional[UserLocation]:
    """Get a user's last known location"""
    return db.query(UserLocation).filter(UserLocation.user_id == user_id).first()

# Alert operations
def create_alert(db: Session, user_id: Optional[int], class_id: int, latitude: float, longitude: float,
                confidence: float, device_id: str, expires_at: Optional[datetime] = None) -> Optional[Alert]:
    """Create a new alert"""
    try:
        alert = Alert(
            user_id=user_id,
            class_id=class_id,
            latitude=latitude,
            longitude=longitude,
            confidence=confidence,
            device_id=device_id,
            expires_at=expires_at
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        logger.info(f"Created alert for class_id: {class_id}")
        return alert
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create alert: {str(e)}")
        return None

def verify_alert(db: Session, alert_id: int) -> Optional[Alert]:
    """Mark an alert as verified"""
    try:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return None
            
        alert.is_verified = True
        db.commit()
        db.refresh(alert)
        logger.info(f"Verified alert: {alert_id}")
        return alert
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to verify alert: {str(e)}")
        return None

def get_alerts_in_radius(db: Session, latitude: float, longitude: float, radius_km: float, 
                        class_ids: Optional[List[int]] = None, hours_ago: Optional[int] = None) -> List[Alert]:
    """
    Get alerts within a radius of a point
    
    Uses the Haversine formula to calculate distance between coordinates
    """
    try:
        # Convert radius from km to degrees (approximate)
        # 1 degree of latitude is approximately 111 km (varying slightly with latitude)
        radius_deg = radius_km / 111.0
        
        # Build the base query
        query = db.query(Alert)
        
        # Apply time filter if specified
        if hours_ago is not None:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_ago)
            query = query.filter(Alert.created_at >= cutoff_time)
        
        # Apply class filter if specified
        if class_ids:
            query = query.filter(Alert.class_id.in_(class_ids))
        
        # Apply radius filter using approximate bounding box for efficiency
        query = query.filter(
            Alert.latitude >= latitude - radius_deg,
            Alert.latitude <= latitude + radius_deg,
            Alert.longitude >= longitude - radius_deg,
            Alert.longitude <= longitude + radius_deg
        )
        
        # Get potential matches
        potential_matches = query.all()
        
        # Filter more precisely using Haversine formula
        results = []
        for alert in potential_matches:
            distance = calculate_distance(latitude, longitude, alert.latitude, alert.longitude)
            if distance <= radius_km:
                # Add distance information to the alert object
                setattr(alert, 'distance_km', distance)
                results.append(alert)
        
        # Sort by distance
        results.sort(key=lambda x: getattr(x, 'distance_km'))
        return results
    except Exception as e:
        logger.error(f"Failed to get alerts in radius: {str(e)}")
        return []

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r