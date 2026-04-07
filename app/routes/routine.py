from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from app.models.routine import RoutineCreate, RoutineResponse, RoutineUpdate
from app.dependencies.auth import get_current_user
from app.models.user import UserInDB
from app.services.firestore import firestore_service

router = APIRouter(prefix="/routines", tags=["Routines"])

@router.post("/", response_model=RoutineResponse, status_code=status.HTTP_201_CREATED)
async def create_routine(routine: RoutineCreate, current_user: UserInDB = Depends(get_current_user)):
    if current_user.role != "caregiver":
        raise HTTPException(status_code=403, detail="Only caregivers can create routines")
    
    routine_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    routine_data = {
        "routine_id": routine_id,
        "caregiver_id": current_user.uid,
        "patient_id": routine.patient_id,
        "task": routine.task,
        "time": routine.time,
        "checked": False,
        "created_at": now,
        "updated_at": now
    }
    
    # Needs a method in firestore_service to save this. We will add a generalized one.
    db = firestore_service.db
    db.collection("patients").document(routine.patient_id).collection("routines").document(routine_id).set(routine_data)
    
    return RoutineResponse(**routine_data)

@router.get("/patients/{patient_id}", response_model=List[RoutineResponse])
async def get_routines(patient_id: str, current_user: UserInDB = Depends(get_current_user)):
    db = firestore_service.db
    routines_ref = db.collection("patients").document(patient_id).collection("routines")
    docs = routines_ref.order_by("time", direction="ASCENDING").stream()
    
    routines = []
    for doc in docs:
        routines.append(doc.to_dict())
        
    return routines

@router.patch("/{routine_id}", response_model=RoutineResponse)
async def update_routine(routine_id: str, update_data: RoutineUpdate, current_user: UserInDB = Depends(get_current_user)):
    # IMPORTANT: This query requires a Collection Group index on 'routines' for the 'routine_id' field.
    # If not created, this will throw a 400 or 500 error from the Firestore SDK.
    # To fix: Go to Firebase Console -> Firestore -> Indexes -> Collection Group -> Add Index
    # Collection ID: routines, Fields: routine_id (Ascending)
    db = firestore_service.db
    docs = db.collection_group("routines").where("routine_id", "==", routine_id).limit(1).stream()
    
    routine_doc = None
    routine_ref = None
    try:
        for doc in docs:
            routine_doc = doc.to_dict()
            routine_ref = doc.reference
            break
    except Exception as e:
        logger.error(f"Firestore query error (check indexes): {e}")
        raise HTTPException(
            status_code=500, 
            detail="Database query failed. Please create a Collection Group index for 'routine_id' in the Firebase Console."
        )
        
    if not routine_doc:
        raise HTTPException(status_code=404, detail="Routine not found")
        
    updates = {k: v for k, v in update_data.dict(exclude_unset=True).items()}
    updates["updated_at"] = datetime.utcnow()
    
    routine_ref.update(updates)
    
    routine_doc.update(updates)
    return RoutineResponse(**routine_doc)

@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_routine(routine_id: str, current_user: UserInDB = Depends(get_current_user)):
    if current_user.role != "caregiver":
        raise HTTPException(status_code=403, detail="Only caregivers can delete routines")
        
    db = firestore_service.db
    docs = db.collection_group("routines").where("routine_id", "==", routine_id).limit(1).stream()
    
    deleted = False
    for doc in docs:
        doc.reference.delete()
        deleted = True
        break
        
    if not deleted:
        raise HTTPException(status_code=404, detail="Routine not found")
