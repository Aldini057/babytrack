from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

VALID_VAULT_CATEGORIES = {
    "POLIZA",
    "CARNET",
    "IDENTIFICACION",
    "INGRESO_HOSPITAL",
    "OTRO",
}


class MediaMomentResponse(BaseModel):
    id: int
    title: str
    caption: Optional[str]
    momentDate: date
    gestationalWeek: int
    gestationalDay: int
    imageRelativePath: str
    imageUrl: str
    uploadedBy: str
    createdAt: datetime


class DocumentVaultItemResponse(BaseModel):
    id: int
    category: str
    title: str
    notes: Optional[str]
    originalFilename: str
    storedRelativePath: str
    url: str
    mimeType: str
    fileCategory: str  # PDF | IMAGE
    fileSizeBytes: int
    uploadedBy: str
    createdAt: datetime
