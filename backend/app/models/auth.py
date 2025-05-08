from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Dict, List, Optional, Any

class Token(BaseModel):
    """JWT token response model"""
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    """User registration model"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserResponse(BaseModel):
    """User information response model"""
    id: int
    username: str
    email: str
    privilege: str
    created_at: datetime

class UserPrivilegeUpdate(BaseModel):
    """User privilege update model"""
    privilege: str = Field(..., description="User privilege level")

class UserUpdate(BaseModel):
    """User update model - for updating username, email, and password"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6)

class UserDeleteResponse(BaseModel):
    """Response model for user deletion"""
    success: bool
    message: str
    user_id: int