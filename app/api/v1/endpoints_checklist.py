from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.checklist import ChecklistItem
from app.schemas.checklist_schema import (
    VALID_CATEGORIES,
    ChecklistItemCreate,
    ChecklistItemUpdate,
    ChecklistToggleRequest,
    ChecklistItemResponse,
    ChecklistSummaryResponse,
    TrimesterSummary,
    CategorySummary,
)

router = APIRouter()


def _to_response(item: ChecklistItem) -> ChecklistItemResponse:
    return ChecklistItemResponse(
        id=item.id,
        category=item.category,
        itemName=item.item_name,
        description=item.description,
        trimesterPriority=item.trimester_priority,
        quantity=item.quantity,
        estimatedCostMxn=float(item.estimated_cost_mxn or 0),
        actualCostMxn=float(item.actual_cost_mxn or 0),
        referenceUrl=item.reference_url,
        isCompleted=bool(item.is_completed),
        completedBy=item.completed_by,
        completedAt=item.completed_at,
        createdAt=item.created_at,
    )


@router.get("/summary", response_model=ChecklistSummaryResponse)
def get_checklist_summary(db: Session = Depends(get_db)):
    """Devuelve métricas globales, por trimestre y por categoría (avance y presupuesto)."""
    items = db.query(ChecklistItem).all()
    total_items = len(items)
    completed_items = sum(1 for i in items if i.is_completed)
    progress_percent = round((completed_items / total_items) * 100, 1) if total_items else 0.0
    total_est = round(sum(float(i.estimated_cost_mxn or 0) for i in items), 2)
    total_act = round(sum(float(i.actual_cost_mxn or 0) for i in items), 2)

    by_trimester: List[TrimesterSummary] = []
    for t in (1, 2, 3):
        t_items = [i for i in items if i.trimester_priority == t]
        t_total = len(t_items)
        t_comp = sum(1 for i in t_items if i.is_completed)
        by_trimester.append(
            TrimesterSummary(
                trimester=t,
                totalItems=t_total,
                completedItems=t_comp,
                progressPercent=round((t_comp / t_total) * 100, 1) if t_total else 0.0,
                estimatedCostMxn=round(sum(float(i.estimated_cost_mxn or 0) for i in t_items), 2),
                actualCostMxn=round(sum(float(i.actual_cost_mxn or 0) for i in t_items), 2),
            )
        )

    ordered_categories = ["HABITACION", "TRANSPORTE", "ALIMENTACION", "HIGIENE", "ROPA", "HOSPITAL"]
    by_category: List[CategorySummary] = []
    for cat in ordered_categories:
        c_items = [i for i in items if i.category == cat]
        c_total = len(c_items)
        c_comp = sum(1 for i in c_items if i.is_completed)
        by_category.append(
            CategorySummary(
                category=cat,
                totalItems=c_total,
                completedItems=c_comp,
                progressPercent=round((c_comp / c_total) * 100, 1) if c_total else 0.0,
                estimatedCostMxn=round(sum(float(i.estimated_cost_mxn or 0) for i in c_items), 2),
                actualCostMxn=round(sum(float(i.actual_cost_mxn or 0) for i in c_items), 2),
            )
        )

    return ChecklistSummaryResponse(
        totalItems=total_items,
        completedItems=completed_items,
        progressPercent=progress_percent,
        totalEstimatedCostMxn=total_est,
        totalActualCostMxn=total_act,
        byTrimester=by_trimester,
        byCategory=by_category,
    )


@router.get("", response_model=List[ChecklistItemResponse])
def list_checklist_items(
    category: Optional[str] = Query(None),
    trimester: Optional[int] = Query(None, ge=1, le=3),
    completed: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    """Lista los artículos de la checklist con filtros opcionales por categoría, trimestre o estado."""
    query = db.query(ChecklistItem)
    if category:
        cat_upper = category.upper()
        if cat_upper not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Categoría inválida. Válidas: {sorted(VALID_CATEGORIES)}",
            )
        query = query.filter(ChecklistItem.category == cat_upper)
    if trimester is not None:
        query = query.filter(ChecklistItem.trimester_priority == trimester)
    if completed is not None:
        query = query.filter(ChecklistItem.is_completed == completed)

    items = query.order_by(ChecklistItem.trimester_priority.asc(), ChecklistItem.id.asc()).all()
    return [_to_response(item) for item in items]


