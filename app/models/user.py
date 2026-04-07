"""
Pydantic models for user data validation and serialization.
"""
from pydantic import BaseModel, EmailStr, Field, validator  # type: ignore
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User roles for role-based access control."""
    patient = "patient"
    caregiver = "caregiver"
    doctor = "doctor"
    admin = "admin"


class UserSignup(BaseModel):
    """User signup request model."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    role: UserRole
    name: str = Field(..., min_length=1, max_length=100)
    age: Optional[int] = Field(None, ge=0, le=150)
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v
    
    @validator('name')
    def validate_name(cls, v):
        """Validate name is not just whitespace."""
        if not v.strip():
            raise ValueError('Name cannot be empty or just whitespace')
        return v.strip()


class UserLogin(BaseModel):
    """User login request model."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User data response model (excludes sensitive data)."""
    uid: str
    email: str
    name: str
    role: str
    age: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """JWT token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class TokenRefresh(BaseModel):
    """Token refresh request model."""
    refresh_token: str


class UserInDB(BaseModel):
    """User model as stored in Firestore."""
    uid: str
    email: str
    name: str
    role: str
    age: Optional[int] = None
    hashed_password: str
    created_at: datetime
    updated_at: datetime
