from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Date, Text, DateTime
from app.database import Base

class PregnancySettings(Base):
    __tablename__ = "pregnancy_settings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    baby_nickname = Column(String(80), nullable=False, default="Nuestro Bebé")
    due_date = Column(Date, nullable=False, default=date(2027, 7, 7))
    calibration_offset_days = Column(Integer, nullable=False, default=1)
    gender_mode = Column(String(20), nullable=False, default="SURPRISE")  # SURPRISE, BOY, GIRL
    mom_name = Column(String(80), nullable=False, default="Mamá")
    dad_name = Column(String(80), nullable=False, default="Papá")
    blood_type_mom = Column(String(10), nullable=True)
    allergies_notes = Column(Text, nullable=True)
    google_calendar_id = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
