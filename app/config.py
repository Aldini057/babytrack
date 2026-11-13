import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    TZ: str = "America/Mexico_City"
    PORT: int = 8000
    DEFAULT_DUE_DATE: str = "2027-07-07"
    FAMILY_ACCESS_PIN: str = "0707"
    GOOGLE_CALENDAR_ID: str = ""
    
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: str = os.getenv("DATA_DIR", str(Path(__file__).resolve().parent.parent / "data"))
    DATABASE_URL: str = ""

    def model_post_init(self, __context):
        if not self.DATABASE_URL:
            # Resolve SQLite path
            db_path = Path(self.DATA_DIR) / "babytrack.db"
            self.DATABASE_URL = f"sqlite:///{db_path}"

        # Ensure directory tree exists
        data_path = Path(self.DATA_DIR)
        for folder in ["ecos", "estudios", "documentos", "momentos"]:
            (data_path / "uploads" / folder).mkdir(parents=True, exist_ok=True)

settings = Settings()
