"""Project configuration loaded from environment (.env supported)."""
import os
import secrets
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional; env vars still work
    pass


@dataclass
class Settings:
    parallel_api_key: str
    webhook_base_url: str
    alert_email: str
    data_dir: str
    database_url: str = ""
    request_timeout: int = 60
    session_secret: str = field(default_factory=lambda: secrets.token_hex(32))
    access_code: str = "parallel"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            parallel_api_key=os.environ.get("PARALLEL_API_KEY", ""),
            webhook_base_url=os.environ.get("WEBHOOK_BASE_URL", "http://localhost:8000"),
            alert_email=os.environ.get("ALERT_EMAIL", ""),
            data_dir=os.environ.get("DATA_DIR", "data"),
            database_url=os.environ.get("DATABASE_URL", ""),
            request_timeout=int(os.environ.get("PARALLEL_TIMEOUT", "60")),
            session_secret=os.environ.get("SESSION_SECRET", secrets.token_hex(32)),
            access_code=os.environ.get("ACCESS_CODE", "parallel"),
        )


def load_settings() -> Settings:
    return Settings.from_env()
