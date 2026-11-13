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
