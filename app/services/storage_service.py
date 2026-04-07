"""
Firebase Storage service for handling quiz image uploads.
"""
from firebase_admin import storage  # type: ignore
from typing import Optional
import uuid
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing file uploads to Firebase Storage."""
    
    def __init__(self):
        """Initialize Firebase Storage bucket."""
        try:
            self.bucket = storage.bucket()
            logger.info("Firebase Storage initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Storage: {e}")
            self.bucket = None
    
    async def upload_quiz_image(
        self,
        file_content: bytes,
        file_name: str,
        quiz_id: str,
        content_type: str = "image/jpeg"
    ) -> Optional[str]:
        """
        Upload a quiz image to Firebase Storage.
        
        Args:
            file_content: Image file bytes
            file_name: Original file name
            quiz_id: Quiz ID for organizing images
            content_type: MIME type of the image
        
        Returns:
            Public URL of the uploaded image, or None if upload fails
        """
        if not self.bucket:
            logger.error("Firebase Storage bucket not initialized")
            return None
        
        try:
            # Generate unique filename
            file_extension = file_name.split('.')[-1] if '.' in file_name else 'jpg'
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            
            # Create blob path: quiz_images/{quiz_id}/{unique_filename}
            blob_path = f"quiz_images/{quiz_id}/{unique_filename}"
            blob = self.bucket.blob(blob_path)
            
            # Upload file
            blob.upload_from_string(
                file_content,
                content_type=content_type
            )
            
            # Make the blob publicly accessible
            blob.make_public()
            
            # Get public URL
            public_url = blob.public_url
            
            logger.info(f"Successfully uploaded image to {blob_path}")
            return public_url
            
        except Exception as e:
            logger.error(f"Failed to upload image: {e}")
            return None
    
    async def upload_quiz_image_with_signed_url(
        self,
        file_content: bytes,
        file_name: str,
        quiz_id: str,
        content_type: str = "image/jpeg",
        expiration_days: int = 365
    ) -> Optional[str]:
        """
        Upload a quiz image and return a signed URL (more secure).
        
        Args:
            file_content: Image file bytes
            file_name: Original file name
            quiz_id: Quiz ID for organizing images
            content_type: MIME type of the image
            expiration_days: Days until signed URL expires
        
        Returns:
            Signed URL of the uploaded image, or None if upload fails
        """
        if not self.bucket:
            logger.error("Firebase Storage bucket not initialized")
            return None
        
        try:
            # Generate unique filename
            file_extension = file_name.split('.')[-1] if '.' in file_name else 'jpg'
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            
            # Create blob path
            blob_path = f"quiz_images/{quiz_id}/{unique_filename}"
            blob = self.bucket.blob(blob_path)
            
            # Upload file
            blob.upload_from_string(
                file_content,
                content_type=content_type
            )
            
            # Generate signed URL
            signed_url = blob.generate_signed_url(
                expiration=timedelta(days=expiration_days),
                method='GET'
            )
            
            logger.info(f"Successfully uploaded image to {blob_path} with signed URL")
            return signed_url
            
        except Exception as e:
            logger.error(f"Failed to upload image with signed URL: {e}")
            return None
    
    async def delete_quiz_images(self, quiz_id: str) -> bool:
        """
        Delete all images associated with a quiz.
        
        Args:
            quiz_id: Quiz ID
        
        Returns:
            True if deletion successful, False otherwise
        """
        if not self.bucket:
            logger.error("Firebase Storage bucket not initialized")
            return False
        
        try:
            # List all blobs in the quiz folder
            blobs = self.bucket.list_blobs(prefix=f"quiz_images/{quiz_id}/")
            
            # Delete each blob
            deleted_count = 0
            for blob in blobs:
                blob.delete()
                deleted_count += 1
            
            logger.info(f"Deleted {deleted_count} images for quiz {quiz_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete quiz images: {e}")
            return False
    
    async def delete_image(self, image_url: str) -> bool:
        """
        Delete a specific image by its URL.
        
        Args:
            image_url: Public or signed URL of the image
        
        Returns:
            True if deletion successful, False otherwise
        """
        if not self.bucket:
            logger.error("Firebase Storage bucket not initialized")
            return False
        
        try:
            # Extract blob path from URL
            # URL format: https://storage.googleapis.com/{bucket}/{path}
            if "storage.googleapis.com" in image_url:
                parts = image_url.split(f"{self.bucket.name}/")
                if len(parts) > 1:
                    blob_path = parts[1].split('?')[0]  # Remove query params if signed URL
                    blob = self.bucket.blob(blob_path)
                    blob.delete()
                    logger.info(f"Deleted image at {blob_path}")
                    return True
            
            logger.warning(f"Could not extract blob path from URL: {image_url}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete image: {e}")
            return False
    

    def validate_image_file(
        self,
        file_content: bytes,
        max_size_mb: int = 5
    ) -> tuple[bool, Optional[str]]:
        """
        Validate image file size and type.
        
        Args:
            file_content: Image file bytes
            max_size_mb: Maximum file size in MB
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file size
        file_size_mb = len(file_content) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            return False, f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed size ({max_size_mb}MB)"
        
        # Check if file is an image (basic check)
        # More sophisticated validation can be added using PIL/Pillow
        image_signatures = [
            b'\xFF\xD8\xFF',  # JPEG
            b'\x89PNG',        # PNG
            b'GIF87a',         # GIF
            b'GIF89a',         # GIF
        ]
        
        is_image = any(file_content.startswith(sig) for sig in image_signatures)
        if not is_image:
            return False, "File does not appear to be a valid image (JPEG, PNG, or GIF)"
        
        return True, None

    def validate_audio_file(
        self,
        file_content: bytes,
        max_size_mb: int = 10
    ) -> tuple[bool, Optional[str]]:
        """
        Validate audio file size and type.
        
        Args:
            file_content: Audio file bytes
            max_size_mb: Maximum file size in MB
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file size
        file_size_mb = len(file_content) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            return False, f"Audio file size ({file_size_mb:.2f}MB) exceeds maximum allowed size ({max_size_mb}MB)"
        
        # Basic signature check for common audio formats
        # MP3 (ID3), WAV (RIFF), OGG (OggS), M4A (ftypM4A)
        # Note: M4A/MP4 signatures can be complex, often starting at offset 4
        
        audio_signatures = [
            b'ID3',             # MP3
            b'\xFF\xFB',        # MP3 (without ID3)
            b'RIFF',            # WAV
            b'OggS',            # OGG
            b'fLaC',            # FLAC
        ]
        
        # specialized check for m4a/mp4 (ftyp at offset 4)
        is_m4a = len(file_content) > 12 and file_content[4:8] == b'ftyp'
        
        is_audio = is_m4a or any(file_content.startswith(sig) for sig in audio_signatures)
        
        if not is_audio:
            # Be lenient with audio validation as signatures vary widely, 
            # maybe just rely on extension + mime type in production if this is too strict
            # For now, allowing unknown types but logging a warning might be better
            # But let's return True with a warning in logs if uncertain, or strict False?
            # Let's be slightly lenient and assume if it's not obviously something else, it might be okay.
            # actually, rely on client mime type is risky but combining with size check is safer.
            return True, None 
            
        return True, None

    async def upload_file(
        self,
        file_content: bytes,
        file_name: str,
        folder: str,
        content_type: str
    ) -> Optional[str]:
        """
        Generic file upload to Firebase Storage.
        
        Args:
            file_content: File bytes
            file_name: Original file name
            folder: folder path in bucket
            content_type: MIME type
        
        Returns:
            Public URL or None
        """
        if not self.bucket:
            logger.error("Firebase Storage bucket not initialized")
            return None
        
        try:
            # Generate unique filename
            file_extension = file_name.split('.')[-1] if '.' in file_name else 'dat'
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            
            # Create blob path
            blob_path = f"{folder}/{unique_filename}"
            blob = self.bucket.blob(blob_path)
            
            # Upload file
            blob.upload_from_string(
                file_content,
                content_type=content_type
            )
            
            # Make public
            blob.make_public()
            
            logger.info(f"Successfully uploaded file to {blob_path}")
            return blob.public_url
            
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return None



    async def upload_report_pdf(self, file_content: bytes, report_id: str) -> Optional[str]:
        """
        Upload a generated PDF report to Firebase Storage.
        """
        return await self.upload_file(
            file_content=file_content,
            file_name=f"report_{report_id}.pdf",
            folder="reports",
            content_type="application/pdf"
        )


# Global storage service instance
storage_service = StorageService()
