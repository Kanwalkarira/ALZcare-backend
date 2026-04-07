"""
Image upload API routes for quiz images.
"""
from fastapi import APIRouter, File, UploadFile, HTTPException, status, Depends  # type: ignore
from typing import Dict

from app.services.storage_service import storage_service  # type: ignore
from app.dependencies.auth import require_role  # type: ignore
from app.models.user import UserInDB  # type: ignore


router = APIRouter(prefix="/upload", tags=["Upload"])


@router.post("/quiz-image", response_model=Dict[str, str])
async def upload_quiz_image(
    quiz_id: str,
    file: UploadFile = File(...),
    current_user: UserInDB = Depends(require_role("caregiver"))
):
    """
    Upload a quiz image to Supabase Storage.
    
    **Caregiver only endpoint.**
    
    Query parameters:
    - quiz_id: Quiz ID to associate the image with
    
    Form data:
    - file: Image file (JPEG, PNG, or GIF, max 5MB)
    
    Returns:
    - image_url: Public URL of the uploaded image
    
    Raises:
    - 400: If file validation fails
    - 403: If user is not a caregiver
    """
    # Read file content
    file_content = await file.read()
    
    # Validate file
    is_valid, error_message = storage_service.validate_image_file(file_content)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
    # Determine content type
    content_type = file.content_type or "image/jpeg"
    
    # Upload to Firebase Storage
    image_url = await storage_service.upload_quiz_image(
        file_content=file_content,
        file_name=file.filename or "image.jpg",
        quiz_id=quiz_id,
        content_type=content_type
    )
    
    if not image_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image to Supabase Storage"
        )
    
    return {"image_url": image_url}


@router.get("/health")
async def health_check():
    """Health check endpoint for upload service."""
    return {"status": "healthy", "service": "image_upload"}
