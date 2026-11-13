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
        if "appointment_type" not in cols:
            with target_engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE medical_appointments "
                        "ADD COLUMN appointment_type VARCHAR(30) NOT NULL DEFAULT 'MEDICO'"
                    )
                )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
