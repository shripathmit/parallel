"""Severity-based alerting for analyzed changes."""
from datetime import datetime, timezone
from pathlib import Path

from src.store import db as _db

SEVERITY_THRESHOLD = 4


def _log_alert_db(severity: int, message: str):
    """Best-effort persistent alert record. Never raises: alerting must not
    break the pipeline it reports on."""
    try:
        if _db.enabled():
            with _db.connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "insert into parallel_alerts (severity, message) values (%s, %s)",
                    (severity, message),
                )
    except Exception:
        pass


def maybe_alert(analysis: dict, settings) -> dict:
    """Alert when severity meets the threshold. Returns what happened."""
    try:
        severity = int(analysis.get("severity") or 0)
    except (TypeError, ValueError):
        severity = 0
    if severity < SEVERITY_THRESHOLD:
        return {"alerted": False, "severity": severity}

    summary = analysis.get("summary", "Untitled change")
    message = f"[parallel] HIGH-SEVERITY FDA CHANGE (severity {severity}/5): {summary}"
    print(message, flush=True)
    _log_alert_db(severity, message)

    log_path = Path(settings.data_dir) / "alerts.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")

    # TODO: wire a real sender here (SMTP email to settings.alert_email,
    # or a Slack/Teams webhook). Stubbed to log-only for now.
    return {"alerted": True, "severity": severity, "message": message}
