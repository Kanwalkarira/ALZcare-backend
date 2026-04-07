"""
Configuration management using Pydantic Settings.
Loads environment variables and provides type-safe configuration.
"""
from pydantic_settings import BaseSettings  # type: ignore
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # JWT Configuration
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Firestore Configuration
    GOOGLE_APPLICATION_CREDENTIALS: str
    
    # Supabase Configuration
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_BUCKET: str = "alzcare-storage-prod"
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    
    # Environment
    ENVIRONMENT: str = "development"
    
    # SOS Configuration
    SOS_RATE_LIMIT_SECONDS: int = 60
    SOS_MAX_ALERTS_PER_HOUR: int = 10
    
    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS string into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
