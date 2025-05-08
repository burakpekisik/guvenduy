from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.models.alerts import (
    UserLocationUpdate, NotifiableClassCreate, NotifiableClassUpdate,
    NotifiableClassResponse, AlertCreate, AlertResponse, AlertQueryParams
)
from app.database import (
    get_db_session, User, NotifiableClass, Alert, 
    create_notifiable_class, get_notifiable_class_by_name, get_notifiable_class_by_id,
    get_active_notifiable_classes, update_notifiable_class, update_user_location, 
    create_alert, get_alerts_in_radius
)
from app.auth import get_current_active_user, check_admin_privilege

router = APIRouter(
    prefix="/alerts",
    tags=["alert-system"]
)

# Notifiable Classes Management (Admin only)
@router.post("/classes", response_model=NotifiableClassResponse, status_code=status.HTTP_201_CREATED)
async def create_new_notifiable_class(
    class_data: NotifiableClassCreate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(check_admin_privilege)
):
    """
    Create a new notifiable sound class (Admin only)
    
    This endpoint allows administrators to define which sound classes can trigger alerts.
    """
    # Check if class name already exists
    existing_class = get_notifiable_class_by_name(db, class_data.class_name)
    if existing_class:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sound class '{class_data.class_name}' is already defined as notifiable"
        )
    
    # Create the new notifiable class
    notifiable_class = create_notifiable_class(
        db=db,
        class_name=class_data.class_name,
        description=class_data.description,
        min_confidence=class_data.min_confidence,
        created_by=current_user.id
    )
    
    if not notifiable_class:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create notifiable class"
        )
    
    return notifiable_class

@router.get("/classes", response_model=List[NotifiableClassResponse])
async def get_notifiable_classes(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
    include_inactive: bool = False
):
    """
    Get all notifiable sound classes
    
    By default, only active classes are returned. Set include_inactive=true to get all classes.
    """
    if include_inactive and current_user.privilege != "admin" and current_user.privilege != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can view inactive classes"
        )
    
    if include_inactive:
        # For admins, get all classes
        classes = db.query(NotifiableClass).all()
    else:
        # For normal users, get only active classes
        classes = get_active_notifiable_classes(db)
    
    return classes

@router.get("/classes/{class_id}", response_model=NotifiableClassResponse)
async def get_notifiable_class(
    class_id: int,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific notifiable sound class by ID
    """
    notifiable_class = get_notifiable_class_by_id(db, class_id)
    
    if not notifiable_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notifiable class with ID {class_id} not found"
        )
    
    # Only admins can see inactive classes
    if not notifiable_class.is_active and current_user.privilege != "admin" and current_user.privilege != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This class is inactive and only viewable by admins"
        )
    
    return notifiable_class

@router.put("/classes/{class_id}", response_model=NotifiableClassResponse)
async def update_notifiable_class_endpoint(
    class_id: int,
    class_data: NotifiableClassUpdate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(check_admin_privilege)
):
    """
    Update a notifiable sound class (Admin only)
    """
    updated_class = update_notifiable_class(
        db=db,
        class_id=class_id,
        min_confidence=class_data.min_confidence,
        description=class_data.description,
        is_active=class_data.is_active
    )
    
    if not updated_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notifiable class with ID {class_id} not found"
        )
    
    return updated_class

# User location management
@router.post("/location", status_code=status.HTTP_200_OK)
async def update_location(
    location: UserLocationUpdate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update the current user's location
    
    This endpoint allows users to update their current geographical location,
    which is used for receiving relevant alerts.
    """
    user_location = update_user_location(
        db=db,
        user_id=current_user.id,
        latitude=location.latitude,
        longitude=location.longitude,
        accuracy=location.accuracy
    )
    
    if not user_location:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update location"
        )
    
    return {"status": "success", "message": "Location updated successfully"}

# Alert creation and querying
@router.post("/create", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_new_alert(
    alert_data: AlertCreate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new alert for a sound detection
    
    This endpoint allows users to create alerts for notifiable sound classes
    that they detect in their vicinity.
    """
    # Check if the notifiable class exists and is active
    notifiable_class = get_notifiable_class_by_id(db, alert_data.class_id)
    
    if not notifiable_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notifiable class with ID {alert_data.class_id} not found"
        )
    
    if not notifiable_class.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Notifiable class '{notifiable_class.class_name}' is currently inactive"
        )
    
    # Check if confidence meets the minimum threshold
    if alert_data.confidence < notifiable_class.min_confidence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Confidence ({alert_data.confidence}) is below the required threshold ({notifiable_class.min_confidence}) for this class"
        )
    
    # Set expiration time (default: 1 hour from now)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    # Create the alert
    alert = create_alert(
        db=db,
        user_id=current_user.id,
        class_id=alert_data.class_id,
        latitude=alert_data.latitude,
        longitude=alert_data.longitude,
        confidence=alert_data.confidence,
        device_id=alert_data.device_id,
        expires_at=expires_at
    )
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create alert"
        )
    
    # Return the created alert
    return alert

@router.get("/nearby", response_model=List[AlertResponse])
async def get_nearby_alerts(
    query: AlertQueryParams = Depends(),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get alerts in the vicinity of the specified location
    
    This endpoint returns alerts that are within the specified radius
    of the given coordinates. Useful for checking if there are any 
    recent alerts in the user's area.
    """
    alerts = get_alerts_in_radius(
        db=db,
        latitude=query.latitude,
        longitude=query.longitude,
        radius_km=query.radius_km,
        class_ids=query.class_ids,
        hours_ago=query.hours_ago
    )
    
    return alerts