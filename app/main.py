from contextlib import asynccontextmanager
import json
from pathlib import Path
from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, Base, get_db, SessionLocal, ensure_schema_migrations
from app.seed import seed_database
from app.models.journal import BabyJournalNote
from app.models.medical import MedicalAppointment, MedicalStudy
from app.models.media import MediaMoment, DocumentVaultItem
from app.api.v1.router import api_router
from app.api.v1.endpoints_settings import get_or_create_settings
from app.api.v1.endpoints_checklist import get_checklist_summary, list_checklist_items
from app.api.v1.endpoints_journal import list_journal_notes
from app.api.v1.endpoints_medical import list_appointments, list_studies
from app.api.v1.endpoints_media import list_moments, list_vault_documents
from app.api.v1.endpoints_auth import get_auth_status
from app.services.obstetric_calculator import ObstetricCalculatorService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización de tablas, migraciones aditivas seguras y sembrado al arranque
    Base.metadata.create_all(bind=engine)
    ensure_schema_migrations(engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="BabyTrack API",
    version="1.0.0",
    description="Plataforma Web para Seguimiento Obstétrico y Cápsula Familiar (FPP: 07/07/2027)",
    lifespan=lifespan
)

# Montaje de archivos estáticos y carpeta de uploads persistente
base_dir = Path(__file__).resolve().parent
static_dir = base_dir / "static"
templates_dir = base_dir / "templates"
uploads_dir = Path(settings.DATA_DIR) / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")
templates = Jinja2Templates(directory=str(templates_dir))

# Enrutador REST v1
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health_check():
    """Chequeo de estado para Docker y Google Cloud Run."""
    return {
        "status": "healthy",
        "service": "babytrack",
        "env": settings.APP_ENV,
        "defaultDueDate": settings.DEFAULT_DUE_DATE
    }


@app.get("/", response_class=HTMLResponse, tags=["Web"])
def render_index(request: Request, db: Session = Depends(get_db)):
    """Renderiza la vista principal Mobile-First con el Hero Counter y acceso a los 5 módulos."""
    record = get_or_create_settings(db)
    metrics = ObstetricCalculatorService.calculate_metrics(
        due_date=record.due_date,
        calibration_offset_days=record.calibration_offset_days
    )
    checklist_summary = get_checklist_summary(db=db)
    journal_count = db.query(BabyJournalNote).count()
    ultrasounds_count = db.query(MedicalStudy).filter(MedicalStudy.study_type == "ULTRASONIDO").count()
    studies_count = db.query(MedicalStudy).filter(MedicalStudy.study_type != "ULTRASONIDO").count()
    appointments_count = db.query(MedicalAppointment).count()
    moments_count = db.query(MediaMoment).count()
    vault_count = db.query(DocumentVaultItem).count()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "settings": record,
            "metrics": metrics,
            "checklist_summary": checklist_summary,
            "journal_count": journal_count,
            "medical_stats": {
                "studies_count": studies_count,
                "ultrasounds_count": ultrasounds_count,
                "appointments_count": appointments_count,
            },
            "media_stats": {
                "moments_count": moments_count,
                "vault_count": vault_count,
            },
            "auth_status": get_auth_status(request),
            "active_tab": "inicio"
        }
    )


@app.get("/checklist", response_class=HTMLResponse, tags=["Web"])
def render_checklist(request: Request, db: Session = Depends(get_db)):
    """Renderiza la vista interactiva de Checklist de Compras y Presupuesto."""
    record = get_or_create_settings(db)
    items = list_checklist_items(category=None, trimester=None, completed=None, db=db)
    summary = get_checklist_summary(db=db)

    return templates.TemplateResponse(
        request=request,
        name="checklist.html",
        context={
            "settings": record,
            "items_json": json.dumps([i.model_dump(mode="json") for i in items]),
            "summary_json": json.dumps(summary.model_dump(mode="json")),
            "auth_status": get_auth_status(request),
            "active_tab": "checklist"
        }
    )


@app.get("/journal", response_class=HTMLResponse, tags=["Web"])
def render_journal(request: Request, db: Session = Depends(get_db)):
    """Renderiza el Diario de Cartas y Pensamientos para el Bebé (Mamá y Papá)."""
    record = get_or_create_settings(db)
    metrics = ObstetricCalculatorService.calculate_metrics(
        due_date=record.due_date,
        calibration_offset_days=record.calibration_offset_days
    )
    notes = list_journal_notes(author=None, db=db)

    return templates.TemplateResponse(
        request=request,
        name="journal.html",
        context={
            "settings": record,
            "metrics": metrics,
            "notes_json": json.dumps([n.model_dump(mode="json") for n in notes]),
            "auth_status": get_auth_status(request),
            "active_tab": "journal"
        }
    )


@app.get("/medical", response_class=HTMLResponse, tags=["Web"])
def render_medical(request: Request, db: Session = Depends(get_db)):
    """Renderiza el Módulo de Control Prenatal, Estudios Híbridos y Galería de Ecos."""
    record = get_or_create_settings(db)
    studies = list_studies(study_type=None, appointment_id=None, db=db)
    appointments = list_appointments(status_filter=None, type_filter=None, db=db)
    today_iso = ObstetricCalculatorService.get_local_date().isoformat()

    return templates.TemplateResponse(
        request=request,
        name="medical.html",
        context={
            "settings": record,
            "google_calendar_id": (record.google_calendar_id or settings.GOOGLE_CALENDAR_ID or ""),
            "studies_json": json.dumps([s.model_dump(mode="json") for s in studies]),
            "appointments_json": json.dumps([a.model_dump(mode="json") for a in appointments]),
            "today_iso": today_iso,
            "auth_status": get_auth_status(request),
            "active_tab": "medical"
        }
    )


@app.get("/moments", response_class=HTMLResponse, tags=["Web"])
def render_moments(request: Request, db: Session = Depends(get_db)):
    """Renderiza el Álbum Fotográfico de Momentos y la Bóveda de Documentos."""
    record = get_or_create_settings(db)
    moments = list_moments(uploaded_by=None, db=db)
    vault_items = list_vault_documents(category=None, db=db)
    today_iso = ObstetricCalculatorService.get_local_date().isoformat()

    return templates.TemplateResponse(
        request=request,
        name="moments.html",
        context={
            "settings": record,
            "moments_json": json.dumps([m.model_dump(mode="json") for m in moments]),
            "vault_json": json.dumps([v.model_dump(mode="json") for v in vault_items]),
            "today_iso": today_iso,
            "auth_status": get_auth_status(request),
            "active_tab": "moments"
        }
    )
