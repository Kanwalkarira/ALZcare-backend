"""
Mood tracking routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status  # type: ignore
from typing import List, Dict, Any

from app.models.mood import MoodCreate, MoodStats  # type: ignore
from app.models.user import UserInDB, UserRole  # type: ignore
from app.services.firestore import firestore_service  # type: ignore
from app.dependencies.auth import require_role  # type: ignore

router = APIRouter(prefix="/moods", tags=["Mood Tracking"])

# Role dependencies
require_patient = require_role([UserRole.patient.value])
require_viewer = require_role([UserRole.caregiver.value, UserRole.doctor.value, UserRole.admin.value])


@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def log_mood(
    mood_data: MoodCreate,
    current_user: UserInDB = Depends(require_patient)
):
    """
    Log a new mood entry.
    Only patients can log their own mood.
    """
    # Convert Pydantic model to dict
    mood_dict = mood_data.model_dump()
    
    # Add patient context
    mood_dict["patient_id"] = current_user.uid
    mood_dict["patient_name"] = current_user.name
    
    result = await firestore_service.create_mood_log(mood_dict)
    
    return result


@router.get("/patients/{patient_id}", response_model=List[Dict[str, Any]])
async def get_patient_moods(
    patient_id: str,
    limit: int = 50,
    current_user: UserInDB = Depends(require_viewer)
):
    """
    Get mood logs for a specific patient.
    Accessible by Caregivers, Doctors, and Admins.
    """
    return await firestore_service.get_mood_logs(patient_id, limit)


@router.get("/patients/{patient_id}/stats", response_model=MoodStats)
async def get_patient_mood_stats(
    patient_id: str,
    days: int = 7,
    current_user: UserInDB = Depends(require_viewer)
):
    """
    Get mood statistics for a patient.
    Accessible by Caregivers, Doctors, and Admins.
    """
    return await firestore_service.get_mood_stats(patient_id, days)
