"""
Pydantic models for Mood Tracking.
"""
from pydantic import BaseModel, Field # type: ignore
from typing import Optional, Dict
from datetime import datetime


class MoodBase(BaseModel):
    """Base mood model."""
    mood_emoji: str = Field(..., description="Emoji representing the mood (e.g., 😊, 😔)")
    note: Optional[str] = Field(None, description="Optional note about the mood")


class MoodCreate(MoodBase):
    """Model for creating a new mood log."""
    pass


class MoodResponse(MoodBase):
    """Model for mood log response."""
    log_id: str
    patient_id: str
    timestamp: datetime
    
    class Config:
        from_attributes = True


class MoodStats(BaseModel):
    """Model for mood statistics."""
    period: str = Field(..., description="Time period (7_days, 30_days)")
    counts: Dict[str, int] = Field(..., description="Count of each mood emoji")
    start_date: datetime
    end_date: datetime
