from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Date, DateTime
from app.database import Base


class MediaMoment(Base):
    __tablename__ = "media_moments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(150), nullable=False)
    caption = Column(Text, nullable=True)
    moment_date = Column(Date, nullable=False, index=True)
    gestational_week = Column(Integer, nullable=False)
    gestational_day = Column(Integer, nullable=False)
    image_relative_path = Column(Text, nullable=False)
    uploaded_by = Column(String(20), nullable=False, default="MAMA")  # MAMA, PAPA
    created_at = Column(DateTime, default=datetime.utcnow)


class DocumentVaultItem(Base):
    __tablename__ = "document_vault_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    category = Column(String(50), nullable=False, index=True)  # POLIZA, CARNET, IDENTIFICACION, INGRESO_HOSPITAL, OTRO
    title = Column(String(150), nullable=False)
    notes = Column(Text, nullable=True)
    original_filename = Column(String(255), nullable=False)
    stored_relative_path = Column(Text, nullable=False)
    mime_type = Column(String(80), nullable=False)
    file_category = Column(String(20), nullable=False)  # PDF, IMAGE
    file_size_bytes = Column(Integer, nullable=False)
    uploaded_by = Column(String(20), nullable=False, default="PAPA")  # MAMA, PAPA
    created_at = Column(DateTime, default=datetime.utcnow)
