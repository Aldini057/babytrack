from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_schema_migrations(target_engine=engine):
    """
    Aplica migraciones aditivas de esquema de forma segura e idempotente
    sin modificar ni borrar ningún registro existente en la base de datos.
    """
    inspector = inspect(target_engine)
    table_names = set(inspector.get_table_names())
    if "medical_appointments" in table_names:
        cols = {c["name"] for c in inspector.get_columns("medical_appointments")}
        with target_engine.begin() as conn:
            if "appointment_type" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE medical_appointments "
                        "ADD COLUMN appointment_type VARCHAR(30) NOT NULL DEFAULT 'MEDICO'"
                    )
                )
            if "reminder_minutes_before" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE medical_appointments "
                        "ADD COLUMN reminder_minutes_before INTEGER NOT NULL DEFAULT 1440"
                    )
                )
            if "google_event_id" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE medical_appointments "
                        "ADD COLUMN google_event_id VARCHAR(255)"
                    )
                )
            if "google_event_link" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE medical_appointments "
                        "ADD COLUMN google_event_link VARCHAR(500)"
                    )
                )

    if "pregnancy_settings" in table_names:
        cols = {c["name"] for c in inspector.get_columns("pregnancy_settings")}
        if "google_calendar_id" not in cols:
            with target_engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE pregnancy_settings "
                        "ADD COLUMN google_calendar_id VARCHAR(255)"
                    )
                )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
