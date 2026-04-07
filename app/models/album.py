"""
Pydantic models for Family Album.
"""
from pydantic import BaseModel, Field # type: ignore
from typing import Optional
from datetime import datetime


class AlbumEntryBase(BaseModel):
    """Base model for album entry metadata."""
    person_name: str = Field(..., description="Name of the person in the photo")
    description: Optional[str] = Field(None, description="Optional description or memory")


class AlbumEntryCreate(AlbumEntryBase):
    """
    Model for creating a new album entry.
    Note: Files (photo, voice note) are handled via UploadFile in the route,
    so they are not included in this Pydantic model for validation of the JSON body.
    This model is used to validate the form fields.
    """
    pass


class AlbumEntryResponse(AlbumEntryBase):
    """Model for album entry response."""
    album_id: str
    patient_id: str
    photo_url: str
    voice_note_url: Optional[str] = None
    uploaded_at: datetime
    uploaded_by: str  # Caregiver ID
    
    class Config:
        from_attributes = True
