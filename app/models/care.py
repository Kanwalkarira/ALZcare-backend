"""
Pydantic models for Clinical Notes (Doctor Suggestions & Caregiver Behavioral Notes).
"""
from pydantic import BaseModel, Field # type: ignore
from typing import Optional, List
from datetime import datetime


class SuggestionBase(BaseModel):
    """Base model for doctor suggestions."""
    suggestion_text: str = Field(..., description="The treatment suggestion text")


class SuggestionCreate(SuggestionBase):
    """Model for creating a suggestion."""
    pass


class SuggestionResponse(SuggestionBase):
    """Model for suggestion response."""
    suggestion_id: str
    doctor_id: str
    doctor_name: str
    attachments_urls: List[str] = []
    created_at: datetime
    
    class Config:
        from_attributes = True


class BehaviorNoteBase(BaseModel):
    """Base model for behavioral notes."""
    note_text: str = Field(..., description="The behavioral note text")


class BehaviorNoteCreate(BehaviorNoteBase):
    """Model for creating a behavioral note."""
    pass


class BehaviorNoteResponse(BehaviorNoteBase):
    """Model for behavioral note response."""
    note_id: str
    caregiver_id: str
    caregiver_name: str
    attachments_urls: List[str] = []
    created_at: datetime
    
    class Config:
        from_attributes = True

class ActivityLog(BaseModel):
    log_id: str
    patient_id: str
    activity_type: str
    description: str
    timestamp: datetime
    
    class Config:
        from_attributes = True
