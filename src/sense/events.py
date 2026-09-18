"""Change events: the unit of work flowing through the pipeline."""
import json
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path

# Event lifecycle: raw -> analyzed -> simulated -> alerted
STATUSES = ("raw", "analyzing", "analyzed", "simulating", "simulated", "alerted")


@dataclass
class ChangeEvent:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: str = ""
    url: str = ""
    title: str = ""
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    change_type: str = "unknown"  # new | revised | withdrawn | discovered | unknown
    raw_diff: str = ""
    status: str = "raw"
    demo: bool = False  # True for seeded illustrative data (called out in UI)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


class EventStore:
    """Append-only JSONL store for change events."""

    def __init__(self, data_dir):
        self.path = Path(data_dir) / "events.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def append(self, event: ChangeEvent) -> ChangeEvent:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict()) + "\n")
        return event

    def list(self, status=None):
        events = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(ChangeEvent.from_dict(json.loads(line)))
        if status:
            events = [e for e in events if e.status == status]
        return events

    def get(self, event_id):
        for event in self.list():
            if event.id == event_id:
                return event
        return None

    def mark_processed(self, event_id, status):
        """Rewrite the store with one event's status updated."""
        if status not in STATUSES:
            raise ValueError(f"Unknown status {status!r}; expected one of {STATUSES}")
        events = self.list()
        found = False
        for event in events:
            if event.id == event_id:
                event.status = status
                found = True
        if not found:
            raise KeyError(f"No event with id {event_id!r}")
        with self.path.open("w", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event.to_dict()) + "\n")
        return True
