from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.settings import PregnancySettings
from app.schemas.settings_schema import (
    PregnancySettingsResponse,
    GestationalAgeResponse,
    ObstetricCalibrationRequest,
    GenderThemeUpdateRequest
)
from app.services.obstetric_calculator import ObstetricCalculatorService

router = APIRouter()

def get_or_create_settings(db: Session) -> PregnancySettings:
    record = db.query(PregnancySettings).first()
    if not record:
        from app.seed import seed_database
        record = seed_database(db)
    return record

@router.get("", response_model=PregnancySettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    """Obtiene los ajustes actuales del embarazo y el cálculo gestacional en tiempo real."""
    record = get_or_create_settings(db)
    metrics = ObstetricCalculatorService.calculate_metrics(
        due_date=record.due_date,
        calibration_offset_days=record.calibration_offset_days
    )

    gestational_age = GestationalAgeResponse(
        weeks=metrics["weeks"],
        days=metrics["days"],
        elapsedDays=metrics["elapsedDays"],
        daysRemaining=metrics["daysRemaining"],
        trimester=metrics["trimester"],
        trimesterName=metrics["trimesterName"],
        progressPercent=metrics["progressPercent"],
        sizeComparison=metrics["sizeComparison"],
        sizeWeight=metrics["sizeWeight"],
        currentDate=metrics["currentDate"]
    )

    return PregnancySettingsResponse(
        id=record.id,
        babyNickname=record.baby_nickname,
        dueDate=record.due_date.isoformat(),
        genderMode=record.gender_mode,
        momName=record.mom_name,
        dadName=record.dad_name,
        bloodTypeMom=record.blood_type_mom,
        allergiesNotes=record.allergies_notes,
        calibrationOffsetDays=record.calibration_offset_days,
        gestationalAge=gestational_age
    )

@router.put("/obstetric", response_model=PregnancySettingsResponse)
def update_obstetric_settings(payload: ObstetricCalibrationRequest, db: Session = Depends(get_db)):
    """Actualiza la FPP, calibra las semanas y opcionalmente guarda datos clínicos de Mamá."""
    record = get_or_create_settings(db)

    if payload.dueDate is not None:
        record.due_date = payload.dueDate

    # Si se especificaron semanas y días específicos, calcular el offset exacto
    if payload.currentWeeks is not None and payload.currentDays is not None:
        new_offset = ObstetricCalculatorService.calculate_offset_from_weeks_days(
            due_date=record.due_date,
            target_weeks=payload.currentWeeks,
            target_days=payload.currentDays
        )
        record.calibration_offset_days = new_offset
    elif payload.calibrationOffsetDays is not None:
        record.calibration_offset_days = payload.calibrationOffsetDays

    if payload.bloodTypeMom is not None:
        record.blood_type_mom = payload.bloodTypeMom.strip() or None
    if payload.allergiesNotes is not None:
        record.allergies_notes = payload.allergiesNotes.strip() or None

    db.commit()
    db.refresh(record)

    return get_settings(db)

@router.put("/gender-theme", response_model=PregnancySettingsResponse)
def update_gender_theme(payload: GenderThemeUpdateRequest, db: Session = Depends(get_db)):
    """Actualiza el modo de género (SURPRISE, BOY, GIRL) y opcionalmente el apodo."""
    valid_modes = {"SURPRISE", "BOY", "GIRL"}
    mode = payload.genderMode.upper()
    if mode not in valid_modes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Modo de género inválido. Debe ser uno de: {valid_modes}"
        )

    record = get_or_create_settings(db)
    record.gender_mode = mode

    if payload.babyNickname:
        record.baby_nickname = payload.babyNickname
    elif mode == "BOY" and record.baby_nickname == "Nuestro Bebé":
        record.baby_nickname = "Nuestro Niño"
    elif mode == "GIRL" and record.baby_nickname == "Nuestro Bebé":
        record.baby_nickname = "Nuestra Niña"

    db.commit()
    db.refresh(record)

    return get_settings(db)