@router.post("", response_model=ChecklistItemResponse, status_code=status.HTTP_201_CREATED)
def create_checklist_item(payload: ChecklistItemCreate, db: Session = Depends(get_db)):
    """Crea un nuevo artículo en la checklist del bebé."""
    cat_upper = payload.category.upper()
    if cat_upper not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Categoría inválida. Válidas: {sorted(VALID_CATEGORIES)}",
        )

    item = ChecklistItem(
        category=cat_upper,
        item_name=payload.itemName,
        description=payload.description,
        trimester_priority=payload.trimesterPriority,
        quantity=payload.quantity,
        estimated_cost_mxn=payload.estimatedCostMxn,
        actual_cost_mxn=payload.actualCostMxn,
        reference_url=payload.referenceUrl,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_response(item)


@router.patch("/{item_id}/toggle", response_model=ChecklistItemResponse)
def toggle_checklist_item(
    item_id: int,
    payload: Optional[ChecklistToggleRequest] = None,
    db: Session = Depends(get_db),
):
    """Alterna el estado de completado de un artículo y registra quién lo marcó (Mamá/Papá) y su costo real."""
    item = db.query(ChecklistItem).filter(ChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artículo no encontrado")

    new_state = not bool(item.is_completed)
    item.is_completed = new_state

    if new_state:
        who = (payload.completedBy if payload and payload.completedBy else "MAMA").upper()
        if who not in {"MAMA", "PAPA"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="completedBy debe ser MAMA o PAPA")
        item.completed_by = who
        item.completed_at = datetime.utcnow()
        if payload and payload.actualCostMxn is not None:
            item.actual_cost_mxn = payload.actualCostMxn
        elif float(item.actual_cost_mxn or 0) == 0:
            item.actual_cost_mxn = item.estimated_cost_mxn
    else:
        item.completed_by = None
        item.completed_at = None

    db.commit()
    db.refresh(item)
    return _to_response(item)


@router.put("/{item_id}", response_model=ChecklistItemResponse)
def update_checklist_item(item_id: int, payload: ChecklistItemUpdate, db: Session = Depends(get_db)):
    """Actualiza los datos o costos de un artículo de la checklist."""
    item = db.query(ChecklistItem).filter(ChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artículo no encontrado")

    if payload.category is not None:
        cat_upper = payload.category.upper()
        if cat_upper not in VALID_CATEGORIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Categoría inválida")
        item.category = cat_upper
    if payload.itemName is not None:
        item.item_name = payload.itemName
    if payload.description is not None:
        item.description = payload.description
    if payload.trimesterPriority is not None:
        item.trimester_priority = payload.trimesterPriority
    if payload.quantity is not None:
        item.quantity = payload.quantity
    if payload.estimatedCostMxn is not None:
        item.estimated_cost_mxn = payload.estimatedCostMxn
    if payload.actualCostMxn is not None:
        item.actual_cost_mxn = payload.actualCostMxn
    if payload.referenceUrl is not None:
        item.reference_url = payload.referenceUrl
    if payload.isCompleted is not None:
        item.is_completed = payload.isCompleted
        item.completed_at = datetime.utcnow() if payload.isCompleted else None
        if not payload.isCompleted:
            item.completed_by = None
    if payload.completedBy is not None:
        item.completed_by = payload.completedBy.upper()

    db.commit()
    db.refresh(item)
    return _to_response(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_checklist_item(item_id: int, db: Session = Depends(get_db)):
    """Elimina un artículo de la checklist."""
    item = db.query(ChecklistItem).filter(ChecklistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artículo no encontrado")
    db.delete(item)
    db.commit()
    return None
