from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.medical import MedicalAppointment, MedicalStudy, StudyAttachment
from app.schemas.medical_schema import (
    VALID_APPOINTMENT_STATUSES,
    VALID_STUDY_TYPES,
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
    ConsultationModeResponse,
    LatestVitalsSummary,
    MedicalStudyResponse,
    PendingQuestionItem,
    StudyAttachmentResponse,
)
from app.api.v1.endpoints_settings import get_or_create_settings
from app.services.obstetric_calculator import ObstetricCalculatorService
from app.services.storage_service import HybridStorageService

router = APIRouter()


def _appointment_to_response(item: MedicalAppointment) -> AppointmentResponse:
    return AppointmentResponse(
        id=item.id,
        appointmentDate=item.appointment_date,
        doctorOrClinic=item.doctor_or_clinic,
        specialty=item.specialty,
        gestationalWeek=item.gestational_week,
        gestationalDay=item.gestational_day,
        momWeightKg=float(item.mom_weight_kg) if item.mom_weight_kg is not None else None,
        bloodPressure=item.blood_pressure,
        babyHeartRateBpm=item.baby_heart_rate_bpm,
        questionsForDoctor=item.questions_for_doctor,
        doctorNotesAndDiagnosis=item.doctor_notes_and_diagnosis,
        status=item.status,
        createdAt=item.created_at,
    )


def _attachment_to_response(att: StudyAttachment) -> StudyAttachmentResponse:
    return StudyAttachmentResponse(
        id=att.id,
        studyId=att.study_id,
        originalFilename=att.original_filename,
        storedRelativePath=att.stored_relative_path,
        url=f"/{att.stored_relative_path}",
        mimeType=att.mime_type,
        fileCategory=att.file_category,
        fileSizeBytes=att.file_size_bytes,
        uploadedAt=att.uploaded_at,
    )


def _study_to_response(study: MedicalStudy) -> MedicalStudyResponse:
    return MedicalStudyResponse(
        id=study.id,
        appointmentId=study.appointment_id,
        studyType=study.study_type,
        title=study.title,
        studyDate=study.study_date,
        gestationalWeek=study.gestational_week,
        gestationalDay=study.gestational_day,
        summaryNotes=study.summary_notes,
        createdBy=study.created_by,
        createdAt=study.created_at,
        attachments=[_attachment_to_response(att) for att in study.attachments],
    )


# ==============================================================================
# CITAS MÉDICAS Y CONTROL PRENATAL
# ==============================================================================


@router.get("/appointments", response_model=List[AppointmentResponse])
def list_appointments(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    """Lista las citas médicas prenatales ordenadas por fecha descendente."""
    query = db.query(MedicalAppointment)
    if status_filter:
        st = status_filter.upper()
        if st not in VALID_APPOINTMENT_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estado inválido. Válidos: {sorted(VALID_APPOINTMENT_STATUSES)}",
            )
        query = query.filter(MedicalAppointment.status == st)

    items = query.order_by(MedicalAppointment.appointment_date.desc(), MedicalAppointment.id.desc()).all()
    return [_appointment_to_response(a) for a in items]


