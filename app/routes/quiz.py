"""
Quiz API routes for quiz management system.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query  # type: ignore
from typing import List, Dict, Any

from app.models.quiz import (  # type: ignore
    QuizCreate,
    QuizResponse,
    QuizSubmission,
    QuizResultResponse,
    QuizListItem
)
from app.models.user import UserInDB  # type: ignore
from app.services.quiz_service import quiz_service  # type: ignore
from app.dependencies.auth import get_current_user, require_role  # type: ignore


router = APIRouter(prefix="/quizzes", tags=["Quizzes"])


@router.post("", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
async def create_quiz(
    quiz_data: QuizCreate,
    current_user: UserInDB = Depends(require_role("caregiver"))
):
    """
    Create a new quiz and assign it to patients.
    
    **Caregiver only endpoint.**
    
    Request body:
    - title: Quiz title
    - description: Optional description
    - questions: List of questions with options and correct answers
    - patient_ids: List of patient IDs to assign this quiz to
    
    Returns:
    - Created quiz data
    
    Raises:
    - 403: If user is not a caregiver
    """
    return await quiz_service.create_quiz(quiz_data, current_user)


@router.get("/patients/me/quizzes", response_model=List[Dict[str, Any]])
async def get_my_quizzes(
    current_user: UserInDB = Depends(require_role("patient"))
):
    """
    Get all quizzes assigned to the current patient.
    
    **Patient only endpoint.**
    
    Returns:
    - List of assigned quizzes with status
    """
    return await quiz_service.get_patient_quizzes(current_user)


@router.get("/created", response_model=List[Dict[str, Any]])
async def get_created_quizzes(
    current_user: UserInDB = Depends(require_role("caregiver"))
):
    """
    Get all quizzes created by the current caregiver.
    
    **Caregiver only endpoint.**
    
    Returns:
    - List of created quizzes
    """
    return await quiz_service.get_created_quizzes(current_user)


@router.post("/{quiz_id}/submit", response_model=QuizResultResponse, status_code=status.HTTP_201_CREATED)
async def submit_quiz(
    quiz_id: str,
    submission: QuizSubmission,
    current_user: UserInDB = Depends(require_role("patient"))
):
    """
    Submit quiz answers and get results.
    
    **Patient only endpoint.**
    
    **IMPORTANT**: Results are persisted to Firestore for analytics.
    
    Request body:
    - answers: List of question_id and selected_answer pairs
    
    Returns:
    - Quiz result with score and detailed answers
    
    Raises:
    - 404: If quiz not found
    - 403: If quiz not assigned to patient
    """
    return await quiz_service.submit_quiz(quiz_id, submission, current_user)


@router.get("/{quiz_id}/results", response_model=List[QuizResultResponse])
async def get_quiz_results(
    quiz_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get all results for a specific quiz.
    
    **Caregiver/Doctor only endpoint.**
    
    - Caregivers can view results for their own quizzes
    - Doctors can view results for their assigned patients
    
    Returns:
    - List of quiz results
    
    Raises:
    - 404: If quiz not found
    - 403: If user not authorized
    """
    return await quiz_service.get_quiz_results(quiz_id, current_user)


@router.get("/patients/{patient_id}/results", response_model=List[QuizResultResponse])
async def get_patient_results(
    patient_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get all quiz results for a specific patient.
    
    **Patient/Caregiver/Doctor endpoint with authorization.**
    
    - Patients can view their own results
    - Caregivers can view results for assigned patients
    - Doctors can view results for assigned patients
    
    Returns:
    - List of quiz results
    
    Raises:
    - 403: If user not authorized
    """
    return await quiz_service.get_patient_results(patient_id, current_user)


@router.get("/results/{result_id}", response_model=QuizResultResponse)
async def get_result(
    result_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get a specific quiz result by ID.
    
    Returns:
    - Detailed quiz result with all answers
    
    Raises:
    - 404: If result not found
    - 403: If user not authorized
    """
    return await quiz_service.get_result_by_id(result_id, current_user)


@router.get("/health")
async def health_check():
    """Health check endpoint for quiz service."""
    return {"status": "healthy", "service": "quiz_management"}