@router.get("/backup.zip")
def download_full_backup_zip(db: Session = Depends(get_db)):
    """
    Genera y descarga un archivo .zip con respaldo completo de BabyTrack:
    - Copia íntegra de babytrack.db (SQLite)
    - Archivo resumen_babytrack.json legible con todos los registros (citas, estudios, notas, checklist, momentos, bóveda)
    - Todos los archivos físicos (ecos, PDFs, fotos) en la carpeta uploads/
    """
    import io
    import json
    import zipfile
    from datetime import datetime
    from pathlib import Path
    from fastapi.responses import Response
    from app.config import settings as app_settings
    from app.models.checklist import ChecklistItem
    from app.models.journal import BabyJournalNote
    from app.models.medical import MedicalAppointment, MedicalStudy, FetalMonitorLog
    from app.models.media import MediaMoment, DocumentVaultItem

    record = get_or_create_settings(db)
    data_dir = Path(app_settings.DATA_DIR)

    # Construir exportación JSON legible
    export_payload = {
        "exportedAt": datetime.utcnow().isoformat() + "Z",
        "settings": {
            "babyNickname": record.baby_nickname,
            "dueDate": record.due_date.isoformat(),
            "genderMode": record.gender_mode,
            "momName": record.mom_name,
            "dadName": record.dad_name,
            "bloodTypeMom": record.blood_type_mom,
            "allergiesNotes": record.allergies_notes,
            "googleCalendarId": record.google_calendar_id,
        },
        "appointments": [
            {
                "id": a.id,
                "appointmentType": getattr(a, "appointment_type", "MEDICO"),
                "appointmentDate": a.appointment_date.isoformat() if a.appointment_date else None,
                "doctorOrClinic": a.doctor_or_clinic,
                "specialty": a.specialty,
                "gestationalWeek": a.gestational_week,
                "gestationalDay": a.gestational_day,
                "momWeightKg": float(a.mom_weight_kg) if a.mom_weight_kg is not None else None,
                "bloodPressure": a.blood_pressure,
                "babyHeartRateBpm": a.baby_heart_rate_bpm,
                "questionsForDoctor": a.questions_for_doctor,
                "doctorNotesAndDiagnosis": a.doctor_notes_and_diagnosis,
                "status": a.status,
            }
            for a in db.query(MedicalAppointment).order_by(MedicalAppointment.appointment_date.asc()).all()
        ],
        "studies": [
            {
                "id": s.id,
                "studyType": s.study_type,
                "title": s.title,
                "studyDate": s.study_date.isoformat() if s.study_date else None,
                "gestationalWeek": s.gestational_week,
                "gestationalDay": s.gestational_day,
                "summaryNotes": s.summary_notes,
                "createdBy": s.created_by,
                "attachments": [att.stored_relative_path for att in s.attachments],
            }
            for s in db.query(MedicalStudy).order_by(MedicalStudy.study_date.asc()).all()
        ],
        "fetalMonitorLogs": [
            {
                "id": fl.id,
                "logType": fl.log_type,
                "recordedAt": fl.recorded_at.isoformat() if fl.recorded_at else None,
                "gestationalWeek": fl.gestational_week,
                "gestationalDay": fl.gestational_day,
                "kickCount": fl.kick_count,
                "durationSeconds": fl.duration_seconds,
                "intervalMinutes": float(fl.interval_minutes) if fl.interval_minutes is not None else None,
                "notes": fl.notes,
            }
            for fl in db.query(FetalMonitorLog).order_by(FetalMonitorLog.recorded_at.desc()).all()
        ],
        "journalNotes": [
            {
                "id": n.id,
                "authorRole": n.author_role,
                "authorDisplayName": n.author_display_name,
                "title": n.title,
                "content": n.content,
                "gestationalWeek": n.gestational_week,
                "gestationalDay": n.gestational_day,
                "createdAt": n.created_at.isoformat() if n.created_at else None,
            }
            for n in db.query(BabyJournalNote).order_by(BabyJournalNote.created_at.asc()).all()
        ],
        "checklistItems": [
            {
                "id": c.id,
                "itemName": c.item_name,
                "category": c.category,
                "trimesterPriority": c.trimester_priority,
                "isCompleted": c.is_completed,
                "estimatedCostMxn": float(c.estimated_cost_mxn or 0),
                "actualCostMxn": float(c.actual_cost_mxn or 0),
            }
            for c in db.query(ChecklistItem).order_by(ChecklistItem.id.asc()).all()
        ],
        "moments": [
            {
                "id": m.id,
                "title": m.title,
                "momentDate": m.moment_date.isoformat() if m.moment_date else None,
                "gestationalWeek": m.gestational_week,
                "gestationalDay": m.gestational_day,
                "photoPath": m.image_relative_path,
            }
            for m in db.query(MediaMoment).order_by(MediaMoment.moment_date.asc()).all()
        ],
        "vaultDocuments": [
            {
                "id": v.id,
                "title": v.title,
                "category": v.category,
                "filePath": v.stored_relative_path,
            }
            for v in db.query(DocumentVaultItem).order_by(DocumentVaultItem.id.asc()).all()
        ],
    }

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Resumen JSON legible
        zf.writestr(
            "resumen_babytrack.json",
            json.dumps(export_payload, ensure_ascii=False, indent=2),
        )

        # 2. Base de datos SQLite si existe en DATA_DIR
        db_file = data_dir / "babytrack.db"
        if db_file.exists() and db_file.is_file():
            zf.write(db_file, arcname="babytrack.db")

        # 3. Todos los archivos subidos en uploads/
        uploads_dir = data_dir / "uploads"
        if uploads_dir.exists() and uploads_dir.is_dir():
            for file_path in uploads_dir.rglob("*"):
                if file_path.is_file():
                    rel_arc = file_path.relative_to(data_dir)
                    zf.write(file_path, arcname=str(rel_arc))

    zip_buffer.seek(0)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"respaldo-babytrack-{today_str}.zip"
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