@router.post("/appointments", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    """Registra una cita prenatal calculando automáticamente la semana y día gestacional."""
    st = payload.status.upper()
    if st not in VALID_APPOINTMENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estado inválido. Válidos: {sorted(VALID_APPOINTMENT_STATUSES)}",
        )

    settings_rec = get_or_create_settings(db)
    metrics = ObstetricCalculatorService.calculate_metrics(
        due_date=settings_rec.due_date,
        calibration_offset_days=settings_rec.calibration_offset_days,
        current_date=payload.appointmentDate.date(),
    )

    appt = MedicalAppointment(
        appointment_date=payload.appointmentDate,
        doctor_or_clinic=payload.doctorOrClinic.strip(),
        specialty=(payload.specialty or "Ginecología y Obstetricia").strip(),
        gestational_week=metrics["weeks"],
        gestational_day=metrics["days"],
        mom_weight_kg=payload.momWeightKg,
        blood_pressure=payload.bloodPressure.strip() if payload.bloodPressure else None,
        baby_heart_rate_bpm=payload.babyHeartRateBpm,
        questions_for_doctor=payload.questionsForDoctor.strip() if payload.questionsForDoctor else None,
        doctor_notes_and_diagnosis=payload.doctorNotesAndDiagnosis.strip() if payload.doctorNotesAndDiagnosis else None,
        status=st,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return _appointment_to_response(appt)


@router.put("/appointments/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: int,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
):
    """Actualiza signos vitales, preguntas, diagnóstico o estado de una cita médica."""
    appt = db.query(MedicalAppointment).filter(MedicalAppointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita médica no encontrada")

    if payload.appointmentDate is not None:
        appt.appointment_date = payload.appointmentDate
        settings_rec = get_or_create_settings(db)
        metrics = ObstetricCalculatorService.calculate_metrics(
            due_date=settings_rec.due_date,
            calibration_offset_days=settings_rec.calibration_offset_days,
            current_date=payload.appointmentDate.date(),
        )
        appt.gestational_week = metrics["weeks"]
        appt.gestational_day = metrics["days"]

    if payload.doctorOrClinic is not None:
        appt.doctor_or_clinic = payload.doctorOrClinic.strip()
    if payload.specialty is not None:
        appt.specialty = payload.specialty.strip()
    if payload.momWeightKg is not None:
        appt.mom_weight_kg = payload.momWeightKg
    if payload.bloodPressure is not None:
        appt.blood_pressure = payload.bloodPressure.strip() or None
    if payload.babyHeartRateBpm is not None:
        appt.baby_heart_rate_bpm = payload.babyHeartRateBpm
    if payload.questionsForDoctor is not None:
        appt.questions_for_doctor = payload.questionsForDoctor.strip() or None
    if payload.doctorNotesAndDiagnosis is not None:
        appt.doctor_notes_and_diagnosis = payload.doctorNotesAndDiagnosis.strip() or None
    if payload.status is not None:
        st = payload.status.upper()
        if st not in VALID_APPOINTMENT_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estado inválido. Válidos: {sorted(VALID_APPOINTMENT_STATUSES)}",
            )
        appt.status = st

    db.commit()
    db.refresh(appt)
    return _appointment_to_response(appt)


@router.delete("/appointments/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment(appointment_id: int, db: Session = Depends(get_db)):
    """Elimina una cita médica."""
    appt = db.query(MedicalAppointment).filter(MedicalAppointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita médica no encontrada")
    db.delete(appt)
    db.commit()
    return None


# ==============================================================================
# ESTUDIOS CLÍNICOS HÍBRIDOS (1:N FOTOS + PDFs) Y GALERÍA DE ULTRASONIDOS
# ==============================================================================


@router.get("/studies", response_model=List[MedicalStudyResponse])
def list_studies(
    study_type: Optional[str] = Query(None),
    appointment_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Lista los estudios clínicos y sus múltiples archivos adjuntos (fotos y PDFs)."""
    query = db.query(MedicalStudy).options(joinedload(MedicalStudy.attachments))

    if study_type:
        st = study_type.upper()
        if st not in VALID_STUDY_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"study_type inválido. Válidos: {sorted(VALID_STUDY_TYPES)}",
            )
        query = query.filter(MedicalStudy.study_type == st)

    if appointment_id is not None:
        query = query.filter(MedicalStudy.appointment_id == appointment_id)

    studies = query.order_by(MedicalStudy.study_date.desc(), MedicalStudy.id.desc()).all()
    return [_study_to_response(s) for s in studies]


@router.post("/studies", response_model=MedicalStudyResponse, status_code=status.HTTP_201_CREATED)
async def create_study_with_attachments(
    studyType: str = Form(...),
    title: str = Form(...),
    studyDate: date = Form(...),
    summaryNotes: Optional[str] = Form(None),
    createdBy: str = Form("PAPA"),
    appointmentId: Optional[int] = Form(None),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Crea un estudio médico o ultrasonido adjuntando 1 o múltiples archivos simultáneos
    (soporta mezcla de PDFs de laboratorio e imágenes/fotos de recetas).
    """
    st_upper = studyType.upper()
    if st_upper not in VALID_STUDY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"studyType inválido. Válidos: {sorted(VALID_STUDY_TYPES)}",
        )

    role_upper = createdBy.upper()
    if role_upper not in {"MAMA", "PAPA"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="createdBy debe ser MAMA o PAPA",
        )

    if appointmentId is not None:
        appt = db.query(MedicalAppointment).filter(MedicalAppointment.id == appointmentId).first()
        if not appt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita vinculada no encontrada")

    valid_files = [f for f in files if f and f.filename]
    if not valid_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe adjuntar al menos un archivo (imagen o PDF).",
        )

    settings_rec = get_or_create_settings(db)
    metrics = ObstetricCalculatorService.calculate_metrics(
        due_date=settings_rec.due_date,
        calibration_offset_days=settings_rec.calibration_offset_days,
        current_date=studyDate,
    )

    subfolder = HybridStorageService.resolve_study_subfolder(st_upper)
    saved_paths: List[str] = []
    attachment_rows: List[StudyAttachment] = []

    try:
        for upload_file in valid_files:
            rel_path, mime_type, file_category, size_bytes = await HybridStorageService.save_hybrid_file(
                upload_file, subfolder=subfolder
            )
            saved_paths.append(rel_path)
            attachment_rows.append(
                StudyAttachment(
                    original_filename=upload_file.filename or "archivo",
                    stored_relative_path=rel_path,
                    mime_type=mime_type,
                    file_category=file_category,
                    file_size_bytes=size_bytes,
                )
            )
    except Exception:
        # Limpiar archivos ya guardados si alguno falla en el lote
        for path in saved_paths:
            HybridStorageService.delete_file(path)
        raise

    study = MedicalStudy(
        appointment_id=appointmentId,
        study_type=st_upper,
        title=title.strip(),
        study_date=studyDate,
        gestational_week=metrics["weeks"],
        gestational_day=metrics["days"],
        summary_notes=summaryNotes.strip() if summaryNotes else None,
        created_by=role_upper,
        attachments=attachment_rows,
    )
    db.add(study)
    db.commit()
    db.refresh(study)

    # Recargar con attachments ordenados
    created = (
        db.query(MedicalStudy)
        .options(joinedload(MedicalStudy.attachments))
        .filter(MedicalStudy.id == study.id)
        .first()
    )
    return _study_to_response(created)


@router.post("/studies/{study_id}/attachments", response_model=MedicalStudyResponse, status_code=status.HTTP_201_CREATED)
async def add_attachments_to_study(
    study_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Agrega más archivos (fotos o PDFs) a un estudio existente."""
    study = (
        db.query(MedicalStudy)
        .options(joinedload(MedicalStudy.attachments))
        .filter(MedicalStudy.id == study_id)
        .first()
    )
    if not study:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estudio médico no encontrado")

    valid_files = [f for f in files if f and f.filename]
    if not valid_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe adjuntar al menos un archivo.",
        )

    subfolder = HybridStorageService.resolve_study_subfolder(study.study_type)
    saved_paths: List[str] = []

    try:
        for upload_file in valid_files:
            rel_path, mime_type, file_category, size_bytes = await HybridStorageService.save_hybrid_file(
                upload_file, subfolder=subfolder
            )
            saved_paths.append(rel_path)
            study.attachments.append(
                StudyAttachment(
                    original_filename=upload_file.filename or "archivo",
                    stored_relative_path=rel_path,
                    mime_type=mime_type,
                    file_category=file_category,
                    file_size_bytes=size_bytes,
                )
            )
    except Exception:
        for path in saved_paths:
            HybridStorageService.delete_file(path)
        raise

    db.commit()
    db.refresh(study)
    return _study_to_response(study)


@router.delete("/studies/{study_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_study(study_id: int, db: Session = Depends(get_db)):
    """Elimina un estudio médico y todos sus archivos físicos adjuntos."""
    study = (
        db.query(MedicalStudy)
        .options(joinedload(MedicalStudy.attachments))
        .filter(MedicalStudy.id == study_id)
        .first()
    )
    if not study:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estudio médico no encontrado")

    for att in study.attachments:
        HybridStorageService.delete_file(att.stored_relative_path)

    db.delete(study)
    db.commit()
    return None


@router.get("/ultrasounds", response_model=List[MedicalStudyResponse])
def list_ultrasounds(db: Session = Depends(get_db)):
    """Devuelve la línea de tiempo exclusiva de ultrasonidos (Ecos) con sus fotos y reportes PDF."""
    ultrasounds = (
        db.query(MedicalStudy)
        .options(joinedload(MedicalStudy.attachments))
        .filter(MedicalStudy.study_type == "ULTRASONIDO")
        .order_by(MedicalStudy.study_date.desc(), MedicalStudy.id.desc())
        .all()
    )
    return [_study_to_response(u) for u in ultrasounds]


# ==============================================================================
# MODO CONSULTA MÉDICA (RESUMEN EN UN TOQUE PARA EL GINECÓLOGO)
# ==============================================================================


@router.get("/consultation-mode", response_model=ConsultationModeResponse)
def get_consultation_mode(db: Session = Depends(get_db)):
    """
    Vista consolidada para usar frente al ginecólogo:
    - Edad gestacional actual y perfil clínico de Mamá
    - Últimos signos vitales registrados
    - Lista de preguntas pendientes anotadas en citas
    - Últimos estudios clínicos y ultrasonidos
    """
    settings_rec = get_or_create_settings(db)
    metrics = ObstetricCalculatorService.calculate_metrics(
        due_date=settings_rec.due_date,
        calibration_offset_days=settings_rec.calibration_offset_days,
    )

    # Últimos signos vitales registrados en citas (donde exista peso, presión o FCF)
    appointments = (
        db.query(MedicalAppointment)
        .order_by(MedicalAppointment.appointment_date.desc(), MedicalAppointment.id.desc())
        .all()
    )

    latest_vitals: Optional[LatestVitalsSummary] = None
    for a in appointments:
        if a.mom_weight_kg is not None or a.blood_pressure or a.baby_heart_rate_bpm is not None:
            latest_vitals = LatestVitalsSummary(
                momWeightKg=float(a.mom_weight_kg) if a.mom_weight_kg is not None else None,
                bloodPressure=a.blood_pressure,
                babyHeartRateBpm=a.baby_heart_rate_bpm,
                recordedAt=a.appointment_date,
                doctorOrClinic=a.doctor_or_clinic,
            )
            break

    # Preguntas pendientes (de citas programadas o recientes con preguntas anotadas)
    pending_questions: List[PendingQuestionItem] = []
    for a in appointments:
        if a.status == "SCHEDULED" and a.questions_for_doctor and a.questions_for_doctor.strip():
            pending_questions.append(
                PendingQuestionItem(
                    appointmentId=a.id,
                    appointmentDate=a.appointment_date,
                    doctorOrClinic=a.doctor_or_clinic,
                    questions=a.questions_for_doctor.strip(),
                )
            )

    recent_studies = (
        db.query(MedicalStudy)
        .options(joinedload(MedicalStudy.attachments))
        .filter(MedicalStudy.study_type != "ULTRASONIDO")
        .order_by(MedicalStudy.study_date.desc(), MedicalStudy.id.desc())
        .limit(5)
        .all()
    )

    recent_ultrasounds = (
        db.query(MedicalStudy)
        .options(joinedload(MedicalStudy.attachments))
        .filter(MedicalStudy.study_type == "ULTRASONIDO")
        .order_by(MedicalStudy.study_date.desc(), MedicalStudy.id.desc())
        .limit(5)
        .all()
    )

    return ConsultationModeResponse(
        babyNickname=settings_rec.baby_nickname,
        dueDate=settings_rec.due_date.isoformat(),
        momName=settings_rec.mom_name,
        momBloodType=settings_rec.blood_type_mom,
        allergiesNotes=settings_rec.allergies_notes,
        currentWeeks=metrics["weeks"],
        currentDays=metrics["days"],
        trimesterName=metrics["trimesterName"],
        daysRemaining=metrics["daysRemaining"],
        latestVitals=latest_vitals,
        pendingQuestions=pending_questions,
        recentStudies=[_study_to_response(s) for s in recent_studies],
        recentUltrasounds=[_study_to_response(u) for u in recent_ultrasounds],
    )
