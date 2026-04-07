"""
FastAPI dependency injection for authentication and authorization.
"""
from fastapi import Depends, HTTPException, status  # type: ignore
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials  # type: ignore
from typing import Optional, List, Dict, Any

from app.services.jwt_handler import jwt_handler  # type: ignore
from app.services.firestore import firestore_service  # type: ignore
from app.models.user import UserInDB  # type: ignore


# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInDB:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Authorization credentials
        
    Returns:
        Current user data
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Verify access token
    payload = jwt_handler.verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Get user from database
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"}
        )
        
    user_doc = await firestore_service.get_user_by_uid(str(user_id))
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    try:
        return UserInDB(**user_doc)
    except Exception as e:
        print(f"Error validating user data: {e}")
        # Return internal error if data consistency fails, or 401 to force re-login?
        # Better to fail safely
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"User data validation error: {str(e)}"
        )


def require_role(allowed_roles: List[str]):
    """
    Dependency factory for role-based access control.
    
    Args:
        allowed_roles: List of roles that are allowed to access the endpoint
        
    Returns:
        Dependency function that checks user role
        
    Example:
        @app.get("/admin", dependencies=[Depends(require_role(["admin"]))])
    """
    async def role_checker(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
            )
        return current_user
    
    return role_checker


# Convenience dependencies for specific roles
require_admin = require_role(["admin"])
require_doctor = require_role(["admin", "doctor"])
require_caregiver = require_role(["admin", "doctor", "caregiver"])
