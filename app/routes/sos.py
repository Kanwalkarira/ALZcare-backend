"""
SOS alert routes for emergency notifications.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query  # type: ignore
from typing import List, Dict, Any

from app.models.sos import (  # type: ignore
    SOSTriggerRequest,
    SOSAlertResponse,
    SOSAlertUpdate,
    AlertStatus
)
from app.models.user import UserInDB  # type: ignore
from app.services.sos_service import sos_service  # type: ignore
from app.dependencies.auth import get_current_user  # type: ignore


router = APIRouter(prefix="/sos", tags=["SOS Alerts"])


@router.post("/trigger", response_model=SOSAlertResponse, status_code=status.HTTP_201_CREATED)
async def trigger_sos_alert(
    sos_request: SOSTriggerRequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Trigger an SOS emergency alert.
    
    **Patient only endpoint.**
    
    Request body:
    - location: Patient's current location (latitude, longitude) - REQUIRED
    - notes: Optional notes about the emergency
    
    Returns:
    - Alert details with number of caregivers notified
    
    Raises:
    - 403: If user is not a patient
    - 429: If rate limit exceeded (1 alert per 60 seconds)
    """
    return await sos_service.trigger_sos_alert(current_user, sos_request)


@router.get("/alerts", response_model=List[Dict[str, Any]])
async def get_sos_alerts(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of alerts to return"),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get SOS alerts based on user role.
    
    - **Patients**: See their own alerts
    - **Caregivers**: See alerts from assigned patients
    - **Admins**: See all alerts (not implemented yet)
    
    Query parameters:
    - limit: Maximum number of alerts (1-100, default 50)
    
    Returns:
    - List of SOS alerts
    """
    return await sos_service.get_sos_alerts(current_user, limit)


@router.get("/alerts/{alert_id}", response_model=Dict[str, Any])
async def get_sos_alert(
    alert_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get a specific SOS alert by ID.
    
    Returns:
    - Alert details
    
    Raises:
    - 404: If alert not found
    - 403: If user not authorized to view this alert
    """
    from app.services.firestore import firestore_service  # type: ignore
    
    alert = await firestore_service.get_sos_alert(alert_id)
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SOS alert not found"
        )
    
    # Check authorization
    if current_user.role == "patient":
        if alert["patient_id"] != current_user.uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own SOS alerts"
            )
    elif current_user.role == "caregiver":
        # Check if caregiver is assigned to this patient
        caregivers = await firestore_service.get_patient_caregivers(alert["patient_id"])
        caregiver_ids = [c["caregiver_id"] for c in caregivers]
        
        if current_user.uid not in caregiver_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view alerts from your assigned patients"
            )
    # Admins can view any alert
    
    return alert


@router.patch("/alerts/{alert_id}", response_model=Dict[str, str])
async def update_sos_alert(
    alert_id: str,
    update_data: SOSAlertUpdate,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Update SOS alert status.
    
    Request body:
    - status: New status ("active", "resolved", "cancelled")
    - notes: Optional notes
    
    Returns:
    - Success message
    
    Raises:
    - 404: If alert not found
    - 403: If user not authorized to update this alert
    """
    success = await sos_service.update_sos_alert_status(
        alert_id,
        current_user,
        update_data.status,
        update_data.notes
    )
    
    if success:
        return {
            "message": f"SOS alert {alert_id} updated to {update_data.status.value}",
            "alert_id": alert_id,
            "status": update_data.status.value
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update SOS alert"
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for SOS service."""
    return {"status": "healthy", "service": "sos_alerts"}
