"""
Firebase Cloud Messaging (FCM) service for sending push notifications.
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

try:
    from firebase_admin import messaging
except ImportError:
    messaging = None
    logging.warning("firebase_admin.messaging not available. FCM notifications will not work.")

from app.config import settings

logger = logging.getLogger(__name__)


class FCMService:
    """Service for sending Firebase Cloud Messaging notifications."""
    
    def __init__(self):
        """Initialize FCM service."""
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.enabled = messaging is not None
    
    async def _run_async(self, func, *args, **kwargs):
        """Run a synchronous FCM operation asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args, **kwargs)
    
    def _send_notification_sync(self, token: str, title: str, body: str, data: Dict[str, str]) -> Optional[str]:
        """
        Send a single FCM notification synchronously.
        
        Args:
            token: FCM device token
            title: Notification title
            body: Notification body
            data: Additional data payload
            
        Returns:
            Message ID if successful, None otherwise
        """
        if not self.enabled:
            logger.warning("FCM is not enabled. Skipping notification.")
            return None
        
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data,
                token=token,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        sound='default',
                        priority='high',
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound='default',
                            badge=1,
                        ),
                    ),
                ),
            )
            
            response = messaging.send(message)
            logger.info(f"Successfully sent FCM notification: {response}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to send FCM notification: {str(e)}")
            return None
    
    async def send_notification(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Send a push notification to a single device.
        
        Args:
            token: FCM device token
            title: Notification title
            body: Notification body
            data: Optional additional data
            
        Returns:
            Message ID if successful, None otherwise
        """
        if data is None:
            data = {}
        
        return await self._run_async(
            self._send_notification_sync,
            token, title, body, data
        )
    
    async def send_sos_alert(
        self,
        token: str,
        patient_name: str,
        alert_id: str,
        latitude: float,
        longitude: float
    ) -> Optional[str]:
        """
        Send SOS alert notification to a caregiver.
        
        Args:
            token: Caregiver's FCM device token
            patient_name: Name of the patient
            alert_id: SOS alert ID
            latitude: Patient's latitude
            longitude: Patient's longitude
            
        Returns:
            Message ID if successful, None otherwise
        """
        title = f"🚨 SOS Alert from {patient_name}"
        body = f"{patient_name} has triggered an emergency alert. Tap to view location."
        
        data = {
            "type": "sos_alert",
            "alert_id": alert_id,
            "patient_name": patient_name,
            "latitude": str(latitude),
            "longitude": str(longitude),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        return await self.send_notification(token, title, body, data)
    
    async def send_bulk_notifications(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None
    ) -> Dict[str, Optional[str]]:
        """
        Send notifications to multiple devices.
        
        Args:
            tokens: List of FCM device tokens
            title: Notification title
            body: Notification body
            data: Optional additional data
            
        Returns:
            Dictionary mapping tokens to message IDs (or None if failed)
        """
        if data is None:
            data = {}
        
        tasks = [
            self.send_notification(token, title, body, data)
            for token in tokens
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            token: result if not isinstance(result, Exception) else None
            for token, result in zip(tokens, results)
        }
    
    async def send_sos_to_caregivers(
        self,
        caregivers: List[Dict[str, Any]],
        patient_name: str,
        alert_id: str,
        latitude: float,
        longitude: float
    ) -> List[Dict[str, Any]]:
        """
        Send SOS alert to multiple caregivers.
        
        Args:
            caregivers: List of caregiver dictionaries with fcm_token
            patient_name: Name of the patient
            alert_id: SOS alert ID
            latitude: Patient's latitude
            longitude: Patient's longitude
            
        Returns:
            List of notification results with status
        """
        results = []
        
        for caregiver in caregivers:
            fcm_token = caregiver.get('fcm_token')
            
            if not fcm_token:
                logger.warning(f"Caregiver {caregiver.get('caregiver_name')} has no FCM token")
                results.append({
                    'caregiver_id': caregiver.get('caregiver_id'),
                    'status': 'failed',
                    'error': 'No FCM token',
                    'message_id': None
                })
                continue
            
            message_id = await self.send_sos_alert(
                fcm_token,
                patient_name,
                alert_id,
                latitude,
                longitude
            )
            
            results.append({
                'caregiver_id': caregiver.get('caregiver_id'),
                'caregiver_name': caregiver.get('caregiver_name'),
                'status': 'sent' if message_id else 'failed',
                'message_id': message_id,
                'error': None if message_id else 'Failed to send'
            })
        
        return results


# Global FCM service instance
fcm_service = FCMService()
