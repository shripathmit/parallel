"""FastAPI service: webhooks, events, analysis, simulation + HTML dashboard.

Run from the repo root:  uvicorn src.surface.api:app --reload
Dashboard: http://localhost:8000/
"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import load_settings
from src.par_client import PLACEHOLDER_KEY, ParallelAPIError, ParallelClient
from src.sense.events import ChangeEvent, EventStore
from src.sense.monitors import FDA_SOURCES, setup_monitors, teardown_monitors
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

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="parallel", version="0.2.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _key_ok() -> bool:
    return bool(settings.parallel_api_key) and settings.parallel_api_key != PLACEHOLDER_KEY


def _ctx(request: Request, active: str = "home", **kw) -> dict:
    return {"request": request, "active": active, "key_ok": _key_ok(), **kw}


def _analysis_path(event_id: str) -> Path:
    path = Path(settings.data_dir) / "analyses"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{event_id}.json"


def _simulation_path(event_id: str) -> Path:
    path = Path(settings.data_dir) / "simulations"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{event_id}.json"


def _save_json(path: Path, data: dict):
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def _load_json(path: Path):
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_analysis(event_id: str, analysis: dict):
    _save_json(_analysis_path(event_id), analysis)


def _load_analysis(event_id: str):
    return _load_json(_analysis_path(event_id))


def _save_simulation(event_id: str, simulation: dict):
    _save_json(_simulation_path(event_id), simulation)


def _load_simulation(event_id: str):
    return _load_json(_simulation_path(event_id))


def _stats() -> dict:
    events = store.list()
    counts = {"total": len(events), "raw": 0, "analyzed": 0, "simulated": 0, "monitors": 0}
    for e in events:
        if e.status in counts:
            counts[e.status] += 1
    try:
        counts["monitors"] = len(ParallelClient().list_monitors())
    except Exception:
        counts["monitors"] = 0
    return counts


# ---------------------------------------------------------------- JSON API

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
    return {
        "event": event.to_dict(),
        "analysis": _load_analysis(event_id),
        "simulation": _load_simulation(event_id),
    }


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
    _save_simulation(event_id, result)
    store.mark_processed(event_id, "simulated")
    return {"event_id": event_id, **result}


# ---------------------------------------------------------------- Dashboard

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    events = store.list()
    recent = [e.to_dict() for e in reversed(events[-8:])]
    return templates.TemplateResponse(
        request, "index.html", _ctx(request, "home", stats=_stats(), recent=recent)
    )


@app.get("/ui/events", response_class=HTMLResponse)
def ui_events(request: Request, status: str = "all"):
    events = store.list(status=None if status == "all" else status)
    events = [e.to_dict() for e in reversed(events)]
    return templates.TemplateResponse(
        request, "events.html", _ctx(request, "events", events=events, status=status)
    )


@app.get("/ui/events/{event_id}", response_class=HTMLResponse)
def ui_event_detail(request: Request, event_id: str, error: str = None, notice: str = None):
    event = store.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return templates.TemplateResponse(
        request, "event_detail.html",
        _ctx(
            request,
            "events",
            event=event.to_dict(),
            analysis=_load_analysis(event_id),
            simulation=_load_simulation(event_id),
            error=error,
            notice=notice,
        ),
    )


@app.post("/ui/events/{event_id}/analyze")
def ui_analyze_event(event_id: str):
    event = store.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    try:
        analysis = analyze_change(ParallelClient(), event)
    except ParallelAPIError as exc:
        return RedirectResponse(
            f"/ui/events/{event_id}?error=Analysis failed: {exc}", status_code=303
        )
    _save_analysis(event_id, analysis)
    kg.add_analysis(event, analysis)
    kg.save(KG_PATH)
    store.mark_processed(event_id, "analyzed")
    maybe_alert(analysis, settings)
    return RedirectResponse(
        f"/ui/events/{event_id}?notice=Analysis complete", status_code=303
    )


@app.post("/ui/events/{event_id}/simulate")
def ui_simulate_event(event_id: str):
    event = store.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    analysis = _load_analysis(event_id)
    if not analysis:
        return RedirectResponse(
            f"/ui/events/{event_id}?error=Analyze the event first", status_code=303
        )
    try:
        result = run_simulation(ParallelClient(), analysis)
    except ParallelAPIError as exc:
        return RedirectResponse(
            f"/ui/events/{event_id}?error=Simulation failed: {exc}", status_code=303
        )
    _save_simulation(event_id, result)
    store.mark_processed(event_id, "simulated")
    return RedirectResponse(
        f"/ui/events/{event_id}?notice=Simulation complete", status_code=303
    )


@app.get("/ui/monitors", response_class=HTMLResponse)
def ui_monitors(request: Request, error: str = None, notice: str = None):
    live = None
    if _key_ok():
        try:
            live = ParallelClient().list_monitors()
        except ParallelAPIError as exc:
            error = f"Could not list monitors: {exc}"
    return templates.TemplateResponse(
        request, "monitors.html",
        _ctx(request, "monitors", sources=FDA_SOURCES, live=live, error=error, notice=notice),
    )


@app.post("/ui/monitors/setup")
def ui_monitors_setup(request: Request):
    webhook_url = settings.webhook_base_url.rstrip("/") + "/webhooks/parallel/monitor"
    try:
        created = setup_monitors(ParallelClient(), webhook_url)
    except ParallelAPIError as exc:
        return RedirectResponse(f"/ui/monitors?error=Setup failed: {exc}", status_code=303)
    return RedirectResponse(
        f"/ui/monitors?notice=Started {len(created)} monitors", status_code=303
    )


@app.post("/ui/monitors/teardown")
def ui_monitors_teardown(request: Request):
    try:
        teardown_monitors(ParallelClient())
    except ParallelAPIError as exc:
        return RedirectResponse(f"/ui/monitors?error=Teardown failed: {exc}", status_code=303)
    return RedirectResponse("/ui/monitors?notice=All monitors stopped", status_code=303)
