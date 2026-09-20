"""Per-event artifacts: analyses, simulations, demo payloads.

DB mode stores each artifact as one JSON document in the schemaless
parallel_docs table (keys "analysis:{id}", "simulation:{id}",
"demo:{id}:{kind}") -- no migrations when artifact shapes evolve. File mode
keeps the exact on-disk layout the app has always used (analyses/{id}.json,
simulations/{id}.json, demo/{id}.{kind}.json), so existing behavior is
unchanged without DATABASE_URL.
"""
import json
from pathlib import Path

from . import db as _db

KINDS = ("analysis", "simulation")


def _analysis_key(event_id: str) -> str:
    return f"analysis:{event_id}"


def _simulation_key(event_id: str) -> str:
    return f"simulation:{event_id}"


def _demo_key(event_id: str, kind: str) -> str:
    return f"demo:{event_id}:{kind}"


# ---------------------------------------------------------------- analyses


def save_analysis(data_dir, event_id: str, analysis: dict):
    if _db.enabled():
        _db.doc_put(_analysis_key(event_id), analysis)
        return
    path = Path(data_dir) / "analyses"
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{event_id}.json").write_text(
        json.dumps(analysis, indent=2), encoding="utf-8"
    )


def load_analysis(data_dir, event_id: str):
    if _db.enabled():
        return _db.doc_get(_analysis_key(event_id))
    path = Path(data_dir) / "analyses" / f"{event_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# -------------------------------------------------------------- simulations


def save_simulation(data_dir, event_id: str, simulation: dict):
    if _db.enabled():
        _db.doc_put(_simulation_key(event_id), simulation)
        return
    path = Path(data_dir) / "simulations"
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{event_id}.json").write_text(
        json.dumps(simulation, indent=2), encoding="utf-8"
    )


def load_simulation(data_dir, event_id: str):
    if _db.enabled():
        return _db.doc_get(_simulation_key(event_id))
    path = Path(data_dir) / "simulations" / f"{event_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------ demo payloads


def save_demo_payload(data_dir, event_id: str, kind: str, payload: dict):
    if kind not in KINDS:
        raise ValueError(f"Unknown demo payload kind {kind!r}")
    if _db.enabled():
        _db.doc_put(_demo_key(event_id, kind), payload)
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
        return _db.doc_get(_demo_key(event_id, kind))
    path = Path(data_dir) / "demo" / f"{event_id}.{kind}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
