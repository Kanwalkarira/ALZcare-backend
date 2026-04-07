"""
Pydantic models for SOS alert system.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from enum import Enum


class AlertStatus(str, Enum):
    """SOS alert status."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class LocationData(BaseModel):
    """Geographic location data."""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    accuracy: Optional[float] = Field(None, description="Location accuracy in meters")
    
    @validator('latitude')
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError('Latitude must be between -90 and 90')
        return v
    
    @validator('longitude')
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError('Longitude must be between -180 and 180')
        return v


class SOSTriggerRequest(BaseModel):
    """Request model for triggering SOS alert."""
    location: LocationData = Field(..., description="Patient's current location (REQUIRED)")
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes about the emergency")


class SOSAlertResponse(BaseModel):
    """Response model for SOS alert."""
    alert_id: str
    patient_id: str
    patient_name: str
    timestamp: datetime
    location: LocationData
    status: AlertStatus
    notes: Optional[str] = None
    caregivers_notified: int = Field(..., description="Number of caregivers notified")


class SOSAlert(BaseModel):
    """Database model for SOS alert."""
    alert_id: str
    patient_id: str
    patient_name: str
    patient_email: str
    timestamp: datetime
    location: LocationData
    status: AlertStatus
    notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    created_at: datetime


class SOSAlertUpdate(BaseModel):
    """Model for updating SOS alert status."""
    status: AlertStatus
    notes: Optional[str] = Field(None, max_length=500)


class NotificationRecord(BaseModel):
    """Model for notification records."""
    notification_id: str
    alert_id: str
    recipient_id: str
    recipient_name: str
    recipient_email: str
    sent_at: datetime
    status: str  # "sent", "delivered", "failed"
    fcm_message_id: Optional[str] = None
    error_message: Optional[str] = None


class CaregiverInfo(BaseModel):
    """Model for caregiver information."""
    caregiver_id: str
    caregiver_name: str
    caregiver_email: str
    relationship: Optional[str] = None
    fcm_token: Optional[str] = None
    added_at: datetime
