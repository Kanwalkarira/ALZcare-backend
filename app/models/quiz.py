"""
Pydantic models for quiz management system.
"""
from pydantic import BaseModel, Field, validator  # type: ignore
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class QuizQuestion(BaseModel):
    """Individual quiz question with options and correct answer."""
    question_id: str = Field(..., description="Unique question identifier")
    text: str = Field(..., min_length=1, max_length=500, description="Question text")
    image_url: Optional[str] = Field(None, description="URL to question image in Firebase Storage")
    options: List[str] = Field(..., min_items=2, max_items=6, description="Answer options")
    correct_answer: str = Field(..., description="The correct answer (must be one of the options)")
    
    @validator('correct_answer')
    def validate_correct_answer(cls, v, values):
        """Ensure correct answer is one of the options."""
        if 'options' in values and v not in values['options']:
            raise ValueError('correct_answer must be one of the provided options')
        return v


class QuizCreate(BaseModel):
    """Request model for creating a new quiz."""
    title: str = Field(..., min_length=1, max_length=200, description="Quiz title")
    description: Optional[str] = Field(None, max_length=1000, description="Quiz description")
    questions: List[QuizQuestion] = Field(..., min_items=1, description="List of quiz questions")
    patient_ids: List[str] = Field(..., min_items=1, description="Patient IDs to assign this quiz to")


class QuizResponse(BaseModel):
    """Quiz data returned to clients."""
    quiz_id: str
    title: str
    description: Optional[str]
    caregiver_id: str
    caregiver_name: str
    questions: List[QuizQuestion]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class QuizAssignment(BaseModel):
    """Patient-quiz assignment."""
    quiz_id: str
    patient_id: str
    caregiver_id: str
    assigned_at: datetime
    status: str = Field(default="pending", description="pending, completed, expired")
    completed_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class QuestionAnswer(BaseModel):
    """Patient's answer to a single question."""
    question_id: str
    selected_answer: str


class QuizSubmission(BaseModel):
    """Patient's quiz submission."""
    answers: List[QuestionAnswer] = Field(..., min_items=1, description="List of answers")


class QuizResultAnswer(BaseModel):
    """Detailed answer result for storage."""
    question_id: str
    question_text: str
    selected_answer: str
    correct_answer: str
    is_correct: bool


class QuizResult(BaseModel):
    """Complete quiz result stored in Firestore."""
    result_id: str
    quiz_id: str
    quiz_title: str
    patient_id: str
    patient_name: str
    patient_email: str
    caregiver_id: str
    caregiver_name: str
    doctor_id: Optional[str] = None
    doctor_name: Optional[str] = None
    answers: List[QuizResultAnswer]
    score: float = Field(..., ge=0, le=100, description="Score as percentage")
    total_questions: int
    correct_answers: int
    submitted_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class QuizResultResponse(BaseModel):
    """Quiz result data for dashboards."""
    result_id: str
    quiz_id: str
    quiz_title: str
    patient_id: str
    patient_name: str
    caregiver_id: str
    caregiver_name: str
    doctor_id: Optional[str]
    doctor_name: Optional[str]
    score: float
    total_questions: int
    correct_answers: int
    submitted_at: datetime
    answers: Optional[List[QuizResultAnswer]] = None  # Include for detailed view
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class QuizStatus(str, Enum):
    """Quiz assignment status."""
    pending = "pending"
    completed = "completed"
    expired = "expired"


class QuizListItem(BaseModel):
    """Simplified quiz info for list views."""
    quiz_id: str
    title: str
    description: Optional[str]
    total_questions: int
    status: str = "pending"
    assigned_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
