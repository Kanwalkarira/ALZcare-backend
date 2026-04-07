"""
Clinical Notes routes (Doctor Suggestions & Caregiver Behavioral Notes).
"""
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form  # type: ignore
from typing import List, Dict, Any, Optional

from app.models.care import SuggestionResponse, BehaviorNoteResponse, ActivityLog  # type: ignore
from app.models.user import UserInDB, UserRole, UserResponse  # type: ignore
from app.services.firestore import firestore_service  # type: ignore
from app.services.storage_service import storage_service  # type: ignore
from app.dependencies.auth import require_role  # type: ignore

router = APIRouter(tags=["Clinical Notes"])

# Role dependencies
require_doctor = require_role([UserRole.doctor.value, UserRole.admin.value])
require_caregiver = require_role([UserRole.caregiver.value, UserRole.admin.value])
require_viewer = require_role([UserRole.doctor.value, UserRole.caregiver.value, UserRole.admin.value])


@router.post("/patients/{patient_id}/suggestions", response_model=SuggestionResponse, status_code=status.HTTP_201_CREATED)
async def create_suggestion(
    patient_id: str,
    suggestion_text: str = Form(..., description="Treatment suggestion text"),
    attachments: List[UploadFile] = File(None, description="Optional attachments"),
    current_user: UserInDB = Depends(require_doctor)
):
    """
    Create a treatment suggestion for a patient.
    **Doctor only.**
    """
    # Upload attachments if any
    attachment_urls = []
    if attachments:
        for file in attachments:
            # Check if file is valid (basic check)
            # validation logic here if needed, generic upload handles most
            url = await storage_service.upload_file(
                file_content=await file.read(),
                file_name=file.filename or "attachment",
                folder=f"patients/{patient_id}/suggestions_attachments",
                content_type=file.content_type or "application/octet-stream"
            )
            if url:
                attachment_urls.append(url)

    suggestion_data = {
        "doctor_id": current_user.uid,
        "doctor_name": current_user.name,
        "suggestion_text": suggestion_text,
        "attachments_urls": attachment_urls
    }
    
    result = await firestore_service.create_suggestion(patient_id, suggestion_data)
    return result


@router.get("/patients/{patient_id}/suggestions", response_model=List[SuggestionResponse])
async def get_suggestions(
    patient_id: str,
    limit: int = 50,
    current_user: UserInDB = Depends(require_viewer)
):
    """
    Get treatment suggestions for a patient.
    **Doctor & Caregiver.**
    """
    return await firestore_service.get_suggestions(patient_id, limit)


@router.post("/patients/{patient_id}/behavior-notes", response_model=BehaviorNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_behavior_note(
    patient_id: str,
    note_text: str = Form(..., description="Behavioral note text"),
    attachments: List[UploadFile] = File(None, description="Optional attachments"),
    current_user: UserInDB = Depends(require_caregiver)
):
    """
    Create a behavioral note for a patient.
    **Caregiver only.**
    """
    # Upload attachments if any
    attachment_urls = []
    if attachments:
        for file in attachments:
            url = await storage_service.upload_file(
                file_content=await file.read(),
                file_name=file.filename or "attachment",
                folder=f"patients/{patient_id}/behavior_notes_attachments",
                content_type=file.content_type or "application/octet-stream"
            )
            if url:
                attachment_urls.append(url)

    note_data = {
        "caregiver_id": current_user.uid,
        "caregiver_name": current_user.name,
        "note_text": note_text,
        "attachments_urls": attachment_urls
    }
    
    result = await firestore_service.create_behavioral_note(patient_id, note_data)
    return result


@router.get("/patients/{patient_id}/behavior-notes", response_model=List[BehaviorNoteResponse])
async def get_behavior_notes(
    patient_id: str,
    limit: int = 50,
    current_user: UserInDB = Depends(require_viewer)
):
    """
    Get behavioral notes for a patient.
    **Doctor & Caregiver.**
    """
    return await firestore_service.get_behavioral_notes(patient_id, limit)

@router.get("/care/logs", response_model=List[ActivityLog])
async def get_activity_logs(
    patient_id: Optional[str] = None, 
    limit: int = 50, 
    current_user: UserInDB = Depends(require_viewer)
):
    """
    Get activity logs (for doctor).
    """
    db = firestore_service.db
    query = db.collection("activity_logs")
    if patient_id:
        query = query.where("patient_id", "==", patient_id)
    docs = query.order_by("timestamp", direction="DESCENDING").limit(limit).stream()
    
    logs = []
    for doc in docs:
        data = doc.to_dict()
        data["log_id"] = doc.id
        logs.append(data)
    return logs

@router.post("/care/suggestions")
async def create_care_suggestion(
    patient_id: str = Form(...),
    suggestion_text: str = Form(...),
    attachments: List[UploadFile] = File(None),
    current_user: UserInDB = Depends(require_doctor)
):
    """Alias for creating a suggestion per user spec"""
    return await create_suggestion(patient_id, suggestion_text, attachments, current_user)

@router.get("/care/suggestions/{patient_id}")
async def get_care_suggestions(
    patient_id: str,
    limit: int = 50,
    current_user: UserInDB = Depends(require_viewer)
):
    """Alias for fetching suggestions per user spec"""
    return await get_suggestions(patient_id, limit, current_user)

@router.get("/care/patients", response_model=List[UserResponse])
async def get_overview_patients(current_user: UserInDB = Depends(require_viewer)):
    """Get patients assigned to current caregiver/doctor"""
    # For now, simplistic approach: just get all users with role 'patient'
    # Real app would query a junction collection 'patient_caregivers'
    users = await firestore_service.get_users_by_role("patient")
    return [UserResponse(**u) for u in users]
