"""
Supabase Storage service for handling quiz image and file uploads.
"""
from supabase import create_client, Client # type: ignore
from typing import Optional
import uuid
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing file uploads to Supabase Storage."""
    
    def __init__(self):
        """Initialize Supabase client."""
        try:
            self.supabase: Client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY
            )
            self.bucket_name = settings.SUPABASE_BUCKET
            logger.info("Supabase Storage initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase Storage: {e}")
            self.supabase = None
    
    async def upload_quiz_image(
        self,
        file_content: bytes,
        file_name: str,
        quiz_id: str,
        content_type: str = "image/jpeg"
    ) -> Optional[str]:
        """
        Upload a quiz image to Supabase Storage.
        """
        folder = f"quiz_images/{quiz_id}"
        return await self.upload_file(
            file_content=file_content,
            file_name=file_name,
            folder=folder,
            content_type=content_type
        )
    
    async def upload_file(
        self,
        file_content: bytes,
        file_name: str,
        folder: str,
        content_type: str
    ) -> Optional[str]:
        """
        Generic file upload to Supabase Storage.
        """
        if not self.supabase:
            logger.error("Supabase client not initialized")
            return None
        
        try:
            # Generate unique filename
            file_extension = file_name.split('.')[-1] if '.' in file_name else 'dat'
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            
            # Create path
            path = f"{folder}/{unique_filename}"
            
            # Upload to Supabase
            # Note: storage.upload expects bytes or a file-like object
            self.supabase.storage.from_(self.bucket_name).upload(
                path=path,
                file=file_content,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            
            # Get public URL
            response = self.supabase.storage.from_(self.bucket_name).get_public_url(path)
            
            logger.info(f"Successfully uploaded file to {path}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to upload file to Supabase: {e}")
            return None
    
    async def delete_image(self, image_url: str) -> bool:
        """
        Delete a specific image by its URL.
        """
        if not self.supabase:
            return False
            
        try:
            # Extract path from URL
            # Supabase URL format: https://[project].supabase.co/storage/v1/object/public/[bucket]/[path]
            prefix = f"/storage/v1/object/public/{self.bucket_name}/"
            if prefix in image_url:
                path = image_url.split(prefix)[1]
                self.supabase.storage.from_(self.bucket_name).remove([path])
                logger.info(f"Deleted image at {path}")
                return True
            
            logger.warning(f"Could not extract path from Supabase URL: {image_url}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete image from Supabase: {e}")
            return False

    async def delete_quiz_images(self, quiz_id: str) -> bool:
        """
        Delete all images associated with a quiz.
        """
        if not self.supabase:
            return False
            
        try:
            # List files in folder
            prefix = f"quiz_images/{quiz_id}/"
            files = self.supabase.storage.from_(self.bucket_name).list(prefix)
            
            if not files:
                return True
                
            paths = [f"{prefix}{file['name']}" for file in files]
            self.supabase.storage.from_(self.bucket_name).remove(paths)
            
            logger.info(f"Deleted {len(paths)} images for quiz {quiz_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete quiz images from Supabase: {e}")
            return False

    async def upload_report_pdf(self, file_content: bytes, report_id: str) -> Optional[str]:
        """
        Upload a generated PDF report to Supabase Storage.
        """
        return await self.upload_file(
            file_content=file_content,
            file_name=f"report_{report_id}.pdf",
            folder="reports",
            content_type="application/pdf"
        )

    def validate_image_file(self, file_content: bytes, max_size_mb: int = 5) -> tuple[bool, Optional[str]]:
        # Keeping existing validation logic
        file_size_mb = len(file_content) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            return False, f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed size ({max_size_mb}MB)"
        
        image_signatures = [b'\xFF\xD8\xFF', b'\x89PNG', b'GIF87a', b'GIF89a']
        if not any(file_content.startswith(sig) for sig in image_signatures):
            return False, "File does not appear to be a valid image"
        return True, None

    def validate_audio_file(self, file_content: bytes, max_size_mb: int = 10) -> tuple[bool, Optional[str]]:
        file_size_mb = len(file_content) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            return False, f"Audio file size ({file_size_mb:.2f}MB) exceeds maximum allowed size ({max_size_mb}MB)"
        return True, None


# Global storage service instance
storage_service = StorageService()
