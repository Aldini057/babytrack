from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

VALID_CATEGORIES = {
    "HABITACION",
    "TRANSPORTE",
    "ALIMENTACION",
    "HIGIENE",
    "ROPA",
    "HOSPITAL"
}

class ChecklistItemCreate(BaseModel):
    category: str
    itemName: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = None
    trimesterPriority: int = Field(1, ge=1, le=3)
    quantity: int = Field(1, ge=1)
    estimatedCostMxn: float = Field(0.0, ge=0)
    actualCostMxn: float = Field(0.0, ge=0)
    referenceUrl: Optional[str] = None

class ChecklistItemUpdate(BaseModel):
    category: Optional[str] = None
    itemName: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = None
    trimesterPriority: Optional[int] = Field(None, ge=1, le=3)
    quantity: Optional[int] = Field(None, ge=1)
    estimatedCostMxn: Optional[float] = Field(None, ge=0)
    actualCostMxn: Optional[float] = Field(None, ge=0)
    referenceUrl: Optional[str] = None
    isCompleted: Optional[bool] = None
    completedBy: Optional[str] = None

class ChecklistToggleRequest(BaseModel):
    completedBy: str = Field("MAMA", description="MAMA o PAPA")
    actualCostMxn: Optional[float] = Field(None, ge=0)

class ChecklistItemResponse(BaseModel):
    id: int
    category: str
    itemName: str
    description: Optional[str]
    trimesterPriority: int
    quantity: int
    estimatedCostMxn: float
    actualCostMxn: float
    referenceUrl: Optional[str]
    isCompleted: bool
    completedBy: Optional[str]
    completedAt: Optional[datetime]
    createdAt: datetime

class TrimesterSummary(BaseModel):
    trimester: int
    totalItems: int
    completedItems: int
    progressPercent: float
    estimatedCostMxn: float
    actualCostMxn: float

class CategorySummary(BaseModel):
    category: str
    totalItems: int
    completedItems: int
    progressPercent: float
    estimatedCostMxn: float
    actualCostMxn: float

class ChecklistSummaryResponse(BaseModel):
    totalItems: int
    completedItems: int
    progressPercent: float
    totalEstimatedCostMxn: float
    totalActualCostMxn: float
    byTrimester: List[TrimesterSummary]
    byCategory: List[CategorySummary]
