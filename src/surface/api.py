"""FastAPI service: webhooks, events, analysis, simulation + HTML dashboard.

Run from the repo root:  uvicorn src.surface.api:app --reload
Dashboard: http://localhost:8000/

Demo mode: when no real PARALLEL_API_KEY is configured, the service seeds
illustrative demo data on startup (set DEMO_SEED=false to disable) and the
"Run analysis" / "Run simulation" buttons materialize canned demo payloads
so the full pipeline flow is explorable. Everything demo is labeled in the UI.
"""
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import load_settings
from src.clones.clone import Clone
from src.clones.patterns import PatternStore, match_patterns
from src.clones.profiles import ALL_PROFILES
from src.demo_seed import seed as seed_demo
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

DEMO_DIR = Path(settings.data_dir) / "demo"


def _key_ok() -> bool:
    return bool(settings.parallel_api_key) and settings.parallel_api_key != PLACEHOLDER_KEY


@asynccontextmanager
async def lifespan(app: FastAPI):
    mode = os.environ.get("DEMO_SEED", "auto").lower()
    if mode != "false" and not store.list():
        if mode == "true" or not _key_ok():
            seed_demo(settings.data_dir)
    yield


app = FastAPI(title="parallel", version="0.3.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _pattern_store() -> PatternStore:
    return PatternStore(settings.data_dir)


def _build_clones(client: ParallelClient, analysis: dict) -> list:
    """Clones grounded in the pattern library: match_patterns selects the
    evidence each clone reasons from, per stakeholder."""
    patterns = _pattern_store().list()
    clones = []
    for profile in ALL_PROFILES:
        matched = match_patterns(analysis, patterns, profile["name"])
        clones.append(Clone(client, profile, patterns=matched))
    return clones


def _has_demo() -> bool:
    return any(e.demo for e in store.list())


def _ctx(request: Request, active: str = "home", **kw) -> dict:
    return {
        "request": request,
        "active": active,
        "key_ok": _key_ok(),
        "demo_mode": _has_demo(),
        **kw,
    }


def _analysis_path(event_id: str) -> Path:
    path = Path(settings.data_dir) / "analyses"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{event_id}.json"


def _simulation_path(event_id: str) -> Path:
    path = Path(settings.data_dir) / "simulations"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{event_id}.json"


def _demo_payload(event_id: str, kind: str):
    """Canned demo payload (analysis|simulation), or None."""
    path = DEMO_DIR / f"{event_id}.{kind}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


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


def _severity_of(event_id: str):
    analysis = _load_analysis(event_id)
    if analysis:
        return analysis.get("severity")
    return None


def _stats() -> dict:
    events = store.list()
    by_status = {}
    for e in events:
        by_status[e.status] = by_status.get(e.status, 0) + 1
    sev_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for e in events:
        s = _severity_of(e.id)
        if s in sev_counts:
            sev_counts[s] += 1
    monitors = 0
    if _key_ok():
        try:
            monitors = len(ParallelClient().list_monitors())
        except Exception:
            monitors = 0
    return {
        "total": len(events),
        "by_status": by_status,
        "severity": sev_counts,
        "high_sev": sev_counts[4] + sev_counts[5],
        "monitors": monitors,
        "demo": sum(1 for e in events if e.demo),
    }


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
    result = run_simulation(
        ParallelClient(), analysis, clones=_build_clones(ParallelClient(), analysis)
    )
    _save_simulation(event_id, result)
    store.mark_processed(event_id, "simulated")
    return {"event_id": event_id, **result}


# ---------------------------------------------------------------- Dashboard


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    stats = _stats()
    recent = sorted(store.list(), key=lambda e: e.detected_at, reverse=True)[:8]
    return templates.TemplateResponse(
        request,
        "index.html",
        _ctx(
            request,
            "home",
            stats=stats,
            recent=recent,
            sev_of=_severity_of,
            sources=FDA_SOURCES,
        ),
    )


@app.get("/ui/events", response_class=HTMLResponse)
def ui_events(
    request: Request, status: str = "all", severity: str = "all", q: str = ""
):
    events = sorted(store.list(), key=lambda e: e.detected_at, reverse=True)
    if status != "all":
        events = [e for e in events if e.status == status]
    if severity != "all":
        events = [e for e in events if str(_severity_of(e.id)) == severity]
    if q:
        ql = q.lower()
        events = [
            e
            for e in events
            if ql in e.title.lower() or ql in e.source.lower() or ql in e.url.lower()
        ]
    return templates.TemplateResponse(
        request,
        "events.html",
        _ctx(
            request,
            "events",
            events=events,
            status=status,
            severity=severity,
            q=q,
            sev_of=_severity_of,
        ),
    )


@app.get("/ui/events/{event_id}", response_class=HTMLResponse)
def ui_event_detail(
    request: Request, event_id: str, error: str = None, notice: str = None
):
    event = store.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    analysis = _load_analysis(event_id)
    simulation = _load_simulation(event_id)
    return templates.TemplateResponse(
        request,
        "event_detail.html",
        _ctx(
            request,
            "events",
            event=event,
            analysis=analysis,
            simulation=simulation,
            error=error,
            notice=notice,
        ),
    )


@app.post("/ui/events/{event_id}/analyze")
def ui_analyze_event(event_id: str):
    event = store.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    # Demo fallback: materialize the canned demo analysis so the flow works
    # end-to-end without an API key. Labeled as demo in the UI.
    if not _key_ok():
        demo = _demo_payload(event_id, "analysis")
        if demo:
            _save_analysis(event_id, demo)
            store.mark_processed(event_id, "analyzed")
            return RedirectResponse(
                f"/ui/events/{event_id}?notice=Demo analysis loaded",
                status_code=303,
            )
        return RedirectResponse(
            f"/ui/events/{event_id}?error=Set PARALLEL_API_KEY to run live analysis",
            status_code=303,
        )
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
    if not _key_ok():
        demo = _demo_payload(event_id, "simulation")
        if demo:
            _save_simulation(event_id, demo)
            store.mark_processed(event_id, "simulated")
            return RedirectResponse(
                f"/ui/events/{event_id}?notice=Demo simulation loaded",
                status_code=303,
            )
        return RedirectResponse(
            f"/ui/events/{event_id}?error=Set PARALLEL_API_KEY to run live simulation",
            status_code=303,
        )
    try:
        client = ParallelClient()
        result = run_simulation(client, analysis, clones=_build_clones(client, analysis))
    except ParallelAPIError as exc:
        return RedirectResponse(
            f"/ui/events/{event_id}?error=Simulation failed: {exc}", status_code=303
        )
    _save_simulation(event_id, result)
    store.mark_processed(event_id, "simulated")
    return RedirectResponse(
        f"/ui/events/{event_id}?notice=Simulation complete", status_code=303
    )


@app.get("/ui/clones", response_class=HTMLResponse)
def ui_clones(request: Request):
    # Latest prediction per clone, pulled from stored simulations.
    latest = {}
    for event in sorted(store.list(), key=lambda e: e.detected_at, reverse=True):
        sim = _load_simulation(event.id)
        if not sim:
            continue
        for name, pred in (sim.get("predictions") or {}).items():
            if name not in latest:
                latest[name] = {"event": event, "pred": pred}
    patterns = _pattern_store().list()
    by_stakeholder = {}
    for p in patterns:
        by_stakeholder.setdefault(p.stakeholder, []).append(p)
    return templates.TemplateResponse(
        request,
        "clones.html",
        _ctx(
            request,
            "clones",
            profiles=ALL_PROFILES,
            latest=latest,
            by_stakeholder=by_stakeholder,
        ),
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
        request,
        "monitors.html",
        _ctx(
            request,
            "monitors",
            sources=FDA_SOURCES,
            live=live,
            error=error,
            notice=notice,
        ),
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
        return RedirectResponse(
            f"/ui/monitors?error=Teardown failed: {exc}", status_code=303
        )
    return RedirectResponse("/ui/monitors?notice=All monitors stopped", status_code=303)
