"""Project configuration loaded from environment (.env supported)."""
import os
from dataclasses import dataclass

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
    request_timeout: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            parallel_api_key=os.environ.get("PARALLEL_API_KEY", ""),
            webhook_base_url=os.environ.get("WEBHOOK_BASE_URL", "http://localhost:8000"),
            alert_email=os.environ.get("ALERT_EMAIL", ""),
            data_dir=os.environ.get("DATA_DIR", "data"),
            request_timeout=int(os.environ.get("PARALLEL_TIMEOUT", "60")),
        )


def load_settings() -> Settings:
    return Settings.from_env()
