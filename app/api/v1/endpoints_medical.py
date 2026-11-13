from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.medical import MedicalAppointment, MedicalStudy, StudyAttachment
from app.schemas.medical_schema import (
    VALID_APPOINTMENT_STATUSES,
    VALID_APPOINTMENT_TYPES,
    VALID_STUDY_TYPES,
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
    CalendarConfigPayload,
    ConsultationModeResponse,
    LatestVitalsSummary,
    MedicalStudyResponse,
    PendingQuestionItem,
    StudyAttachmentResponse,
)
from app.api.v1.endpoints_settings import get_or_create_settings
from app.services.calendar_service import GoogleCalendarService
from app.services.obstetric_calculator import ObstetricCalculatorService
from app.services.storage_service import HybridStorageService

router = APIRouter()

DEFAULT_SPECIALTY_BY_TYPE = {
    "MEDICO": "Ginecología y Obstetricia",
    "LABORATORIO": "Análisis Clínicos / Laboratorio",
    "ECO": "Ultrasonido Obstétrico",
}


def _appointment_to_response(item: MedicalAppointment, baby_nickname: str = "Nuestro Bebé") -> AppointmentResponse:
    appt_type = getattr(item, "appointment_type", None) or "MEDICO"
    reminder_mins = getattr(item, "reminder_minutes_before", None) or 1440
    return AppointmentResponse(
        id=item.id,
        appointmentType=appt_type,
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
        reminderMinutesBefore=reminder_mins,
        googleEventId=getattr(item, "google_event_id", None),
        googleEventLink=getattr(item, "google_event_link", None),
        googleCalendarTemplateUrl=GoogleCalendarService.build_google_calendar_template_url(item, baby_nickname),
        icsDownloadUrl=f"/api/v1/medical/appointments/{item.id}/calendar.ics",
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
# CITAS MÉDICAS, DE LABORATORIO Y DE ECO (AGENDA PRENATAL + GOOGLE CALENDAR)
# ==============================================================================


@router.get("/appointments", response_model=List[AppointmentResponse])
def list_appointments(
    status_filter: Optional[str] = Query(None, alias="status"),
    type_filter: Optional[str] = Query(None, alias="type"),
    db: Session = Depends(get_db),
):
    """Lista las citas prenatales (Médico, Laboratorio o Eco) ordenadas por fecha descendente."""
    settings_rec = get_or_create_settings(db)
    baby_nickname = settings_rec.baby_nickname or "Nuestro Bebé"

    query = db.query(MedicalAppointment)
    if isinstance(status_filter, str) and status_filter:
        st = status_filter.upper()
        if st not in VALID_APPOINTMENT_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Estado inválido. Válidos: {sorted(VALID_APPOINTMENT_STATUSES)}",
            )
        query = query.filter(MedicalAppointment.status == st)

    if isinstance(type_filter, str) and type_filter:
        tp = type_filter.upper()
        if tp not in VALID_APPOINTMENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de cita inválido. Válidos: {sorted(VALID_APPOINTMENT_TYPES)}",
            )
        query = query.filter(MedicalAppointment.appointment_type == tp)

    items = query.order_by(MedicalAppointment.appointment_date.desc(), MedicalAppointment.id.desc()).all()
    return [_appointment_to_response(a, baby_nickname) for a in items]


