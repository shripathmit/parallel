# parallel

FDA regulatory change intelligence + behavior-pattern clones, built on the [parallel.ai](https://parallel.ai) API platform.

## The idea

The FDA world changes constantly — new guidances, revised rules, warning letters, recalls. **parallel** watches those changes, understands what they mean, and spins up **behavior-pattern clones** of the stakeholders involved (reviewers, sponsors, enforcement) to predict how each will react.

## The three pillars

**1. Sense** — `src/sense/`
parallel.ai **Monitor** API watches FDA source pages and fires webhooks on change; **Search** discovers new docs; **Extract** pulls clean markdown from guidance PDFs and pages. Webhooks normalize into `ChangeEvent`s stored as JSONL.

**2. Understand** — `src/understand/`
parallel.ai **Task** API analyzes each change event against a structured JSON schema: change type, affected product codes / submission types, severity 1–5, citations, confidence. Results feed a networkx knowledge graph linking changes → product codes → submission types.

**3. Clone** — `src/clones/`
Three behavior-pattern clones run on the parallel.ai **Chat** API (web-grounded completions):
- **Enforcement clone** — predicts enforcement risk from warning-letter patterns
- **Reviewer clone** — predicts the questions an FDA reviewer would ask under a new guidance
- **Sponsor clone** — predicts how industry adapts submission strategy after a change

Clone behavior profiles are mined with **FindAll** + **Task**. `src/simulate/` fans a change out to all clones side-by-side; `src/surface/` adds severity alerts and a FastAPI service.

## Phases

- **Phase 0** — scaffold (this repo): config, parallel.ai client, docs
- **Phase 1** — Sense: monitors live, change events flowing (`src/sense/`)
- **Phase 2** — Understand: Task-powered analysis + knowledge graph (`src/understand/`)
- **Phase 3** — First clone: enforcement clone from warning-letter data (`src/clones/`)
- **Phase 4** — Clone fleet + batch simulation via Task Groups (`src/simulate/`)
- **Phase 5** — Alerts + FastAPI service (`src/surface/`)

## Setup

```bash
cp .env.example .env
# edit .env and set PARALLEL_API_KEY (get one at https://platform.parallel.ai)
pip install -r requirements.txt
```

The parallel.ai client itself (`src/par_client.py`) is stdlib-only (`urllib`) — no SDK needed. If `PARALLEL_API_KEY` is missing or still the placeholder, every API call raises a clear error telling you to set it. The key is never printed or logged.

## Running each phase

```bash
# Phase 1: register monitors (webhooks point at your public base URL)
python - <<'EOF'
from config import load_settings
from src.par_client import ParallelClient
from src.sense.monitors import setup_monitors
s = load_settings()
setup_monitors(ParallelClient(), webhook_url=f"{s.webhook_base_url}/webhooks/parallel/monitor")
EOF

# Phase 1 (alt): backfill historical events without monitors
python -m src.sense.backfill "AI/ML medical device guidance" --max-results 20

# Phase 2: analyze one event
python - <<'EOF'
from config import load_settings
from src.par_client import ParallelClient
from src.sense.events import EventStore
from src.understand.analyze import analyze_change
s = load_settings()
store = EventStore(s.data_dir)
event = store.list()[0]
print(analyze_change(ParallelClient(), event))
EOF

# Phase 4: simulate all clones against an analysis dict
python - <<'EOF'
import json
from src.par_client import ParallelClient
from src.simulate.runner import run_simulation
analysis = json.load(open("data/analyses/<event_id>.json"))
print(json.dumps(run_simulation(ParallelClient(), analysis), indent=2))
EOF

# Phase 5: run the API service
uvicorn src.surface.api:app --reload

# Tests (no API key needed)
python -m unittest discover -s tests -v
```

See `docs/plan.md` for the full detailed plan.
