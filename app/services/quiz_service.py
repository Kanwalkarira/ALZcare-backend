"""
Quiz service for handling quiz business logic.
Includes quiz creation, assignment, submission, and result calculation.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging

from app.models.quiz import (  # type: ignore
    QuizCreate,
    QuizResponse,
    QuizSubmission,
    QuizResult,
    QuizResultAnswer,
    QuizResultResponse,
    QuizQuestion
)
from app.models.user import UserInDB  # type: ignore
from app.services.firestore import firestore_service  # type: ignore
from fastapi import HTTPException, status  # type: ignore

logger = logging.getLogger(__name__)


class QuizService:
    """Service for quiz management and result calculation."""
    
    async def create_quiz(
        self,
        quiz_create: QuizCreate,
        caregiver: UserInDB
    ) -> QuizResponse:
        """
        Create a new quiz and assign it to patients.
        
        Args:
            quiz_create: Quiz creation data
            caregiver: Caregiver creating the quiz
        
        Returns:
            Created quiz data
        
        Raises:
            HTTPException: If caregiver role validation fails
        """
        # Validate caregiver role
        if caregiver.role != "caregiver":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only caregivers can create quizzes"
            )
        
        # Generate quiz ID
        quiz_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Prepare quiz data for Firestore
        quiz_data = {
            "quiz_id": quiz_id,
            "title": quiz_create.title,
            "description": quiz_create.description,
            "caregiver_id": caregiver.uid,
            "caregiver_name": caregiver.name,
            "questions": [q.dict() for q in quiz_create.questions],
            "created_at": now,
            "updated_at": now
        }
        
        # Store quiz in Firestore
        await firestore_service.create_quiz(quiz_data)
        
        # Assign quiz to patients
        for patient_id in quiz_create.patient_ids:
            assignment_data = {
                "quiz_id": quiz_id,
                "patient_id": patient_id,
                "caregiver_id": caregiver.uid,
                "assigned_at": now,
                "status": "pending",
                "completed_at": None
            }
            await firestore_service.assign_quiz_to_patient(assignment_data)
        
        logger.info(f"Quiz {quiz_id} created by caregiver {caregiver.uid} and assigned to {len(quiz_create.patient_ids)} patients")
        
        # Return quiz response
        return QuizResponse(**quiz_data)
    
    async def get_patient_quizzes(self, patient: UserInDB) -> List[Dict[str, Any]]:
        """
        Get all quizzes assigned to a patient.
        
        Args:
            patient: Patient user
        
        Returns:
            List of assigned quizzes
        """
        if patient.role != "patient":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only patients can access this endpoint"
            )
        
        quizzes = await firestore_service.get_patient_quizzes(patient.uid)
        return quizzes
    
    async def get_created_quizzes(self, caregiver: UserInDB) -> List[Dict[str, Any]]:
        """
        Get all quizzes created by a caregiver.
        
        Args:
            caregiver: Caregiver user
        
        Returns:
            List of created quizzes
        """
        if caregiver.role != "caregiver":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only caregivers can access this endpoint"
            )
        
        quizzes = await firestore_service.get_quizzes_by_caregiver(caregiver.uid)
        return quizzes
    
    async def submit_quiz(
        self,
        quiz_id: str,
        submission: QuizSubmission,
        patient: UserInDB
    ) -> QuizResultResponse:
        """
        Submit quiz answers and calculate score.
        CRITICAL: This method persists results to Firestore.
        
        Args:
            quiz_id: Quiz ID
            submission: Patient's answers
            patient: Patient submitting the quiz
        
        Returns:
            Quiz result with score
        
        Raises:
            HTTPException: If quiz not found or not assigned to patient
        """
        # Validate patient role
        if patient.role != "patient":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only patients can submit quizzes"
            )
        
        # Get quiz data
        quiz = await firestore_service.get_quiz(quiz_id)
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found"
            )
        
        # Verify quiz is assigned to this patient
        patient_quizzes = await firestore_service.get_patient_quizzes(patient.uid)
        assigned_quiz_ids = [q["quiz_id"] for q in patient_quizzes]
        
        if quiz_id not in assigned_quiz_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Quiz not assigned to you"
            )
        
        # Calculate score
        questions = [QuizQuestion(**q) for q in quiz["questions"]]
        result_answers = []
        correct_count = 0
        
        # Create answer lookup
        answer_dict = {ans.question_id: ans.selected_answer for ans in submission.answers}
        
        for question in questions:
            selected = answer_dict.get(question.question_id, "")
            is_correct = selected == question.correct_answer
            
            if is_correct:
                correct_count += 1
            
            result_answers.append(QuizResultAnswer(
                question_id=question.question_id,
                question_text=question.text,
                selected_answer=selected,
                correct_answer=question.correct_answer,
                is_correct=is_correct
            ))
        
        total_questions = len(questions)
        score = (correct_count / total_questions * 100) if total_questions > 0 else 0
        
        # Get patient's doctor (if assigned)
        doctor = await firestore_service.get_patient_doctor(patient.uid)
        
        # Prepare result data
        result_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        result_data = {
            "result_id": result_id,
            "quiz_id": quiz_id,
            "quiz_title": quiz["title"],
            "patient_id": patient.uid,
            "patient_name": patient.name,
            "patient_email": patient.email,
            "caregiver_id": quiz["caregiver_id"],
            "caregiver_name": quiz["caregiver_name"],
            "doctor_id": doctor["doctor_id"] if doctor else None,
            "doctor_name": doctor["doctor_name"] if doctor else None,
            "answers": [ans.dict() for ans in result_answers],
            "score": round(score, 2),
            "total_questions": total_questions,
            "correct_answers": correct_count,
            "submitted_at": now
        }
        
        # **PERSIST RESULT TO FIRESTORE** - This is the critical step
        await firestore_service.submit_quiz_result(result_data)
        
        logger.info(f"Quiz {quiz_id} submitted by patient {patient.uid} with score {score:.2f}%")
        
        # Return result response
        return QuizResultResponse(**result_data)
    
    async def get_quiz_results(
        self,
        quiz_id: str,
        current_user: UserInDB
    ) -> List[QuizResultResponse]:
        """
        Get all results for a quiz (caregiver/doctor only).
        
        Args:
            quiz_id: Quiz ID
            current_user: Current user
        
        Returns:
            List of quiz results
        
        Raises:
            HTTPException: If user not authorized
        """
        # Get quiz to verify ownership
        quiz = await firestore_service.get_quiz(quiz_id)
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found"
            )
        
        # Authorization check
        if current_user.role == "caregiver":
            if quiz["caregiver_id"] != current_user.uid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view results for your own quizzes"
                )
        elif current_user.role not in ["doctor", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only caregivers and doctors can view quiz results"
            )
        
        # Fetch results from Firestore (not recalculated)
        results = await firestore_service.get_quiz_results(quiz_id)
        
        return [QuizResultResponse(**r) for r in results]
    
    async def get_patient_results(
        self,
        patient_id: str,
        current_user: UserInDB
    ) -> List[QuizResultResponse]:
        """
        Get all quiz results for a patient.
        
        Args:
            patient_id: Patient ID
            current_user: Current user
        
        Returns:
            List of quiz results
        
        Raises:
            HTTPException: If user not authorized
        """
        # Authorization check
        if current_user.role == "patient":
            # Patients can only view their own results
            if current_user.uid != patient_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own results"
                )
        elif current_user.role == "caregiver":
            # Caregivers can view results for their assigned patients
            caregivers = await firestore_service.get_patient_caregivers(patient_id)
            caregiver_ids = [c["caregiver_id"] for c in caregivers]
            
            if current_user.uid not in caregiver_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view results for your assigned patients"
                )
        elif current_user.role == "doctor":
            # Doctors can view results for their assigned patients
            doctor = await firestore_service.get_patient_doctor(patient_id)
            
            if not doctor or doctor["doctor_id"] != current_user.uid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view results for your assigned patients"
                )
        elif current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized to view patient results"
            )
        
        # Fetch results from Firestore
        results = await firestore_service.get_patient_results(patient_id)
        
        return [QuizResultResponse(**r) for r in results]
    
    async def get_result_by_id(
        self,
        result_id: str,
        current_user: UserInDB
    ) -> QuizResultResponse:
        """
        Get a specific quiz result.
        
        Args:
            result_id: Result ID
            current_user: Current user
        
        Returns:
            Quiz result
        
        Raises:
            HTTPException: If result not found or user not authorized
        """
        result = await firestore_service.get_quiz_result(result_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Result not found"
            )
        
        # Authorization check
        if current_user.role == "patient":
            if result["patient_id"] != current_user.uid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own results"
                )
        elif current_user.role == "caregiver":
            if result["caregiver_id"] != current_user.uid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view results for your quizzes"
                )
        elif current_user.role == "doctor":
            if result.get("doctor_id") != current_user.uid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view results for your assigned patients"
                )
        elif current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized to view this result"
            )
        
        return QuizResultResponse(**result)


# Global quiz service instance
quiz_service = QuizService()
