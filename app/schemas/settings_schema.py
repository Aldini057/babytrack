from datetime import date
from typing import Optional
from pydantic import BaseModel, Field

class GestationalAgeResponse(BaseModel):
    weeks: int
    days: int
    elapsedDays: int
    daysRemaining: int
    trimester: int
    trimesterName: str
    progressPercent: float
    sizeComparison: str
    sizeWeight: str
    currentDate: str

class PregnancySettingsResponse(BaseModel):
    id: int
    babyNickname: str
    dueDate: str
    genderMode: str
    momName: str
    dadName: str
    bloodTypeMom: Optional[str] = None
    allergiesNotes: Optional[str] = None
    calibrationOffsetDays: int
    gestationalAge: GestationalAgeResponse

class ObstetricCalibrationRequest(BaseModel):
    dueDate: Optional[date] = None
    calibrationOffsetDays: Optional[int] = None
    # Calibración intuitiva: "Hoy cumplimos X semanas y Y días"
    currentWeeks: Optional[int] = Field(None, ge=0, le=45)
    currentDays: Optional[int] = Field(None, ge=0, le=6)
    bloodTypeMom: Optional[str] = Field(None, max_length=10)
    allergiesNotes: Optional[str] = None

class GenderThemeUpdateRequest(BaseModel):
    genderMode: str = Field(..., description="SURPRISE, BOY, o GIRL")
    babyNickname: Optional[str] = None
