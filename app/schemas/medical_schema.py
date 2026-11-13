from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field

VALID_STUDY_TYPES = {"LABORATORIO", "ULTRASONIDO", "RECETA", "DOCUMENTO_CLINICO"}
VALID_APPOINTMENT_STATUSES = {"SCHEDULED", "COMPLETED", "CANCELLED"}


class AppointmentCreate(BaseModel):
    appointmentDate: datetime
    doctorOrClinic: str = Field(..., min_length=1, max_length=120)
    specialty: str = Field("Ginecología y Obstetricia", max_length=80)
    momWeightKg: Optional[float] = Field(None, ge=25, le=250)
    bloodPressure: Optional[str] = Field(None, max_length=20)
    babyHeartRateBpm: Optional[int] = Field(None, ge=60, le=240)
    questionsForDoctor: Optional[str] = None
    doctorNotesAndDiagnosis: Optional[str] = None
    status: str = Field("SCHEDULED")


class AppointmentUpdate(BaseModel):
    appointmentDate: Optional[datetime] = None
    doctorOrClinic: Optional[str] = Field(None, min_length=1, max_length=120)
    specialty: Optional[str] = Field(None, max_length=80)
    momWeightKg: Optional[float] = Field(None, ge=25, le=250)
    bloodPressure: Optional[str] = Field(None, max_length=20)
    babyHeartRateBpm: Optional[int] = Field(None, ge=60, le=240)
    questionsForDoctor: Optional[str] = None
    doctorNotesAndDiagnosis: Optional[str] = None
    status: Optional[str] = None


class AppointmentResponse(BaseModel):
    id: int
    appointmentDate: datetime
    doctorOrClinic: str
    specialty: Optional[str]
    gestationalWeek: int
    gestationalDay: int
    momWeightKg: Optional[float]
    bloodPressure: Optional[str]
    babyHeartRateBpm: Optional[int]
    questionsForDoctor: Optional[str]
    doctorNotesAndDiagnosis: Optional[str]
    status: str
    createdAt: datetime


class StudyAttachmentResponse(BaseModel):
    id: int
    studyId: int
    originalFilename: str
    storedRelativePath: str
    url: str
    mimeType: str
    fileCategory: str  # PDF | IMAGE
    fileSizeBytes: int
    uploadedAt: datetime


class MedicalStudyResponse(BaseModel):
    id: int
    appointmentId: Optional[int]
    studyType: str
    title: str
    studyDate: date
    gestationalWeek: int
    gestationalDay: int
    summaryNotes: Optional[str]
    createdBy: str
    createdAt: datetime
    attachments: List[StudyAttachmentResponse] = []


class LatestVitalsSummary(BaseModel):
    momWeightKg: Optional[float] = None
    bloodPressure: Optional[str] = None
    babyHeartRateBpm: Optional[int] = None
    recordedAt: Optional[datetime] = None
    doctorOrClinic: Optional[str] = None


class PendingQuestionItem(BaseModel):
    appointmentId: int
    appointmentDate: datetime
    doctorOrClinic: str
    questions: str


class ConsultationModeResponse(BaseModel):
    babyNickname: str
    dueDate: str
    momName: str
    momBloodType: Optional[str]
    allergiesNotes: Optional[str]
    currentWeeks: int
    currentDays: int
    trimesterName: str
    daysRemaining: int
    latestVitals: Optional[LatestVitalsSummary]
    pendingQuestions: List[PendingQuestionItem]
    recentStudies: List[MedicalStudyResponse]
    recentUltrasounds: List[MedicalStudyResponse]
