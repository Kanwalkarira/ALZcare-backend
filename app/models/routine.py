from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class RoutineBase(BaseModel):
    patient_id: str
    task: str = Field(..., min_length=1, max_length=200)
    time: str = Field(..., description="Time of the routine in HH:MM format")

class RoutineCreate(RoutineBase):
    pass

class RoutineUpdate(BaseModel):
    task: Optional[str] = None
    time: Optional[str] = None
    checked: Optional[bool] = None

class RoutineResponse(RoutineBase):
    routine_id: str
    caregiver_id: str
    checked: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
