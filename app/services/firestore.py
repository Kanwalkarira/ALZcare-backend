"""
Firestore database service with async operations.
Handles all database interactions using Firebase Admin SDK.
"""
import firebase_admin  # type: ignore
from firebase_admin import credentials, firestore  # type: ignore
from google.cloud.firestore_v1.base_query import FieldFilter  # type: ignore
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid
import json
import os

from app.config import settings  # type: ignore


class FirestoreService:
    """Service for interacting with Firestore database."""
    
    def __init__(self):
        """Initialize Firebase Admin SDK and Firestore client.
        
        Supports two modes:
        - FIREBASE_KEY_JSON env var: paste the full JSON (for Railway/cloud)
        - GOOGLE_APPLICATION_CREDENTIALS: path to the file (for local dev)
        """
        if not firebase_admin._apps:
            cred = None
            
            # Priority 1: Inline JSON from environment variable
            if settings.FIREBASE_KEY_JSON:
                try:
                    key_dict = json.loads(settings.FIREBASE_KEY_JSON)
                    cred = credentials.Certificate(key_dict)
                except Exception as e:
                    raise RuntimeError(f"Failed to parse FIREBASE_KEY_JSON: {e}")
            
            # Priority 2: File path or JSON content
            elif settings.GOOGLE_APPLICATION_CREDENTIALS:
                json_str = settings.GOOGLE_APPLICATION_CREDENTIALS.strip()
                if json_str.startswith('{') and json_str.endswith('}'):
                    try:
                        key_dict = json.loads(json_str)
                        cred = credentials.Certificate(key_dict)
                    except Exception as e:
                        raise RuntimeError(f"GOOGLE_APPLICATION_CREDENTIALS looks like JSON but failed to parse: {e}")
                else:
                    # Treat as file path
                    cred = credentials.Certificate(settings.GOOGLE_APPLICATION_CREDENTIALS)
            
            else:
                raise RuntimeError(
                    "No Firebase credentials found. "
                    "Set FIREBASE_KEY_JSON or GOOGLE_APPLICATION_CREDENTIALS."
                )
            
            firebase_admin.initialize_app(cred)
        
        self.db = firestore.client()
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    async def _run_async(self, func, *args, **kwargs) -> Any:
        """Run a synchronous Firestore operation asynchronously."""
        from functools import partial
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, partial(func, *args, **kwargs)) # type: ignore
    
    async def create_user(self, email: str, name: str, role: str, hashed_password: str, age: Optional[int] = None) -> Dict[str, Any]:
        """
        Create a new user in Firestore.
        Stores user data in both users/{uid} and roles/{role}/members/{uid}.
        
        Args:
            email: User's email address
            name: User's full name
            role: User's role (admin, teacher, student)
            hashed_password: Bcrypt hashed password
            age: Optional age of user
            
        Returns:
            User document data including uid
        """
        uid = str(uuid.uuid4())
        now = datetime.utcnow()
        
        user_data = {
            "uid": uid,
            "email": email.lower(),
            "name": name,
            "role": role,
            "age": age,
            "hashed_password": hashed_password,
            "created_at": now,
            "updated_at": now
        }
        
        def _create():
            # Create user document
            self.db.collection("users").document(uid).set(user_data)
            
            # Create role index document
            role_data = {
                "uid": uid,
                "email": email.lower(),
                "name": name,
                "added_at": now
            }
            self.db.collection("roles").document(role).collection("members").document(uid).set(role_data)
            
            return user_data
        
        return await self._run_async(_create)
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user by email address.
        
        Args:
            email: User's email address
            
        Returns:
            User document data or None if not found
        """
        def _get():
            users_ref = self.db.collection("users")
            query = users_ref.where(filter=FieldFilter("email", "==", email.lower())).limit(1)
            docs = query.stream()
            
            for doc in docs:
                return doc.to_dict()
            return None
        
        return await self._run_async(_get)
    
    async def get_user_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Get user by UID.
        
        Args:
            uid: User's unique identifier
            
        Returns:
            User document data or None if not found
        """
        def _get():
            doc = self.db.collection("users").document(uid).get()
            if doc.exists:
                return doc.to_dict()
            return None
        
        return await self._run_async(_get)
    
    async def update_user(self, uid: str, update_data: Dict[str, Any]) -> bool:
        """
        Update user document.
        
        Args:
            uid: User's unique identifier
            update_data: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        def _update():
            update_data["updated_at"] = datetime.utcnow()
            self.db.collection("users").document(uid).update(update_data)
            return True
        
        try:
            return await self._run_async(_update)
        except Exception:
            return False
    
    async def get_users_by_role(self, role: str) -> list[Dict[str, Any]]:
        """
        Get all users with a specific role.
        
        Args:
            role: User role to filter by
            
        Returns:
            List of user documents
        """
        def _get():
            members_ref = self.db.collection("roles").document(role).collection("members")
            docs = members_ref.stream()
            return [doc.to_dict() for doc in docs]
        
        return await self._run_async(_get)
    
    # ==================== SOS Alert Methods ====================
    
    async def create_sos_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new SOS alert in Firestore.
        
        Args:
            alert_data: SOS alert data
            
        Returns:
            Created alert document
        """
        def _create():
            alert_id = alert_data["alert_id"]
            self.db.collection("sos_alerts").document(alert_id).set(alert_data)
            return alert_data
        
        return await self._run_async(_create)
    
    async def get_sos_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        """
        Get SOS alert by ID.
        
        Args:
            alert_id: Alert ID
            
        Returns:
            Alert document or None
        """
        def _get():
            doc = self.db.collection("sos_alerts").document(alert_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        
        return await self._run_async(_get)
    
    async def update_sos_alert(self, alert_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update SOS alert.
        
        Args:
            alert_id: Alert ID
            update_data: Fields to update
            
        Returns:
            True if successful
        """
        def _update():
            self.db.collection("sos_alerts").document(alert_id).update(update_data)
            return True
        
        try:
            return await self._run_async(_update)
        except Exception:
            return False
    
    async def get_patient_caregivers(self, patient_id: str) -> list[Dict[str, Any]]:
        """
        Get all caregivers assigned to a patient.
        
        Args:
            patient_id: Patient's UID
            
        Returns:
            List of caregiver documents
        """
        def _get():
            caregivers_ref = self.db.collection("patient_caregivers").document(patient_id).collection("caregivers")
            docs = caregivers_ref.stream()
            caregivers = []
            for doc in docs:
                caregiver_data = doc.to_dict()
                # Get caregiver's FCM token from users collection
                caregiver_id = caregiver_data.get("caregiver_id")
                user_doc = self.db.collection("users").document(caregiver_id).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    caregiver_data["fcm_token"] = user_data.get("fcm_token")
                caregivers.append(caregiver_data)
            return caregivers
        
        return await self._run_async(_get)
    
    async def create_notification_record(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a notification record in Firestore.
        
        Args:
            notification_data: Notification data
            
        Returns:
            Created notification document
        """
        def _create():
            notification_id = notification_data["notification_id"]
            self.db.collection("notifications").document(notification_id).set(notification_data)
            return notification_data
        
        return await self._run_async(_create)
    
    async def check_sos_rate_limit(self, patient_id: str, limit_seconds: int) -> tuple[bool, Optional[int]]:
        """
        Check if patient can trigger SOS based on rate limit.
        
        Args:
            patient_id: Patient's UID
            limit_seconds: Minimum seconds between SOS alerts
            
        Returns:
            Tuple of (can_trigger, seconds_remaining)
        """
        def _check():
            from datetime import datetime, timedelta
            
            doc_ref = self.db.collection("sos_rate_limits").document(patient_id)
            doc = doc_ref.get()
            
            now = datetime.utcnow()
            
            if not doc.exists:
                # First SOS alert, allow it
                doc_ref.set({
                    "patient_id": patient_id,
                    "last_alert_time": now,
                    "alert_count": 1
                })
                return (True, None)
            
            data = doc.to_dict()
            last_alert_time = data.get("last_alert_time")
            
            if isinstance(last_alert_time, datetime):
                time_diff = (now - last_alert_time).total_seconds()
                
                if time_diff < limit_seconds:
                    seconds_remaining = int(limit_seconds - time_diff)
                    return (False, seconds_remaining)
            
            # Update rate limit
            doc_ref.update({
                "last_alert_time": now,
                "alert_count": data.get("alert_count", 0) + 1
            })
            
            return (True, None)
        
        return await self._run_async(_check)
    
    async def get_sos_alerts_for_patient(self, patient_id: str, limit: int = 50) -> list[Dict[str, Any]]:
        """
        Get SOS alerts for a specific patient.
        
        Args:
            patient_id: Patient's UID
            limit: Maximum number of alerts to return
            
        Returns:
            List of alert documents
        """
        def _get():
            alerts_ref = self.db.collection("sos_alerts")
            query = alerts_ref.where(filter=FieldFilter("patient_id", "==", patient_id)).order_by("timestamp", direction="DESCENDING").limit(limit)
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        
        return await self._run_async(_get)
    
    async def get_sos_alerts_for_caregiver(self, caregiver_id: str, limit: int = 50) -> list[Dict[str, Any]]:
        """
        Get SOS alerts for patients assigned to a caregiver.
        
        Args:
            caregiver_id: Caregiver's UID
            limit: Maximum number of alerts to return
            
        Returns:
            List of alert documents
        """
        def _get():
            # First, get all patients assigned to this caregiver
            patient_ids = []
            users_ref = self.db.collection_group("caregivers")
            query = users_ref.where(filter=FieldFilter("caregiver_id", "==", caregiver_id))
            for doc in query.stream():
                # Extract patient_id from document path
                patient_id = doc.reference.parent.parent.id
                patient_ids.append(patient_id)
            
            if not patient_ids:
                return []
            
            # Get SOS alerts for these patients
            alerts = []
            alerts_ref = self.db.collection("sos_alerts")
            for patient_id in patient_ids:
                query = alerts_ref.where(filter=FieldFilter("patient_id", "==", patient_id)).order_by("timestamp", direction="DESCENDING").limit(limit)
                for doc in query.stream():
                    alerts.append(doc.to_dict())
            
            # Sort by timestamp descending
            alerts.sort(key=lambda x: x.get("timestamp", datetime.min), reverse=True)
            # Return limited results
            if len(alerts) > limit:
                return alerts[:limit] # type: ignore
            return alerts
        
        return await self._run_async(_get)
    
    # ==================== Quiz Management Methods ====================
    
    async def create_quiz(self, quiz_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new quiz in Firestore."""
        def _create():
            quiz_ref = self.db.collection("quizzes").document(quiz_data["quiz_id"])
            quiz_ref.set(quiz_data)
            return quiz_data
        
        return await self._run_async(_create)  # type: ignore
    
    async def get_quiz(self, quiz_id: str) -> Optional[Dict[str, Any]]:
        """Get quiz by ID."""
        def _get():
            quiz_ref = self.db.collection("quizzes").document(quiz_id)
            doc = quiz_ref.get()
            return doc.to_dict() if doc.exists else None
        
        return await self._run_async(_get)  # type: ignore
    
    async def get_quizzes_by_caregiver(self, caregiver_id: str) -> list[Dict[str, Any]]:
        """Get all quizzes created by a caregiver."""
        def _get():
            quizzes_ref = self.db.collection("quizzes")
            query = quizzes_ref.where(filter=FieldFilter("caregiver_id", "==", caregiver_id))
            return [doc.to_dict() for doc in query.stream()]
        
        return await self._run_async(_get)  # type: ignore
    
    async def delete_quiz(self, quiz_id: str) -> bool:
        """Delete a quiz and all its assignments."""
        def _delete():
            try:
                # Delete quiz document
                self.db.collection("quizzes").document(quiz_id).delete()
                
                # Delete all assignments for this quiz
                # Note: This requires querying all patients, which may not be efficient
                # Consider using a separate collection for quiz_assignments indexed by quiz_id
                return True
            except Exception:
                return False
        
        return await self._run_async(_delete)  # type: ignore
    
    async def assign_quiz_to_patient(self, assignment_data: Dict[str, Any]) -> bool:
        """Assign a quiz to a patient."""
        def _assign():
            try:
                patient_id = assignment_data["patient_id"]
                quiz_id = assignment_data["quiz_id"]
                
                # Create assignment in patient's subcollection
                assignment_ref = self.db.collection("quiz_assignments").document(patient_id)\
                    .collection("assigned").document(quiz_id)
                assignment_ref.set(assignment_data)
                return True
            except Exception:
                return False
        
        return await self._run_async(_assign)  # type: ignore
    
    async def get_patient_quizzes(self, patient_id: str) -> list[Dict[str, Any]]:
        """Get all quizzes assigned to a patient."""
        def _get():
            assignments_ref = self.db.collection("quiz_assignments").document(patient_id)\
                .collection("assigned")
            assignments = [doc.to_dict() for doc in assignments_ref.stream()]
            
            # Fetch full quiz data for each assignment
            quizzes = []
            for assignment in assignments:
                quiz_ref = self.db.collection("quizzes").document(assignment["quiz_id"])
                quiz_doc = quiz_ref.get()
                if quiz_doc.exists:
                    quiz_data = quiz_doc.to_dict()
                    quiz_data["assignment_status"] = assignment.get("status", "pending")
                    quiz_data["assigned_at"] = assignment.get("assigned_at")
                    quiz_data["completed_at"] = assignment.get("completed_at")
                    quizzes.append(quiz_data)
            
            return quizzes
        
        return await self._run_async(_get)  # type: ignore
    
    async def submit_quiz_result(self, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persist quiz result to Firestore.
        This is the critical method that ensures results are stored permanently.
        """
        def _submit():
            # Store result in quiz_results collection
            result_ref = self.db.collection("quiz_results").document(result_data["result_id"])
            result_ref.set(result_data)
            
            # Update assignment status to completed
            patient_id = result_data["patient_id"]
            quiz_id = result_data["quiz_id"]
            assignment_ref = self.db.collection("quiz_assignments").document(patient_id)\
                .collection("assigned").document(quiz_id)
            assignment_ref.update({
                "status": "completed",
                "completed_at": result_data["submitted_at"]
            })
            
            return result_data
        
        return await self._run_async(_submit)  # type: ignore
    
    async def get_quiz_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific quiz result by ID."""
        def _get():
            result_ref = self.db.collection("quiz_results").document(result_id)
            doc = result_ref.get()
            return doc.to_dict() if doc.exists else None
        
        return await self._run_async(_get)  # type: ignore
    
    async def get_patient_results(self, patient_id: str, limit: int = 50) -> list[Dict[str, Any]]:
        """Get all quiz results for a patient."""
        def _get():
            results_ref = self.db.collection("quiz_results")
            query = results_ref.where(filter=FieldFilter("patient_id", "==", patient_id))\
                .order_by("submitted_at", direction="DESCENDING").limit(limit)
            return [doc.to_dict() for doc in query.stream()]
        
        return await self._run_async(_get)  # type: ignore
    
    async def get_quiz_results(self, quiz_id: str, limit: int = 100) -> list[Dict[str, Any]]:
        """Get all results for a specific quiz."""
        def _get():
            results_ref = self.db.collection("quiz_results")
            query = results_ref.where(filter=FieldFilter("quiz_id", "==", quiz_id))\
                .order_by("submitted_at", direction="DESCENDING").limit(limit)
            return [doc.to_dict() for doc in query.stream()]
        
        return await self._run_async(_get)  # type: ignore
    
    async def get_results_by_caregiver(self, caregiver_id: str, limit: int = 100) -> list[Dict[str, Any]]:
        """Get all quiz results for patients assigned to a caregiver."""
        def _get():
            results_ref = self.db.collection("quiz_results")
            query = results_ref.where(filter=FieldFilter("caregiver_id", "==", caregiver_id))\
                .order_by("submitted_at", direction="DESCENDING").limit(limit)
            return [doc.to_dict() for doc in query.stream()]
        
        return await self._run_async(_get)  # type: ignore
    
    async def get_results_by_doctor(self, doctor_id: str, limit: int = 100) -> list[Dict[str, Any]]:
        """Get all quiz results for patients assigned to a doctor."""
        def _get():
            results_ref = self.db.collection("quiz_results")
            query = results_ref.where(filter=FieldFilter("doctor_id", "==", doctor_id))\
                .order_by("submitted_at", direction="DESCENDING").limit(limit)
            return [doc.to_dict() for doc in query.stream()]
        
        return await self._run_async(_get)  # type: ignore
    
    async def get_patient_caregivers_for_quiz(self, patient_id: str) -> list[Dict[str, Any]]:
        """Get caregivers assigned to a patient (for quiz assignment)."""
        return await self.get_patient_caregivers(patient_id)
    
    async def get_patient_doctor(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Get the doctor assigned to a patient."""
        def _get():
            doctors_ref = self.db.collection("patient_doctors").document(patient_id)\
                .collection("doctors")
            docs = list(doctors_ref.limit(1).stream())
            return docs[0].to_dict() if docs else None
        
        return await self._run_async(_get)  # type: ignore
    
    async def assign_doctor_to_patient(self, patient_id: str, doctor_data: Dict[str, Any]) -> bool:
        """Assign a doctor to a patient."""
        def _assign():
            try:
                doctor_id = doctor_data["doctor_id"]
                doctor_ref = self.db.collection("patient_doctors").document(patient_id)\
                    .collection("doctors").document(doctor_id)
                doctor_ref.set(doctor_data)
                return True
            except Exception:
                return False
        
        return await self._run_async(_assign)  # type: ignore


    async def create_mood_log(self, mood_data: Dict[str, Any]) -> str:
        """
        Create a new mood log in Firestore.
        
        Args:
            mood_data: Mood log data
            
        Returns:
            Created log ID
        """
        def _create():
            doc_ref = self.db.collection('mood_logs').document(mood_data['log_id'])
            doc_ref.set(mood_data)
            return mood_data['log_id']
        
        return await self._run_async(_create) # type: ignore

    async def get_patient_moods(self, patient_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent mood logs for a patient.
        
        Args:
            patient_id: Patient ID
            limit: Max number of logs to return
            
        Returns:
            List of mood logs
        """
        def _get():
            logs = []
            query = (
                self.db.collection('mood_logs')
                .where(filter=FieldFilter('patient_id', '==', patient_id))
                .order_by('timestamp', direction="DESCENDING")
                .limit(limit)
            )
            return [doc.to_dict() for doc in query.stream()]
            
        return await self._run_async(_get) # type: ignore

    async def get_mood_logs_range(
        self, 
        patient_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get mood logs for a patient within a date range.
        
        Args:
            patient_id: Patient ID
            start_date: Start datetime
            end_date: End datetime
            
        Returns:
            List of mood logs
        """
        def _get():
            query = (
                self.db.collection('mood_logs')
                .where(filter=FieldFilter('patient_id', '==', patient_id))
                .where(filter=FieldFilter('timestamp', '>=', start_date))
                .where(filter=FieldFilter('timestamp', '<=', end_date))
                .order_by('timestamp', direction="DESCENDING")
            )
            return [doc.to_dict() for doc in query.stream()]
            
        return await self._run_async(_get) # type: ignore


    # ==================== Mood Tracking Methods ====================
    
    async def create_mood_log(self, mood_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new mood log in Firestore and notify caregivers if negative.
        """
        def _create():
            log_id = str(uuid.uuid4())
            mood_data["log_id"] = log_id
            if "timestamp" not in mood_data:
                mood_data["timestamp"] = datetime.utcnow()
            
            # Store in global mood_logs collection
            self.db.collection("mood_logs").document(log_id).set(mood_data)
            
            # Store reference in patient's subcollection for easy querying
            patient_id = mood_data["patient_id"]
            self.db.collection("patients").document(patient_id).collection("moods").document(log_id).set(mood_data)
            
            return mood_data
        
        # Run DB operation
        result = await self._run_async(_create)
        
        # Check for negative mood and notify caregivers
        # Negative emojis: 😔 (pensive), 😡 (pouting/angry), 😢 (crying), 😭 (loud crying), 😩 (weary), 😫 (tired)
        negative_emojis = ["😔", "😡", "😢", "😭", "😩", "😫", "😠", "😞", "😟"]
        
        if result.get("mood_emoji") in negative_emojis:
            try:
                caregivers = await self.get_patient_caregivers(result["patient_id"])
                
                # Get patient name for better notification
                patient = await self.get_user_by_uid(result["patient_id"])
                patient_name = patient.get("name", "Your Patient") if patient else "Your Patient"
                
                for caregiver in caregivers:
                    notification = {
                        "notification_id": str(uuid.uuid4()),
                        "user_id": caregiver.get("caregiver_id"), # Ensure field name matches
                        "title": "Negative Mood Alert",
                        "body": f"{patient_name} is feeling {result['mood_emoji']}. Note: {result.get('note', 'No note')}",
                        "type": "mood_alert",
                        "data": {
                            "patient_id": result["patient_id"], 
                            "log_id": result["log_id"],
                            "mood": result["mood_emoji"]
                        },
                        "read": False,
                        "created_at": datetime.utcnow()
                    }
                    await self.create_notification_record(notification)
            except Exception as e:
                # Log error but don't fail the request
                print(f"Failed to send mood notifications: {e}")
                
        return result

    async def get_mood_logs(self, patient_id: str, limit: int = 50) -> list[Dict[str, Any]]:
        """Get mood logs for a patient."""
        def _get():
            logs_ref = self.db.collection("patients").document(patient_id).collection("moods")
            query = logs_ref.order_by("timestamp", direction="DESCENDING").limit(limit)
            return [doc.to_dict() for doc in query.stream()]
        
        return await self._run_async(_get)

    async def get_mood_stats(self, patient_id: str, days: int = 7) -> Dict[str, Any]:
        """Get mood statistics for a patient."""
        def _get_stats():
            from datetime import timedelta
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            logs_ref = self.db.collection("patients").document(patient_id).collection("moods")
            # Note: Compound query might require index. 
            # If so, can fetch all recent and filter in memory if volume is low, 
            # but better to use query.
            # filtering by timestamp
            query = logs_ref.where(filter=FieldFilter("timestamp", ">=", start_date))
            docs = query.stream()
            
            counts = {}
            for doc in docs:
                data = doc.to_dict()
                emoji = data.get("mood_emoji")
                if emoji:
                    counts[emoji] = counts.get(emoji, 0) + 1
            
            return {
                "period": f"{days}_days",
                "counts": counts,
                "start_date": start_date,
                "end_date": end_date
            }
        
        return await self._run_async(_get_stats)


    # ==================== Family Album Methods ====================

    async def create_album_entry(self, album_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new album entry in Firestore.
        Stores in patients/{patient_id}/albums
        """
        def _create():
            album_id = str(uuid.uuid4())
            album_data["album_id"] = album_id
            if "uploaded_at" not in album_data:
                album_data["uploaded_at"] = datetime.utcnow()
            
            patient_id = album_data["patient_id"]
            
            # Store in patient's album subcollection
            self.db.collection("patients").document(patient_id).collection("albums").document(album_id).set(album_data)
            
            # Also store in top-level albums collection if needed for global queries, but usually not needed for this feature
            # Keeping it scoped to patient for privacy and ease of security rules
            
            return album_data
        
        return await self._run_async(_create)

    async def get_album_entries(self, patient_id: str, limit: int = 100) -> list[Dict[str, Any]]:
        """
        Get album entries for a patient.
        sorted by uploaded_at descending.
        """
        def _get():
            albums_ref = self.db.collection("patients").document(patient_id).collection("albums")
            query = albums_ref.order_by("uploaded_at", direction="DESCENDING").limit(limit)
            return [doc.to_dict() for doc in query.stream()]
        
        return await self._run_async(_get)


    # ==================== Clinical Notes Methods ====================

    async def create_suggestion(self, patient_id: str, suggestion_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a doctor suggestion for a patient.
        Stores in patients/{patient_id}/suggestions/{suggestion_id}
        """
        def _create():
            suggestion_id = str(uuid.uuid4())
            suggestion_data["suggestion_id"] = suggestion_id
            if "created_at" not in suggestion_data:
                suggestion_data["created_at"] = datetime.utcnow()
            
            # Store in patient's suggestions subcollection
            self.db.collection("patients").document(patient_id).collection("suggestions").document(suggestion_id).set(suggestion_data)
            
            return suggestion_data
        
        return await self._run_async(_create)

    async def get_suggestions(self, patient_id: str, limit: int = 50) -> list[Dict[str, Any]]:
        """
        Get doctor suggestions for a patient.
        """
        def _get():
            ref = self.db.collection("patients").document(patient_id).collection("suggestions")
            query = ref.order_by("created_at", direction="DESCENDING").limit(limit)
            return [doc.to_dict() for doc in query.stream()]
        
        return await self._run_async(_get)

    async def create_behavioral_note(self, patient_id: str, note_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a behavioral note for a patient (by Caregiver).
        Stores in patients/{patient_id}/behavior_notes/{note_id}
        """
        def _create():
            note_id = str(uuid.uuid4())
            note_data["note_id"] = note_id
            if "created_at" not in note_data:
                note_data["created_at"] = datetime.utcnow()
            
            # Store in patient's behavior_notes subcollection
            self.db.collection("patients").document(patient_id).collection("behavior_notes").document(note_id).set(note_data)
            
            return note_data
        
        return await self._run_async(_create)

    async def get_behavioral_notes(self, patient_id: str, limit: int = 50) -> list[Dict[str, Any]]:
        """
        Get behavioral notes for a patient.
        """
        def _get():
            ref = self.db.collection("patients").document(patient_id).collection("behavior_notes")
            query = ref.order_by("created_at", direction="DESCENDING").limit(limit)
            return [doc.to_dict() for doc in query.stream()]
        
        return await self._run_async(_get)


    # ==================== Report Generation Data Methods ====================

    async def get_mood_logs_by_date(self, patient_id: str, start_date: datetime, end_date: datetime) -> list[Dict[str, Any]]:
        """Get mood logs within a date range."""
        def _get():
            ref = self.db.collection("patients").document(patient_id).collection("moods")
            query = ref.where(filter=FieldFilter("timestamp", ">=", start_date))\
                       .where(filter=FieldFilter("timestamp", "<=", end_date))\
                       .order_by("timestamp", direction="DESCENDING")
            return [doc.to_dict() for doc in query.stream()]
        return await self._run_async(_get)

    async def get_quiz_results_by_date(self, patient_id: str, start_date: datetime, end_date: datetime) -> list[Dict[str, Any]]:
        """Get quiz results within a date range."""
        def _get():
            ref = self.db.collection("quiz_results")
            query = ref.where(filter=FieldFilter("patient_id", "==", patient_id))\
                       .where(filter=FieldFilter("submitted_at", ">=", start_date))\
                       .where(filter=FieldFilter("submitted_at", "<=", end_date))\
                       .order_by("submitted_at", direction="DESCENDING")
            return [doc.to_dict() for doc in query.stream()]
        return await self._run_async(_get)

    async def get_sos_alerts_by_date(self, patient_id: str, start_date: datetime, end_date: datetime) -> list[Dict[str, Any]]:
        """Get SOS alerts within a date range."""
        def _get():
            ref = self.db.collection("sos_alerts")
            query = ref.where(filter=FieldFilter("patient_id", "==", patient_id))\
                       .where(filter=FieldFilter("timestamp", ">=", start_date))\
                       .where(filter=FieldFilter("timestamp", "<=", end_date))\
                       .order_by("timestamp", direction="DESCENDING")
            return [doc.to_dict() for doc in query.stream()]
        return await self._run_async(_get)

    async def get_album_entries_count(self, patient_id: str) -> int:
        """Get total count of album entries (simplified for summary)."""
        def _get():
            ref = self.db.collection("patients").document(patient_id).collection("albums")
            # Count queries can be expensive/slow if large, but aggregation queries are supported in newer SDKs
            # For now using stream (inefficient for huge datasets but fine for MVP)
            # Or simplified: just filtered by recent if needed.
            # Let's just get all for now as album size usually isn't massive in this context
            return len(list(ref.stream()))
        return await self._run_async(_get)

    # ==================== Persistent Report Methods ====================

    async def create_report_record(self, report_id: str, patient_id: str, timeframe: str, doctor_name: str) -> Dict[str, Any]:
        """Initialize a report generation record in Firestore."""
        now = datetime.utcnow()
        report_data = {
            "report_id": report_id,
            "patient_id": patient_id,
            "timeframe": timeframe,
            "doctor_name": doctor_name,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "download_url": None,
            "error": None
        }
        
        def _create():
            self.db.collection("reports").document(report_id).set(report_data)
            return report_data
            
        return await self._run_async(_create)

    async def update_report_record(self, report_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a report record in Firestore."""
        update_data["updated_at"] = datetime.utcnow()
        
        def _update():
            self.db.collection("reports").document(report_id).update(update_data)
            return True
            
        return await self._run_async(_update)

    async def get_report_record(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get a report record by ID."""
        def _get():
            doc = self.db.collection("reports").document(report_id).get()
            return doc.to_dict() if doc.exists else None
            
        return await self._run_async(_get)


# Global Firestore service instance
firestore_service = FirestoreService()
