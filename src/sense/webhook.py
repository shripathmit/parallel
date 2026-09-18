"""Normalize parallel.ai Monitor webhook payloads into ChangeEvents."""
import hashlib
import hmac

from src.sense.events import ChangeEvent


def normalize_monitor_payload(payload: dict) -> ChangeEvent:
    """Convert a Monitor webhook body into a ChangeEvent.

    The exact webhook body shape is not yet confirmed; this handles the
    documented shape defensively and falls back to top-level fields.
    TODO: verify against docs.parallel.ai once the first webhook arrives.
    """
    monitor = payload.get("monitor", {}) or {}
    change = payload.get("change", {}) or {}
    # Some payloads may nest the change under "event" or "notification".
    if not change:
        change = payload.get("event", payload.get("notification", {})) or {}

    url = change.get("url", "") or monitor.get("url", "")
    title = (
        change.get("title", "")
        or change.get("summary", "")
        or payload.get("title", "Untitled change")
    )
    return ChangeEvent(
        source=monitor.get("name", payload.get("source", "monitor")),
        url=url,
        title=title,
        change_type=change.get("change_type", "unknown"),
        raw_diff=change.get("diff", change.get("content", "")),
        status="raw",
    )


def verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """HMAC-SHA256 webhook signature check.

    TODO: verify Parallel's actual webhook signing scheme (header name and
    algorithm) in docs.parallel.ai; wire the real secret from settings.
    """
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
