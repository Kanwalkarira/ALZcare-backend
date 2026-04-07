"""
Authentication service handling user registration, login, and token management.
"""
import bcrypt
from typing import Optional, Tuple
from fastapi import HTTPException, status

from app.models.user import UserSignup, UserLogin, UserInDB, TokenResponse
from app.services.firestore import firestore_service
from app.services.jwt_handler import jwt_handler


class AuthService:
    """Service for authentication operations."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password to compare against
            
        Returns:
            True if password matches, False otherwise
        """
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    
    async def register_user(self, user_data: UserSignup) -> Tuple[UserInDB, TokenResponse]:
        """
        Register a new user.
        
        Args:
            user_data: User signup data
            
        Returns:
            Tuple of (user document, token response)
            
        Raises:
            HTTPException: If email already exists
        """
        # Check if user already exists
        existing_user = await firestore_service.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = self.hash_password(user_data.password)
        
        # Create user in Firestore
        user_doc = await firestore_service.create_user(
            email=user_data.email,
            name=user_data.name,
            role=user_data.role.value,
            hashed_password=hashed_password,
            age=user_data.age
        )
        
        # Create tokens
        access_token = jwt_handler.create_access_token(user_doc["uid"], user_doc["role"])
        refresh_token = jwt_handler.create_refresh_token(user_doc["uid"])
        
        user_in_db = UserInDB(**user_doc)
        token_response = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=jwt_handler.get_token_expiry_seconds()
        )
        
        return user_in_db, token_response
    
    async def authenticate_user(self, login_data: UserLogin) -> Tuple[UserInDB, TokenResponse]:
        """
        Authenticate a user and generate tokens.
        
        Args:
            login_data: User login credentials
            
        Returns:
            Tuple of (user document, token response)
            
        Raises:
            HTTPException: If credentials are invalid
        """
        # Get user by email
        user_doc = await firestore_service.get_user_by_email(login_data.email)
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Verify password
        if not self.verify_password(login_data.password, user_doc["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Create tokens
        access_token = jwt_handler.create_access_token(user_doc["uid"], user_doc["role"])
        refresh_token = jwt_handler.create_refresh_token(user_doc["uid"])
        
        user_in_db = UserInDB(**user_doc)
        token_response = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=jwt_handler.get_token_expiry_seconds()
        )
        
        return user_in_db, token_response
    
    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """
        Generate a new access token using a refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New token response
            
        Raises:
            HTTPException: If refresh token is invalid
        """
        # Verify refresh token
        payload = jwt_handler.verify_refresh_token(refresh_token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        # Get user
        user_id = payload.get("sub")
        user_doc = await firestore_service.get_user_by_uid(user_id)
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Create new tokens
        access_token = jwt_handler.create_access_token(user_doc["uid"], user_doc["role"])
        new_refresh_token = jwt_handler.create_refresh_token(user_doc["uid"])
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=jwt_handler.get_token_expiry_seconds()
        )


# Global auth service instance
auth_service = AuthService()
