"""Change events: the unit of work flowing through the pipeline."""
import json
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path

from src.store import db as _db

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


_EVENT_COLUMNS = (
    "id, source, url, title, detected_at, change_type, raw_diff, status, demo"
)


def _row_to_event(row: dict) -> ChangeEvent:
    """Map a parallel_events row (dict_row) back onto a ChangeEvent."""
    detected = row["detected_at"]
    if hasattr(detected, "isoformat"):  # timestamptz -> datetime
        detected = detected.isoformat()
    return ChangeEvent(
        id=row["id"],
        source=row["source"] or "",
        url=row["url"] or "",
        title=row["title"] or "",
        detected_at=detected,
        change_type=row["change_type"] or "unknown",
        raw_diff=row["raw_diff"] or "",
        status=row["status"] or "raw",
        demo=bool(row["demo"]),
    )


class EventStore:
    """Change-event store: Postgres when DATABASE_URL is set, otherwise the
    original append-only JSONL file. Same interface either way."""

    def __init__(self, data_dir):
        self.data_dir = str(data_dir)
        self.use_db = _db.enabled()
        if not self.use_db:
            self.path = Path(data_dir) / "events.jsonl"
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self.path.touch()

    # ------------------------------------------------------------------ write

    def append(self, event: ChangeEvent) -> ChangeEvent:
        if self.use_db:
            with _db.connection() as conn, conn.cursor() as cur:
                cur.execute(
                    f"""
                    insert into parallel_events
                        ({_EVENT_COLUMNS})
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (id) do nothing
                    """,
                    (
                        event.id,
                        event.source,
                        event.url,
                        event.title,
                        event.detected_at,
                        event.change_type,
                        event.raw_diff,
                        event.status,
                        event.demo,
                    ),
                )
            return event
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict()) + "\n")
        return event

    def mark_processed(self, event_id, status):
        """Mark one event's status. Raises KeyError when unknown."""
        if status not in STATUSES:
            raise ValueError(f"Unknown status {status!r}; expected one of {STATUSES}")
        if self.use_db:
            with _db.connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "update parallel_events set status = %s where id = %s",
                    (status, event_id),
                )
                if cur.rowcount == 0:
                    raise KeyError(f"No event with id {event_id!r}")
            return True
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

    # ------------------------------------------------------------------- read

    def list(self, status=None):
        if self.use_db:
            with _db.connection() as conn, conn.cursor() as cur:
                if status:
                    cur.execute(
                        f"select {_EVENT_COLUMNS} from parallel_events "
                        "where status = %s order by detected_at",
                        (status,),
                    )
                else:
                    cur.execute(
                        f"select {_EVENT_COLUMNS} from parallel_events "
                        "order by detected_at"
                    )
                return [_row_to_event(row) for row in cur.fetchall()]
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
        if self.use_db:
            with _db.connection() as conn, conn.cursor() as cur:
                cur.execute(
                    f"select {_EVENT_COLUMNS} from parallel_events where id = %s",
                    (event_id,),
                )
                row = cur.fetchone()
                return _row_to_event(row) if row else None
        for event in self.list():
            if event.id == event_id:
                return event
        return None
