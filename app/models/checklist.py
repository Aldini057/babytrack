from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, DateTime
from app.database import Base

class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    category = Column(String(50), nullable=False, index=True)  # HABITACION, TRANSPORTE, ALIMENTACION, HIGIENE, ROPA, HOSPITAL
    item_name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    trimester_priority = Column(Integer, nullable=False, default=1)  # 1, 2 o 3
    quantity = Column(Integer, nullable=False, default=1)
    estimated_cost_mxn = Column(Numeric(10, 2), default=0.00)
    actual_cost_mxn = Column(Numeric(10, 2), default=0.00)
    reference_url = Column(Text, nullable=True)
    is_completed = Column(Boolean, nullable=False, default=False)
    completed_by = Column(String(20), nullable=True)  # MAMA, PAPA
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
