from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.journal import BabyJournalNote
from app.schemas.journal_schema import JournalNoteCreate, JournalNoteResponse
from app.api.v1.endpoints_settings import get_or_create_settings
from app.services.obstetric_calculator import ObstetricCalculatorService
from app.services.storage_service import HybridStorageService

router = APIRouter()


def _to_response(note: BabyJournalNote) -> JournalNoteResponse:
    return JournalNoteResponse(
        id=note.id,
        authorRole=note.author_role,
        authorDisplayName=note.author_display_name,
        title=note.title,
        content=note.content,
        gestationalWeek=note.gestational_week,
        gestationalDay=note.gestational_day,
        attachedImagePath=note.attached_image_path,
        createdAt=note.created_at,
    )


@router.get("", response_model=List[JournalNoteResponse])
def list_journal_notes(
    author: Optional[str] = Query(None, description="Filtrar por MAMA, PAPA o FAMILIA"),
    db: Session = Depends(get_db),
):
    """Lista las cartas y pensamientos del diario ordenados del más reciente al más antiguo."""
    query = db.query(BabyJournalNote)
    if isinstance(author, str) and author:
        role_upper = author.upper()
        if role_upper not in {"MAMA", "PAPA", "FAMILIA"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El filtro author debe ser MAMA, PAPA o FAMILIA",
            )
        query = query.filter(BabyJournalNote.author_role == role_upper)

    notes = query.order_by(BabyJournalNote.created_at.desc(), BabyJournalNote.id.desc()).all()
    return [_to_response(n) for n in notes]


@router.post("", response_model=JournalNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_journal_note(request: Request, db: Session = Depends(get_db)):
    """
    Crea una nueva carta/pensamiento en el diario del bebé (Mamá, Papá o Familia/Amigos).
    Soporta tanto JSON (application/json) como FormData con foto opcional (multipart/form-data).
    Asigna automáticamente la semana y día gestacional actuales.
    """
    content_type = request.headers.get("content-type", "").lower()
    attached_path: Optional[str] = None

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        author_role_raw = str(form.get("authorRole") or "")
        author_display_raw = form.get("authorDisplayName")
        title_raw = str(form.get("title") or "")
        content_raw = str(form.get("content") or "")
        photo = form.get("photo")

        payload = JournalNoteCreate(
            authorRole=author_role_raw,
            authorDisplayName=str(author_display_raw).strip() if author_display_raw else None,
            title=title_raw,
            content=content_raw,
        )

        if photo is not None and hasattr(photo, "read") and getattr(photo, "filename", ""):
            attached_path, _, _ = await HybridStorageService.save_image(
                photo, subfolder="momentos"
            )
    else:
        try:
            body = await request.json()
            payload = JournalNoteCreate.model_validate(body)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Datos inválidos: {str(exc)}",
            )

    role_upper = payload.authorRole.upper()
    if role_upper not in {"MAMA", "PAPA", "FAMILIA"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="authorRole debe ser MAMA, PAPA o FAMILIA",
        )

    settings_rec = get_or_create_settings(db)
    metrics = ObstetricCalculatorService.calculate_metrics(
        due_date=settings_rec.due_date,
        calibration_offset_days=settings_rec.calibration_offset_days,
    )

    display_name = (payload.authorDisplayName or "").strip()
    if not display_name:
        if role_upper == "MAMA":
            display_name = settings_rec.mom_name
        elif role_upper == "PAPA":
            display_name = settings_rec.dad_name
        else:
            display_name = "Familia"

    note = BabyJournalNote(
        author_role=role_upper,
        author_display_name=display_name[:80],
        title=payload.title.strip(),
        content=payload.content.strip(),
        gestational_week=metrics["weeks"],
        gestational_day=metrics["days"],
        attached_image_path=attached_path,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _to_response(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journal_note(note_id: int, db: Session = Depends(get_db)):
    """Elimina una carta o pensamiento del diario (y su imagen adjunta si existe)."""
    note = db.query(BabyJournalNote).filter(BabyJournalNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota no encontrada")

    if note.attached_image_path:
        HybridStorageService.delete_file(note.attached_image_path)

    db.delete(note)
    db.commit()
    return None
