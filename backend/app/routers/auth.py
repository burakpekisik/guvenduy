from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from sqlalchemy.orm import Session
import logging

from app.models.auth import Token, UserCreate, UserResponse, UserPrivilegeUpdate, UserUpdate, UserDeleteResponse
from app.auth import authenticate_user, create_access_token, get_current_active_user, check_admin_privilege
from app.database import get_db_session, User, get_user_by_username, get_user_by_email, get_user_by_id, create_user, update_user, delete_user
from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, UserPrivilege

router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)

logger = logging.getLogger("sound-api")

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    database: Session = Depends(get_db_session)
):
    """
    Authenticate user and provide JWT token
    
    This endpoint follows the OAuth2 password flow, accepting a username and password
    and returning a JWT token if authentication is successful.
    """
    # Authenticate user
    user = authenticate_user(database, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token with user claims
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "privilege": user.privilege}, 
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    database: Session = Depends(get_db_session)
):
    """
    Register a new user
    
    This endpoint allows new users to register with a username, email, and password.
    Passwords are hashed before storage.
    """
    # Check if username already exists
    db_user = get_user_by_username(database, user_data.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    db_user = get_user_by_email(database, user_data.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = create_user(
        db=database,
        username=user_data.username,
        email=user_data.email,
        password=user_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )
    
    return user

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    Get current user profile
    
    This endpoint returns the profile information of the authenticated user.
    """
    return current_user

@router.get("/users/{user_id}", response_model=UserResponse)
async def read_user(
    user_id: int,
    database: Session = Depends(get_db_session),
    current_user: User = Depends(check_admin_privilege)
):
    """
    Get user by ID (admin only)
    
    This endpoint allows administrators to retrieve user information by ID.
    """
    user = get_user_by_id(database, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.get("/users", response_model=list[UserResponse])
async def get_all_users(
    database: Session = Depends(get_db_session),
    current_user: User = Depends(check_admin_privilege)
):
    """
    Get all users (admin only)
    
    This endpoint allows administrators to retrieve a list of all users.
    """
    try:
        users = database.query(User).all()
        return users
    except Exception as e:
        logger.error(f"Error retrieving users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving users: {str(e)}"
        )

@router.put("/users/{user_id}/privilege", response_model=UserResponse)
async def update_user_privilege(
    user_id: int,
    privilege_data: UserPrivilegeUpdate,
    database: Session = Depends(get_db_session),
    current_user: User = Depends(check_admin_privilege)
):
    """
    Update user privilege (admin only)
    
    This endpoint allows administrators to update the privilege level of a user.
    """
    # Check if privilege is valid
    if privilege_data.privilege not in [UserPrivilege.USER, UserPrivilege.ADMIN, UserPrivilege.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid privilege level: {privilege_data.privilege}"
        )
    
    # Only super_admin can create other admins
    if (privilege_data.privilege == UserPrivilege.ADMIN or privilege_data.privilege == UserPrivilege.SUPER_ADMIN) and \
       current_user.privilege != UserPrivilege.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can create or modify admin accounts"
        )
    
    user = get_user_by_id(database, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user privilege
    user.privilege = privilege_data.privilege
    database.commit()
    database.refresh(user)
    
    return user

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user_info(
    user_id: int,
    user_data: UserUpdate,
    database: Session = Depends(get_db_session),
    current_user: User = Depends(check_admin_privilege)
):
    """
    Update user information (admin only)
    
    This endpoint allows administrators to update user information including username, email, and password.
    """
    try:
        user = get_user_by_id(database, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Block updating super_admin account by normal admin
        if user.privilege == UserPrivilege.SUPER_ADMIN and current_user.privilege != UserPrivilege.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admins can modify super admin accounts"
            )
            
        updated_user = update_user(
            db=database,
            user_id=user_id,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user information"
            )
        
        return updated_user
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}"
        )

@router.delete("/users/{user_id}", response_model=UserDeleteResponse)
async def delete_user_account(
    user_id: int,
    database: Session = Depends(get_db_session),
    current_user: User = Depends(check_admin_privilege)
):
    """
    Delete a user (admin only)
    
    This endpoint allows administrators to delete user accounts.
    """
    # Check if user exists
    user = get_user_by_id(database, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Block deleting super_admin account by normal admin
    if user.privilege == UserPrivilege.SUPER_ADMIN and current_user.privilege != UserPrivilege.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can delete super admin accounts"
        )
    
    # Prevent admin from deleting their own account
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account"
        )
    
    success = delete_user(database, user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user account"
        )
    
    return UserDeleteResponse(
        success=True,
        message=f"User '{user.username}' deleted successfully",
        user_id=user_id
    )