@router.post("/appointments", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    """Registra una cita prenatal (MEDICO, LABORATORIO o ECO) y la sincroniza con Google Calendar si está activo."""
    st = payload.status.upper()
    if st not in VALID_APPOINTMENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estado inválido. Válidos: {sorted(VALID_APPOINTMENT_STATUSES)}",
        )

    appt_type = (payload.appointmentType or "MEDICO").upper()
    if appt_type not in VALID_APPOINTMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de cita inválido. Válidos: {sorted(VALID_APPOINTMENT_TYPES)}",
        )

    settings_rec = get_or_create_settings(db)
    metrics = ObstetricCalculatorService.calculate_metrics(
        due_date=settings_rec.due_date,
        calibration_offset_days=settings_rec.calibration_offset_days,
        current_date=payload.appointmentDate.date(),
    )

    specialty_val = (payload.specialty or "").strip() or DEFAULT_SPECIALTY_BY_TYPE.get(appt_type, "Ginecología y Obstetricia")
    reminder_mins = payload.reminderMinutesBefore if payload.reminderMinutesBefore is not None else 1440

    appt = MedicalAppointment(
        appointment_type=appt_type,
        appointment_date=payload.appointmentDate,
        doctor_or_clinic=payload.doctorOrClinic.strip(),
        specialty=specialty_val,
        gestational_week=metrics["weeks"],
        gestational_day=metrics["days"],
        mom_weight_kg=payload.momWeightKg,
        blood_pressure=payload.bloodPressure.strip() if payload.bloodPressure else None,
        baby_heart_rate_bpm=payload.babyHeartRateBpm,
        questions_for_doctor=payload.questionsForDoctor.strip() if payload.questionsForDoctor else None,
        doctor_notes_and_diagnosis=payload.doctorNotesAndDiagnosis.strip() if payload.doctorNotesAndDiagnosis else None,
        status=st,
        reminder_minutes_before=reminder_mins,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    # Opción 2: Sincronización automática en segundo plano con Google Calendar API (si hay calendario vinculado)
    cal_id = GoogleCalendarService.get_effective_calendar_id(settings_rec)
    if cal_id and st != "CANCELLED":
        sync_res = GoogleCalendarService.sync_appointment_to_google_calendar(
            appt, cal_id, baby_nickname=settings_rec.baby_nickname
        )
        if sync_res.get("synced"):
            appt.google_event_id = sync_res.get("eventId")
            appt.google_event_link = sync_res.get("htmlLink")
            db.commit()
            db.refresh(appt)

    return _appointment_to_response(appt, settings_rec.baby_nickname)


@router.put("/appointments/{appointment_id}", response_model=AppointmentResponse)
def update_appointment(
    appointment_id: int,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
):
    """Actualiza una cita y sincroniza los cambios automáticamente con Google Calendar."""
    appt = db.query(MedicalAppointment).filter(MedicalAppointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita médica no encontrada")

    settings_rec = get_or_create_settings(db)

    if payload.appointmentType is not None:
        tp = payload.appointmentType.upper()
        if tp not in VALID_APPOINTMENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de cita inválido. Válidos: {sorted(VALID_APPOINTMENT_TYPES)}",
            )
        appt.appointment_type = tp

    if payload.appointmentDate is not None:
        appt.appointment_date = payload.appointmentDate
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
    if payload.reminderMinutesBefore is not None:
        appt.reminder_minutes_before = payload.reminderMinutesBefore
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

    # Sincronizar actualización con Google Calendar API
    cal_id = GoogleCalendarService.get_effective_calendar_id(settings_rec)
    if cal_id:
        sync_res = GoogleCalendarService.sync_appointment_to_google_calendar(
            appt, cal_id, baby_nickname=settings_rec.baby_nickname
        )
        if sync_res.get("synced"):
            appt.google_event_id = sync_res.get("eventId")
            appt.google_event_link = sync_res.get("htmlLink")
            db.commit()
            db.refresh(appt)
        elif appt.status == "CANCELLED" and sync_res.get("deleted"):
            appt.google_event_id = None
            appt.google_event_link = None
            db.commit()
            db.refresh(appt)

    return _appointment_to_response(appt, settings_rec.baby_nickname)


@router.delete("/appointments/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment(appointment_id: int, db: Session = Depends(get_db)):
    """Elimina una cita prenatal y la borra de Google Calendar si estaba sincronizada."""
    appt = db.query(MedicalAppointment).filter(MedicalAppointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita médica no encontrada")

    settings_rec = get_or_create_settings(db)
    cal_id = GoogleCalendarService.get_effective_calendar_id(settings_rec)
    if cal_id and getattr(appt, "google_event_id", None):
        GoogleCalendarService.delete_appointment_from_google_calendar(appt.google_event_id, cal_id)

    db.delete(appt)
    db.commit()
    return None


# ==============================================================================
# GOOGLE CALENDAR (.ICS FEED, ARCHIVO INDIVIDUAL Y SINCRONIZACIÓN API)
# ==============================================================================


@router.get("/calendar.ics")
def get_full_calendar_ics(db: Session = Depends(get_db)):
    """
    Devuelve el calendario completo suscribible (.ics) con todas las citas y la FPP,
    incluyendo alarmas automáticas de 1 día antes (24 horas) y 2 horas antes.
    """
    settings_rec = get_or_create_settings(db)
    appointments = (
        db.query(MedicalAppointment)
        .filter(MedicalAppointment.status != "CANCELLED")
        .order_by(MedicalAppointment.appointment_date.asc())
        .all()
    )
    ics_content = GoogleCalendarService.generate_ics_feed(appointments, settings_rec)
    return Response(
        content=ics_content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="babytrack-calendario.ics"'},
    )


@router.get("/appointments/{appointment_id}/calendar.ics")
def get_single_appointment_ics(appointment_id: int, db: Session = Depends(get_db)):
    """
    Descarga el archivo .ics de una cita individual con alerta automática de 1 día antes.
    Ideal para abrir directamente en el calendario nativo del celular.
    """
    appt = db.query(MedicalAppointment).filter(MedicalAppointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita médica no encontrada")
    settings_rec = get_or_create_settings(db)
    ics_content = GoogleCalendarService.generate_single_appointment_ics(appt, settings_rec.baby_nickname)
    return Response(
        content=ics_content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="cita-babytrack-{appt.id}.ics"'},
    )


@router.get("/calendar/config")
def get_calendar_config(db: Session = Depends(get_db)):
    """Devuelve la configuración actual de vinculación con Google Calendar."""
    settings_rec = get_or_create_settings(db)
    cal_id = GoogleCalendarService.get_effective_calendar_id(settings_rec)
    return {
        "googleCalendarId": cal_id,
        "isConfigured": bool(cal_id),
        "defaultReminderMinutes": 1440,
        "icsFeedPath": "/api/v1/medical/calendar.ics",
    }


@router.put("/calendar/config")
def update_calendar_config(payload: CalendarConfigPayload, db: Session = Depends(get_db)):
    """Guarda el correo o ID del Google Calendar para sincronización automática en segundo plano."""
    settings_rec = get_or_create_settings(db)
    clean_id = (payload.googleCalendarId or "").strip() or None
    settings_rec.google_calendar_id = clean_id
    db.commit()
    db.refresh(settings_rec)
    cal_id = GoogleCalendarService.get_effective_calendar_id(settings_rec)
    return {
        "googleCalendarId": cal_id,
        "isConfigured": bool(cal_id),
        "message": "Configuración de Google Calendar guardada correctamente.",
    }


@router.post("/calendar/sync")
def sync_all_appointments_to_google_calendar(db: Session = Depends(get_db)):
    """
    Sincroniza todas las citas activas con Google Calendar API (Opción 2),
    creando o actualizando cada evento con alerta de 1 día antes (1440 min).
    Si el correo ingresado daba HTTP 404 (no compartido manualmente), crea automáticamente
    el calendario compartido "🍼 BabyTrack" y le da permisos al correo del usuario.
    """
    settings_rec = get_or_create_settings(db)
    cal_id = GoogleCalendarService.get_effective_calendar_id(settings_rec)
    if not cal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Primero ingresa tu correo o ID de Google Calendar en la configuración.",
        )

    # Verificar acceso o auto-crear calendario compartido "🍼 BabyTrack" con permisos para el usuario
    ensured = GoogleCalendarService.ensure_accessible_calendar(
        cal_id, baby_nickname=settings_rec.baby_nickname
    )
    auto_created = False
    add_calendar_url = None
    if ensured.get("ok") and ensured.get("calendarId"):
        cal_id = ensured["calendarId"]
        settings_rec.google_calendar_id = cal_id
        auto_created = bool(ensured.get("autoCreated"))
        add_calendar_url = ensured.get("addCalendarUrl")

    appointments = (
        db.query(MedicalAppointment)
        .filter(MedicalAppointment.status != "CANCELLED")
        .order_by(MedicalAppointment.appointment_date.asc())
        .all()
    )

    synced_count = 0
    errors = []
    for appt in appointments:
        res = GoogleCalendarService.sync_appointment_to_google_calendar(
            appt, cal_id, baby_nickname=settings_rec.baby_nickname
        )
        if res.get("synced"):
            appt.google_event_id = res.get("eventId")
            appt.google_event_link = res.get("htmlLink")
            if res.get("calendarId") and res.get("calendarId") != cal_id:
                cal_id = res["calendarId"]
                settings_rec.google_calendar_id = cal_id
            synced_count += 1
        else:
            errors.append(res.get("reason", "Error desconocido"))

    db.commit()
    return {
        "totalAppointments": len(appointments),
        "syncedCount": synced_count,
        "calendarId": cal_id,
        "autoCreatedCalendar": auto_created,
        "addCalendarUrl": add_calendar_url,
        "errors": errors[:3],
    }


# ==============================================================================
# ESTUDIOS DE LABORATORIO, DIAGNÓSTICOS/RECETAS Y ULTRASONIDOS (0:N ADJUNTOS)
# ==============================================================================


@router.get("/studies", response_model=List[MedicalStudyResponse])
def list_studies(
    study_type: Optional[str] = Query(None),
    appointment_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Lista los estudios clínicos, diagnósticos/recetas y ultrasonidos con sus adjuntos."""
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
    files: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
):
    """
    Crea un resultado de laboratorio, diagnóstico/receta médica o ultrasonido.
    Permite guardarse CON o SIN documentos adjuntos (0:N archivos PDF o Imagen).
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

    valid_files = [f for f in (files or []) if f and getattr(f, "filename", "")]

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
    """Agrega más archivos (fotos o PDFs) a un estudio, diagnóstico, receta o eco existente."""
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
    - Últimos estudios clínicos, diagnósticos/recetas y ultrasonidos
    """
    settings_rec = get_or_create_settings(db)
    metrics = ObstetricCalculatorService.calculate_metrics(
        due_date=settings_rec.due_date,
        calibration_offset_days=settings_rec.calibration_offset_days,
    )

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

    pending_questions: List[PendingQuestionItem] = []
    for a in appointments:
        if a.status == "SCHEDULED" and a.questions_for_doctor and a.questions_for_doctor.strip():
            pending_questions.append(
                PendingQuestionItem(
                    appointmentId=a.id,
                    appointmentType=getattr(a, "appointment_type", None) or "MEDICO",
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
