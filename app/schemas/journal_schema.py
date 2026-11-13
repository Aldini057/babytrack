from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class JournalNoteCreate(BaseModel):
    authorRole: str = Field(..., description="MAMA, PAPA o FAMILIA")
    authorDisplayName: Optional[str] = Field(None, max_length=80)
    title: str = Field(..., min_length=1, max_length=150)
    content: str = Field(..., min_length=1)

class JournalNoteResponse(BaseModel):
    id: int
    authorRole: str
    authorDisplayName: str
    title: str
    content: str
    gestationalWeek: int
    gestationalDay: int
    attachedImagePath: Optional[str]
    createdAt: datetime
