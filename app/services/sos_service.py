"""
SOS alert service handling emergency alerts and caregiver notifications.
"""
import uuid
from typing import Dict, Any, List, Tuple
from datetime import datetime
from fastapi import HTTPException, status
import logging

from app.models.sos import (
    SOSTriggerRequest,
    SOSAlertResponse,
    SOSAlert,
    AlertStatus,
    NotificationRecord,
    LocationData
)
from app.models.user import UserInDB
from app.services.firestore import firestore_service
from app.services.fcm_service import fcm_service
from app.config import settings

logger = logging.getLogger(__name__)


class SOSService:
    """Service for SOS alert operations."""
    
    def __init__(self):
        self.rate_limit_seconds = getattr(settings, 'SOS_RATE_LIMIT_SECONDS', 60)
    
    async def trigger_sos_alert(
        self,
        current_user: UserInDB,
        sos_request: SOSTriggerRequest
    ) -> SOSAlertResponse:
        """
        Trigger an SOS alert.
        
        Args:
            current_user: Authenticated user (must be patient)
            sos_request: SOS trigger request with location
            
        Returns:
            SOS alert response
            
        Raises:
            HTTPException: If user is not a patient or rate limit exceeded
        """
        # Verify user is a patient
        if current_user.role != "patient":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only patients can trigger SOS alerts"
            )
        
        # Check rate limiting
        can_trigger, seconds_remaining = await firestore_service.check_sos_rate_limit(
            current_user.uid,
            self.rate_limit_seconds
        )
        
        if not can_trigger:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {seconds_remaining} seconds before triggering another SOS alert"
            )
        
        # Create SOS alert
        alert_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        alert_data = {
            "alert_id": alert_id,
            "patient_id": current_user.uid,
            "patient_name": current_user.name,
            "patient_email": current_user.email,
            "timestamp": now,
            "location": sos_request.location.dict(),
            "status": AlertStatus.ACTIVE.value,
            "notes": sos_request.notes,
            "created_at": now
        }
        
        # Store alert in Firestore
        await firestore_service.create_sos_alert(alert_data)
        
        logger.info(f"SOS alert {alert_id} created for patient {current_user.name}")
        
        # Find caregivers
        caregivers = await firestore_service.get_patient_caregivers(current_user.uid)
        
        if not caregivers:
            logger.warning(f"No caregivers found for patient {current_user.uid}")
        
        # Send notifications to caregivers
        notification_results = await fcm_service.send_sos_to_caregivers(
            caregivers,
            current_user.name,
            alert_id,
            sos_request.location.latitude,
            sos_request.location.longitude
        )
        
        # Store notification records
        for result in notification_results:
            notification_id = str(uuid.uuid4())
            notification_data = {
                "notification_id": notification_id,
                "alert_id": alert_id,
                "recipient_id": result['caregiver_id'],
                "recipient_name": result.get('caregiver_name', 'Unknown'),
                "recipient_email": "",  # Could be added if needed
                "sent_at": now,
                "status": result['status'],
                "fcm_message_id": result.get('message_id'),
                "error_message": result.get('error')
            }
            
            await firestore_service.create_notification_record(notification_data)
        
        caregivers_notified = sum(1 for r in notification_results if r['status'] == 'sent')
        
        logger.info(f"SOS alert {alert_id}: Notified {caregivers_notified}/{len(caregivers)} caregivers")
        
        return SOSAlertResponse(
            alert_id=alert_id,
            patient_id=current_user.uid,
            patient_name=current_user.name,
            timestamp=now,
            location=sos_request.location,
            status=AlertStatus.ACTIVE,
            notes=sos_request.notes,
            caregivers_notified=caregivers_notified
        )
    
    async def get_sos_alerts(
        self,
        current_user: UserInDB,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get SOS alerts based on user role.
        
        Args:
            current_user: Authenticated user
            limit: Maximum number of alerts to return
            
        Returns:
            List of SOS alerts
        """
        if current_user.role == "patient":
            # Patients can only see their own alerts
            alerts = await firestore_service.get_sos_alerts_for_patient(
                current_user.uid,
                limit
            )
        elif current_user.role == "caregiver":
            # Caregivers can see alerts from their assigned patients
            alerts = await firestore_service.get_sos_alerts_for_caregiver(
                current_user.uid,
                limit
            )
        elif current_user.role == "admin":
            # Admins can see all alerts (implement if needed)
            alerts = []  # TODO: Implement admin view
        else:
            alerts = []
        
        return alerts
    
    async def update_sos_alert_status(
        self,
        alert_id: str,
        current_user: UserInDB,
        new_status: AlertStatus,
        notes: str = None
    ) -> bool:
        """
        Update SOS alert status.
        
        Args:
            alert_id: Alert ID
            current_user: Authenticated user
            new_status: New alert status
            notes: Optional notes
            
        Returns:
            True if successful
            
        Raises:
            HTTPException: If alert not found or unauthorized
        """
        # Get alert
        alert = await firestore_service.get_sos_alert(alert_id)
        
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SOS alert not found"
            )
        
        # Check authorization
        if current_user.role == "patient":
            # Patients can only update their own alerts
            if alert["patient_id"] != current_user.uid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only update your own SOS alerts"
                )
        elif current_user.role == "caregiver":
            # Caregivers can update alerts from their assigned patients
            caregivers = await firestore_service.get_patient_caregivers(alert["patient_id"])
            caregiver_ids = [c["caregiver_id"] for c in caregivers]
            
            if current_user.uid not in caregiver_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only update alerts from your assigned patients"
                )
        # Admins can update any alert
        
        # Update alert
        update_data = {
            "status": new_status.value
        }
        
        if new_status in [AlertStatus.RESOLVED, AlertStatus.CANCELLED]:
            update_data["resolved_at"] = datetime.utcnow()
            update_data["resolved_by"] = current_user.uid
        
        if notes:
            update_data["notes"] = notes
        
        success = await firestore_service.update_sos_alert(alert_id, update_data)
        
        if success:
            logger.info(f"SOS alert {alert_id} updated to {new_status.value} by {current_user.name}")
        
        return success


# Global SOS service instance
sos_service = SOSService()
