"""Per-event artifacts: analyses, simulations, demo payloads.

DB mode stores them in Postgres; file mode keeps the exact on-disk layout
the app has always used (analyses/{id}.json, simulations/{id}.json,
demo/{id}.{kind}.json), so existing behavior is unchanged without DATABASE_URL.
"""
import json
from pathlib import Path

from . import db as _db

KINDS = ("analysis", "simulation")


def _jsonb(payload: dict):
    from psycopg.types.json import Json

    return Json(payload)


# ---------------------------------------------------------------- analyses


def save_analysis(data_dir, event_id: str, analysis: dict):
    if _db.enabled():
        with _db.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into parallel_analyses (event_id, payload, updated_at)
                values (%s, %s, now())
                on conflict (event_id)
                do update set payload = excluded.payload, updated_at = now()
                """,
                (event_id, _jsonb(analysis)),
            )
        return
    path = Path(data_dir) / "analyses"
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{event_id}.json").write_text(
        json.dumps(analysis, indent=2), encoding="utf-8"
    )


def load_analysis(data_dir, event_id: str):
    if _db.enabled():
        with _db.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "select payload from parallel_analyses where event_id = %s",
                (event_id,),
            )
            row = cur.fetchone()
            return row["payload"] if row else None
    path = Path(data_dir) / "analyses" / f"{event_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# -------------------------------------------------------------- simulations


def save_simulation(data_dir, event_id: str, simulation: dict):
    if _db.enabled():
        with _db.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into parallel_simulations (event_id, payload, updated_at)
                values (%s, %s, now())
                on conflict (event_id)
                do update set payload = excluded.payload, updated_at = now()
                """,
                (event_id, _jsonb(simulation)),
            )
        return
    path = Path(data_dir) / "simulations"
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{event_id}.json").write_text(
        json.dumps(simulation, indent=2), encoding="utf-8"
    )


def load_simulation(data_dir, event_id: str):
    if _db.enabled():
        with _db.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "select payload from parallel_simulations where event_id = %s",
                (event_id,),
            )
            row = cur.fetchone()
            return row["payload"] if row else None
    path = Path(data_dir) / "simulations" / f"{event_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------ demo payloads


def save_demo_payload(data_dir, event_id: str, kind: str, payload: dict):
    if kind not in KINDS:
        raise ValueError(f"Unknown demo payload kind {kind!r}")
    if _db.enabled():
        with _db.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into parallel_demo_payloads (event_id, kind, payload)
                values (%s, %s, %s)
                on conflict (event_id, kind)
                do update set payload = excluded.payload
                """,
                (event_id, kind, _jsonb(payload)),
            )
        return
    demo_dir = Path(data_dir) / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    (demo_dir / f"{event_id}.{kind}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def load_demo_payload(data_dir, event_id: str, kind: str):
    if kind not in KINDS:
        raise ValueError(f"Unknown demo payload kind {kind!r}")
    if _db.enabled():
        with _db.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "select payload from parallel_demo_payloads "
                "where event_id = %s and kind = %s",
                (event_id, kind),
            )
            row = cur.fetchone()
            return row["payload"] if row else None
    path = Path(data_dir) / "demo" / f"{event_id}.{kind}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
