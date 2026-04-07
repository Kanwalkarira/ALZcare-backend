"""
JWT token generation and validation utilities.
Handles access and refresh tokens with expiration.
"""
import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional
from app.config import settings


class JWTHandler:
    """Handler for JWT token operations."""
    
    def __init__(self):
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
    
    def create_access_token(self, user_id: str, role: str) -> str:
        """
        Create a new access token.
        
        Args:
            user_id: User's unique identifier
            role: User's role
            
        Returns:
            Encoded JWT access token
        """
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        payload = {
            "sub": user_id,
            "role": role,
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, user_id: str) -> str:
        """
        Create a new refresh token.
        
        Args:
            user_id: User's unique identifier
            
        Returns:
            Encoded JWT refresh token
        """
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": expire,
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def decode_token(self, token: str) -> Optional[Dict]:
        """
        Decode and validate a JWT token.
        
        Args:
            token: JWT token to decode
            
        Returns:
            Decoded payload or None if invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def verify_access_token(self, token: str) -> Optional[Dict]:
        """
        Verify an access token.
        
        Args:
            token: Access token to verify
            
        Returns:
            Decoded payload or None if invalid
        """
        payload = self.decode_token(token)
        if payload and payload.get("type") == "access":
            return payload
        return None
    
    def verify_refresh_token(self, token: str) -> Optional[Dict]:
        """
        Verify a refresh token.
        
        Args:
            token: Refresh token to verify
            
        Returns:
            Decoded payload or None if invalid
        """
        payload = self.decode_token(token)
        if payload and payload.get("type") == "refresh":
            return payload
        return None
    
    def get_token_expiry_seconds(self) -> int:
        """Get access token expiry time in seconds."""
        return self.access_token_expire_minutes * 60


# Global JWT handler instance
jwt_handler = JWTHandler()
