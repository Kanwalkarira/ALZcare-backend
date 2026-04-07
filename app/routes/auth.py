"""
Authentication routes for user signup, login, token refresh, and profile.
"""
from fastapi import APIRouter, Depends, HTTPException, status  # type: ignore
from typing import Dict

from app.models.user import (  # type: ignore
    UserSignup,
    UserLogin,
    UserResponse,
    TokenResponse,
    TokenRefresh,
    UserInDB
)
from app.services.auth import auth_service  # type: ignore
from app.dependencies.auth import get_current_user  # type: ignore


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=Dict, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserSignup):
    """
    Register a new user.
    
    Request body:
    - email: Valid email address
    - password: Minimum 8 characters with uppercase, lowercase, and digit
    - role: One of "patient", "caregiver", "doctor"
    - name: User's full name
    
    Returns:
    - user: User profile data
    - tokens: Access and refresh tokens
    """
    try:
        user, tokens = await auth_service.register_user(user_data)
        
        return {
            "user": UserResponse(
                uid=user.uid,
                email=user.email,
                name=user.name,
                role=user.role,
                age=user.age,
                created_at=user.created_at,
                updated_at=user.updated_at
            ),
            "tokens": tokens
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.post("/login", response_model=Dict)
async def login(login_data: UserLogin):
    """
    Authenticate a user and return tokens.
    
    Request body:
    - email: User's email address
    - password: User's password
    
    Returns:
    - user: User profile data
    - tokens: Access and refresh tokens
    """
    try:
        user, tokens = await auth_service.authenticate_user(login_data)
        
        return {
            "user": UserResponse(
                uid=user.uid,
                email=user.email,
                name=user.name,
                role=user.role,
                age=user.age,
                created_at=user.created_at,
                updated_at=user.updated_at
            ),
            "tokens": tokens
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(token_data: TokenRefresh):
    """
    Refresh access token using a refresh token.
    
    Request body:
    - refresh_token: Valid refresh token
    
    Returns:
    - New access and refresh tokens
    """
    try:
        tokens = await auth_service.refresh_access_token(token_data.refresh_token)
        return tokens
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: UserInDB = Depends(get_current_user)):
    """
    Get current authenticated user's profile.
    
    Requires:
    - Valid access token in Authorization header
    
    Returns:
    - User profile data
    """
    return UserResponse(
        uid=current_user.uid,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        age=current_user.age,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "authentication"}
