from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field

VALID_STUDY_TYPES = {"LABORATORIO", "ULTRASONIDO", "RECETA", "DIAGNOSTICO", "DOCUMENTO_CLINICO"}
VALID_APPOINTMENT_TYPES = {"MEDICO", "LABORATORIO", "ECO"}
VALID_APPOINTMENT_STATUSES = {"SCHEDULED", "COMPLETED", "CANCELLED"}


class AppointmentCreate(BaseModel):
    appointmentType: str = Field("MEDICO", description="MEDICO, LABORATORIO o ECO")
    appointmentDate: datetime
    doctorOrClinic: str = Field(..., min_length=1, max_length=120)
    specialty: Optional[str] = Field(None, max_length=80)
    momWeightKg: Optional[float] = Field(None, ge=25, le=250)
    bloodPressure: Optional[str] = Field(None, max_length=20)
    babyHeartRateBpm: Optional[int] = Field(None, ge=60, le=240)
    questionsForDoctor: Optional[str] = None
    doctorNotesAndDiagnosis: Optional[str] = None
    status: str = Field("SCHEDULED")
    reminderMinutesBefore: Optional[int] = Field(1440, ge=10, le=10080, description="1440 = 1 día antes")


class AppointmentUpdate(BaseModel):
    appointmentType: Optional[str] = None
    appointmentDate: Optional[datetime] = None
    doctorOrClinic: Optional[str] = Field(None, min_length=1, max_length=120)
    specialty: Optional[str] = Field(None, max_length=80)
    momWeightKg: Optional[float] = Field(None, ge=25, le=250)
    bloodPressure: Optional[str] = Field(None, max_length=20)
    babyHeartRateBpm: Optional[int] = Field(None, ge=60, le=240)
    questionsForDoctor: Optional[str] = None
    doctorNotesAndDiagnosis: Optional[str] = None
    status: Optional[str] = None
    reminderMinutesBefore: Optional[int] = Field(None, ge=10, le=10080)


class AppointmentResponse(BaseModel):
    id: int
    appointmentType: str
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
    reminderMinutesBefore: int = 1440
    googleEventId: Optional[str] = None
    googleEventLink: Optional[str] = None
    googleCalendarTemplateUrl: Optional[str] = None
    icsDownloadUrl: Optional[str] = None
    createdAt: datetime


class CalendarConfigPayload(BaseModel):
    googleCalendarId: Optional[str] = Field(None, max_length=255)


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
    appointmentType: str = "MEDICO"
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
