from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, UserPrivilege
from app.database import get_user_by_username, verify_password, get_db_session, User

# OAuth2 Password Bearer token setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# Token data model
class TokenData:
    def __init__(self, username: Optional[str] = None, privilege: Optional[str] = None):
        self.username = username
        self.privilege = privilege

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate a user with username and password
    """
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a new JWT access token
    """
    to_encode = data.copy()
    
    # Set expiration time
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    # Create JWT token
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(
    db: Session = Depends(get_db_session),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Get the current user from the JWT token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        
        if username is None:
            raise credentials_exception
        
        token_data = TokenData(
            username=username,
            privilege=payload.get("privilege")
        )
    except JWTError:
        raise credentials_exception
    
    # Get the user from the database
    user = get_user_by_username(db, token_data.username)
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Ensure that the current user is active
    """
    # Add any additional checks here (e.g., account disabled)
    return current_user

def check_admin_privilege(current_user: User = Depends(get_current_user)) -> User:
    """
    Check if the current user has admin privileges
    """
    if current_user.privilege != UserPrivilege.ADMIN and current_user.privilege != UserPrivilege.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action. Admin privileges required."
        )
    return current_user

def check_super_admin_privilege(current_user: User = Depends(get_current_user)) -> User:
    """
    Check if the current user has super admin privileges
    """
    if current_user.privilege != UserPrivilege.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action. Super admin privileges required."
        )
    return current_user