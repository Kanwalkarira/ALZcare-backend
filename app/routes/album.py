"""
Family Album routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form  # type: ignore
from typing import List, Dict, Any, Optional

from app.models.album import AlbumEntryResponse, AlbumEntryCreate  # type: ignore
from app.models.user import UserInDB, UserRole  # type: ignore
from app.services.firestore import firestore_service  # type: ignore
from app.services.storage_service import storage_service  # type: ignore
from app.dependencies.auth import require_role  # type: ignore

router = APIRouter(prefix="/albums", tags=["Family Album"])

# Role dependencies
require_caregiver = require_role([UserRole.caregiver.value, UserRole.admin.value])
require_patient = require_role([UserRole.patient.value])


@router.post("/", response_model=AlbumEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_album_entry(
    patient_id: str = Form(..., description="ID of the patient this album entry is for"),
    person_name: str = Form(..., description="Name of the person in the photo"),
    description: Optional[str] = Form(None, description="Optional description"),
    photo: UploadFile = File(..., description="Photo file (JPEG/PNG)"),
    voice_note: Optional[UploadFile] = File(None, description="Optional voice note (Audio)"),
    current_user: UserInDB = Depends(require_caregiver)
):
    """
    Create a new album entry.
    Uploads photo and optional voice note to Supabase Storage,
    then saves metadata to Firestore.
    
    **Caregiver only endpoint.**
    """
    # 1. Validate & Upload Photo
    photo_content = await photo.read()
    is_valid_photo, photo_error = storage_service.validate_image_file(photo_content)
    if not is_valid_photo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid photo: {photo_error}"
        )
        
    photo_url = await storage_service.upload_file(
        file_content=photo_content,
        file_name=photo.filename or "photo.jpg",
        folder=f"patients/{patient_id}/album_photos",
        content_type=photo.content_type or "image/jpeg"
    )
    
    if not photo_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload photo"
        )
        
    # 2. Validate & Upload Voice Note (if provided)
    voice_note_url = None
    if voice_note:
        voice_content = await voice_note.read()
        is_valid_audio, audio_error = storage_service.validate_audio_file(voice_content)
        if not is_valid_audio:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid voice note: {audio_error}"
            )
            
        voice_note_url = await storage_service.upload_file(
            file_content=voice_content,
            file_name=voice_note.filename or "voice_note.mp3",
            folder=f"patients/{patient_id}/album_audio",
            content_type=voice_note.content_type or "audio/mpeg"
        )
        
        if not voice_note_url:
             # Clean up photo if audio fails? strictly speaking yes, but complex.
             # For now just fail.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload voice note"
            )

    # 3. Create Firestore Entry
    album_data = {
        "patient_id": patient_id,
        "person_name": person_name,
        "description": description,
        "photo_url": photo_url,
        "voice_note_url": voice_note_url,
        "uploaded_by": current_user.uid,
        "caregiver_name": current_user.name
    }
    
    result = await firestore_service.create_album_entry(album_data)
    
    return result


@router.get("/patients/me", response_model=List[AlbumEntryResponse])
async def get_my_album(
    current_user: UserInDB = Depends(require_patient)
):
    """
    Get the album entries for the current patient.
    """
    return await firestore_service.get_album_entries(current_user.uid)


@router.get("/patients/{patient_id}", response_model=List[AlbumEntryResponse])
async def get_patient_album(
    patient_id: str,
    current_user: UserInDB = Depends(require_role([UserRole.caregiver.value, UserRole.doctor.value, UserRole.admin.value]))
):
    """
    Get the album entries for a specific patient.
    Accessible by Caregivers, Doctors, and Admins.
    """
    return await firestore_service.get_album_entries(patient_id)
