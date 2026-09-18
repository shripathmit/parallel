"""FastAPI service: webhooks, events, analysis, simulation.

Run from the repo root:  uvicorn src.surface.api:app --reload
"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from config import load_settings
from src.par_client import ParallelClient
from src.sense.events import ChangeEvent, EventStore
from src.sense.webhook import normalize_monitor_payload, verify_signature
from src.simulate.runner import run_simulation
from src.surface.alerts import maybe_alert
from src.understand.analyze import analyze_change
from src.understand.knowledge_graph import KnowledgeGraph

settings = load_settings()
store = EventStore(settings.data_dir)
kg = KnowledgeGraph()
KG_PATH = Path(settings.data_dir) / "knowledge_graph.json"
if KG_PATH.exists():
    kg = KnowledgeGraph.load(KG_PATH)

app = FastAPI(title="parallel", version="0.1.0")


def _analysis_path(event_id: str) -> Path:
    path = Path(settings.data_dir) / "analyses"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{event_id}.json"


def _save_analysis(event_id: str, analysis: dict):
    with _analysis_path(event_id).open("w", encoding="utf-8") as fh:
        json.dump(analysis, fh, indent=2)


def _load_analysis(event_id: str):
    path = _analysis_path(event_id)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhooks/parallel/monitor")
async def monitor_webhook(request: Request):
    raw_body = await request.body()
    payload = await request.json()
    # TODO: verify signature once Parallel's signing scheme is confirmed;
    # secret should come from settings, not be hardcoded.
    _ = verify_signature(raw_body, request.headers.get("x-parallel-signature", ""), secret="")
    event = normalize_monitor_payload(payload)
    store.append(event)
    return {"status": "accepted", "event_id": event.id}


@app.get("/events")
def list_events(status: str = None):
    return [e.to_dict() for e in store.list(status=status)]


@app.get("/events/{event_id}")
def get_event(event_id: str):
    event = store.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"event": event.to_dict(), "analysis": _load_analysis(event_id)}


@app.post("/events/{event_id}/analyze")
def analyze_event(event_id: str):
    event = store.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    analysis = analyze_change(ParallelClient(), event)
    _save_analysis(event_id, analysis)
    kg.add_analysis(event, analysis)
    kg.save(KG_PATH)
    store.mark_processed(event_id, "analyzed")
    alert = maybe_alert(analysis, settings)
    return {"event_id": event_id, "analysis": analysis, "alert": alert}


@app.post("/simulate/{event_id}")
def simulate_event(event_id: str):
    event = store.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    analysis = _load_analysis(event_id)
    if not analysis:
        raise HTTPException(
            status_code=400, detail="No analysis stored; POST /events/{id}/analyze first"
        )
    result = run_simulation(ParallelClient(), analysis)
    store.mark_processed(event_id, "simulated")
    return {"event_id": event_id, **result}
