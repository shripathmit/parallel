"""Severity-based alerting for analyzed changes."""
from datetime import datetime, timezone
from pathlib import Path

SEVERITY_THRESHOLD = 4


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

    log_path = Path(settings.data_dir) / "alerts.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n")

    # TODO: wire a real sender here (SMTP email to settings.alert_email,
    # or a Slack/Teams webhook). Stubbed to log-only for now.
    return {"alerted": True, "severity": severity, "message": message}
