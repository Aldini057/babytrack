from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base

class BabyJournalNote(Base):
    __tablename__ = "baby_journal_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    author_role = Column(String(20), nullable=False, index=True)  # MAMA, PAPA
    author_display_name = Column(String(80), nullable=False)
    title = Column(String(150), nullable=False)
    content = Column(Text, nullable=False)
    gestational_week = Column(Integer, nullable=False)
    gestational_day = Column(Integer, nullable=False)
    attached_image_path = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
