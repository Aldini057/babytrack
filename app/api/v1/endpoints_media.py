from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.media import MediaMoment, DocumentVaultItem
from app.schemas.media_schema import (
    VALID_VAULT_CATEGORIES,
    MediaMomentResponse,
    DocumentVaultItemResponse,
)
from app.api.v1.endpoints_settings import get_or_create_settings
from app.services.obstetric_calculator import ObstetricCalculatorService
from app.services.storage_service import HybridStorageService

moments_router = APIRouter()
vault_router = APIRouter()


def _moment_to_response(m: MediaMoment) -> MediaMomentResponse:
    return MediaMomentResponse(
        id=m.id,
        title=m.title,
        caption=m.caption,
        momentDate=m.moment_date,
        gestationalWeek=m.gestational_week,
        gestationalDay=m.gestational_day,
        imageRelativePath=m.image_relative_path,
        imageUrl=f"/{m.image_relative_path}",
        uploadedBy=m.uploaded_by,
        createdAt=m.created_at,
    )


def _vault_to_response(v: DocumentVaultItem) -> DocumentVaultItemResponse:
    return DocumentVaultItemResponse(
        id=v.id,
        category=v.category,
        title=v.title,
        notes=v.notes,
        originalFilename=v.original_filename,
        storedRelativePath=v.stored_relative_path,
        url=f"/{v.stored_relative_path}",
        mimeType=v.mime_type,
        fileCategory=v.file_category,
        fileSizeBytes=v.file_size_bytes,
        uploadedBy=v.uploaded_by,
        createdAt=v.created_at,
    )


# ==============================================================================
# ÁLBUM FOTOGRÁFICO DE MOMENTOS (/api/v1/moments)
# ==============================================================================


@moments_router.get("", response_model=List[MediaMomentResponse])
def list_moments(
    uploaded_by: Optional[str] = Query(None, alias="uploadedBy"),
    db: Session = Depends(get_db),
):
    """Lista las fotografías del álbum de momentos ordenadas cronológicamente."""
    query = db.query(MediaMoment)
    if uploaded_by:
        role = uploaded_by.upper()
        if role not in {"MAMA", "PAPA"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="uploadedBy debe ser MAMA o PAPA",
            )
        query = query.filter(MediaMoment.uploaded_by == role)

    items = query.order_by(MediaMoment.moment_date.desc(), MediaMoment.id.desc()).all()
    return [_moment_to_response(m) for m in items]


@moments_router.post("", response_model=MediaMomentResponse, status_code=status.HTTP_201_CREATED)
async def create_moment(
    title: str = Form(...),
    momentDate: Optional[date] = Form(None),
    caption: Optional[str] = Form(None),
    uploadedBy: str = Form("MAMA"),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Sube una fotografía al álbum de momentos con cálculo automático de semana y día gestacional."""
    role = uploadedBy.upper()
    if role not in {"MAMA", "PAPA"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="uploadedBy debe ser MAMA o PAPA",
        )

    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El título del momento no puede estar vacío.",
        )

    effective_date = momentDate or ObstetricCalculatorService.get_local_date()
    settings_rec = get_or_create_settings(db)
    metrics = ObstetricCalculatorService.calculate_metrics(
        due_date=settings_rec.due_date,
        calibration_offset_days=settings_rec.calibration_offset_days,
        current_date=effective_date,
    )

    rel_path, _, _ = await HybridStorageService.save_image(photo, subfolder="momentos")

    moment = MediaMoment(
        title=clean_title,
        caption=caption.strip() if caption else None,
        moment_date=effective_date,
        gestational_week=metrics["weeks"],
        gestational_day=metrics["days"],
        image_relative_path=rel_path,
        uploaded_by=role,
    )
    db.add(moment)
    db.commit()
    db.refresh(moment)
    return _moment_to_response(moment)


@moments_router.delete("/{moment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_moment(moment_id: int, db: Session = Depends(get_db)):
    """Elimina un momento fotográfico y su imagen del disco."""
    moment = db.query(MediaMoment).filter(MediaMoment.id == moment_id).first()
    if not moment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Momento no encontrado")

    HybridStorageService.delete_file(moment.image_relative_path)
    db.delete(moment)
    db.commit()
    return None


# ==============================================================================
# BÓVEDA DE DOCUMENTOS ADMINISTRATIVOS Y CLÍNICOS (/api/v1/vault)
# ==============================================================================


@vault_router.get("", response_model=List[DocumentVaultItemResponse])
def list_vault_documents(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Lista los documentos de la bóveda (pólizas, carnets, identificaciones, ingreso)."""
    query = db.query(DocumentVaultItem)
    if category:
        cat = category.upper()
        if cat not in VALID_VAULT_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Categoría inválida. Válidas: {sorted(VALID_VAULT_CATEGORIES)}",
            )
        query = query.filter(DocumentVaultItem.category == cat)

    items = query.order_by(DocumentVaultItem.created_at.desc(), DocumentVaultItem.id.desc()).all()
    return [_vault_to_response(v) for v in items]


@vault_router.post("", response_model=DocumentVaultItemResponse, status_code=status.HTTP_201_CREATED)
async def create_vault_document(
    category: str = Form("POLIZA"),
    title: str = Form(...),
    notes: Optional[str] = Form(None),
    uploadedBy: str = Form("PAPA"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Guarda un documento administrativo/clínico (PDF o Imagen) en /uploads/documentos."""
    cat = category.upper()
    if cat not in VALID_VAULT_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Categoría inválida. Válidas: {sorted(VALID_VAULT_CATEGORIES)}",
        )

    role = uploadedBy.upper()
    if role not in {"MAMA", "PAPA"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="uploadedBy debe ser MAMA o PAPA",
        )

    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El título del documento es obligatorio.",
        )

    rel_path, mime_type, file_category, size_bytes = await HybridStorageService.save_hybrid_file(
        file, subfolder="documentos"
    )

    doc = DocumentVaultItem(
        category=cat,
        title=clean_title,
        notes=notes.strip() if notes else None,
        original_filename=file.filename or "documento",
        stored_relative_path=rel_path,
        mime_type=mime_type,
        file_category=file_category,
        file_size_bytes=size_bytes,
        uploaded_by=role,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _vault_to_response(doc)


@vault_router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vault_document(doc_id: int, db: Session = Depends(get_db)):
    """Elimina un documento de la bóveda y su archivo físico."""
    doc = db.query(DocumentVaultItem).filter(DocumentVaultItem.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")

    HybridStorageService.delete_file(doc.stored_relative_path)
    db.delete(doc)
    db.commit()
    return None
