"""
Service for handling mood tracking business logic.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import uuid
import logging

from app.models.mood import MoodCreate, MoodResponse, MoodStats, MoodEmoji  # type: ignore
from app.models.user import UserInDB  # type: ignore
from app.services.firestore import firestore_service  # type: ignore
from app.services.fcm_service import fcm_service  # type: ignore  # For push notifications
from fastapi import HTTPException, status  # type: ignore

logger = logging.getLogger(__name__)


class MoodService:
    """Service for mood logging and analytics."""

    async def log_mood(
        self,
        mood_create: MoodCreate,
        patient: UserInDB
    ) -> MoodResponse:
        """
        Log a new mood for a patient.
        
        Args:
            mood_create: Mood data
            patient: User logging the mood (must be patient)
            
        Returns:
            Created mood response
        """
        if patient.role != "patient":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only patients can log moods"
            )

        log_id = str(uuid.uuid4())
        now = datetime.utcnow()

        mood_data = {
            "log_id": log_id,
            "patient_id": patient.uid,
            "patient_name": patient.name,
            "emoji": mood_create.emoji,
            "note": mood_create.note,
            "timestamp": now,
            "created_at": now
        }

        # Persist to Firestore
        await firestore_service.create_mood_log(mood_data)
        
        # Check for negative mood and notify caregivers
        # Negative emojis: SAD, ANGRY, ANXIOUS, CONFUSED
        negative_emojis = [
            MoodEmoji.SAD.value, 
            MoodEmoji.ANGRY.value, 
            MoodEmoji.ANXIOUS.value, 
            MoodEmoji.CONFUSED.value
        ]
        
        if mood_create.emoji in negative_emojis:
            await self._notify_caregivers(patient, mood_create.emoji, mood_create.note)

        return MoodResponse(
            log_id=log_id,
            emoji=mood_create.emoji,
            note=mood_create.note,
            timestamp=now
        )

    async def get_patient_moods(
        self,
        patient_id: str,
        current_user: UserInDB,
        limit: int = 50
    ) -> List[MoodResponse]:
        """
        Get recent mood logs for a patient.
        
        Args:
            patient_id: Target patient ID
            current_user: Requesting user
            limit: Pagination limit
            
        Returns:
            List of mood responses
        """
        # Authorization check
        await self._verify_access(current_user, patient_id)

        logs = await firestore_service.get_patient_moods(patient_id, limit)
        return [MoodResponse(**log) for log in logs]

    async def get_mood_stats(
        self,
        patient_id: str,
        current_user: UserInDB,
        period: str = "7_days"
    ) -> MoodStats:
        """
        Get mood statistics for a patient (bar graph data).
        
        Args:
            patient_id: Target patient ID
            current_user: Requesting user
            period: '7_days' or '30_days'
            
        Returns:
            MoodStats object
        """
        # Authorization check
        await self._verify_access(current_user, patient_id)
        
        # Calculate date range
        end_date = datetime.utcnow()
        days = 30 if period == "30_days" else 7
        start_date = end_date - timedelta(days=days)
        
        # Fetch logs
        logs = await firestore_service.get_mood_logs_range(patient_id, start_date, end_date)
        
        # Aggregate counts
        counts = {}
        for log in logs:
            emoji = log.get('emoji', 'Unknown')
            counts[emoji] = counts.get(emoji, 0) + 1
            
        return MoodStats(
            period=period,
            total_logs=len(logs),
            emoji_counts=counts,
            start_date=start_date,
            end_date=end_date
        )

    async def _verify_access(self, user: UserInDB, patient_id: str):
        """Verify user has access to patient data."""
        if user.role == "patient":
            if user.uid != patient_id:
                raise HTTPException(status_code=403, detail="Access denied")
        elif user.role == "caregiver":
            # Check assignment
            caregivers = await firestore_service.get_patient_caregivers(patient_id)
            if user.uid not in [c['caregiver_id'] for c in caregivers]:
                 # For simplicity, if not explicitly assigned, deny. 
                 # But we might want to allow if they have *any* link.
                 # Reusing the strict check from other services.
                 raise HTTPException(status_code=403, detail="Not assigned to this patient")
        elif user.role == "doctor":
             doctor = await firestore_service.get_patient_doctor(patient_id)
             if not doctor or doctor['doctor_id'] != user.uid:
                 raise HTTPException(status_code=403, detail="Not assigned to this patient")
        elif user.role != "admin":
            raise HTTPException(status_code=403, detail="Unauthorized role")

    async def _notify_caregivers(self, patient: UserInDB, emoji: str, note: Optional[str]):
        """Send push notification to assigned caregivers."""
        try:
            caregivers = await firestore_service.get_patient_caregivers(patient.uid)
            for caregiver in caregivers:
                # We need fcm_token. Assuming it's in the caregiver record or we fetch user.
                # Firestore service 'get_patient_caregivers' usually returns relationships.
                # We might need to fetch the actual user doc to get fcm_token if it's stored there.
                # Let's assume fcm_service handles lookup if we pass ID, or we fetch here.
                # 'fcm_service.send_notification' usually takes token.
                # Let's try to get the caregiver user doc.
                
                caregiver_id = caregiver['caregiver_id']
                # Potential optimization: Batch fetch
                user_doc = await firestore_service.get_user(caregiver_id)
                if user_doc and 'fcm_token' in user_doc:
                    title = f"Mood Alert: {patient.name}"
                    body = f"{patient.name} is feeling {emoji}."
                    if note:
                        body += f" Note: {note}"
                    
                    await fcm_service.send_notification(
                        token=user_doc['fcm_token'],
                        title=title,
                        body=body,
                        data={"type": "mood_alert", "patient_id": patient.uid}
                    )
        except Exception as e:
            logger.error(f"Failed to notify caregivers for mood: {e}")

mood_service = MoodService()
