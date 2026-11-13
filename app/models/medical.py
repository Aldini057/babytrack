from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class MedicalAppointment(Base):
    __tablename__ = "medical_appointments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    appointment_date = Column(DateTime, nullable=False, index=True)
    doctor_or_clinic = Column(String(120), nullable=False)
    specialty = Column(String(80), default="Ginecología y Obstetricia")
    gestational_week = Column(Integer, nullable=False)
    gestational_day = Column(Integer, nullable=False)
    mom_weight_kg = Column(Numeric(5, 2), nullable=True)
    blood_pressure = Column(String(20), nullable=True)
    baby_heart_rate_bpm = Column(Integer, nullable=True)
    questions_for_doctor = Column(Text, nullable=True)
    doctor_notes_and_diagnosis = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="SCHEDULED")  # SCHEDULED, COMPLETED, CANCELLED
    created_at = Column(DateTime, default=datetime.utcnow)

    studies = relationship("MedicalStudy", back_populates="appointment")


class MedicalStudy(Base):
    __tablename__ = "medical_studies"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    appointment_id = Column(Integer, ForeignKey("medical_appointments.id", ondelete="SET NULL"), nullable=True)
    study_type = Column(String(30), nullable=False, index=True)  # LABORATORIO, ULTRASONIDO, RECETA, DOCUMENTO_CLINICO
    title = Column(String(150), nullable=False)
    study_date = Column(Date, nullable=False)
    gestational_week = Column(Integer, nullable=False)
    gestational_day = Column(Integer, nullable=False)
    summary_notes = Column(Text, nullable=True)
    created_by = Column(String(20), nullable=False, default="PAPA")  # MAMA, PAPA
    created_at = Column(DateTime, default=datetime.utcnow)

    appointment = relationship("MedicalAppointment", back_populates="studies")
    attachments = relationship(
        "StudyAttachment",
        back_populates="study",
        cascade="all, delete-orphan",
        order_by="StudyAttachment.id.asc()"
    )


class StudyAttachment(Base):
    __tablename__ = "study_attachments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    study_id = Column(Integer, ForeignKey("medical_studies.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_relative_path = Column(Text, nullable=False)
    mime_type = Column(String(80), nullable=False)  # application/pdf, image/jpeg, image/png, image/webp
    file_category = Column(String(20), nullable=False)  # PDF, IMAGE
    file_size_bytes = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    study = relationship("MedicalStudy", back_populates="attachments")
