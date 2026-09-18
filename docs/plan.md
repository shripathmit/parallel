# parallel — detailed plan

## Vision

**parallel** is a system that watches the FDA regulatory world in parallel, understands what changed, and spins up behavior-pattern clones of stakeholders to simulate impact — so a regulatory, product, or strategy team can see around corners instead of reading about changes after the fact.

## The three pillars

### 1. Sense — ingestion + change detection

- **Sources (priority order):** FDA guidance documents (CDRH/CDER/CBER), FDA warning letters, Federal Register FDA rules, FDA recall database, 510(k)/PMA/De Novo decision database, FAERS adverse events, advisory committee materials.
- **parallel.ai Monitor API** (`POST /v1alpha/monitors`) watches the source listing pages on a schedule and fires webhook notifications on change — this replaces nearly all custom poller code.
- **parallel.ai Search API** discovers new/changed FDA docs that have no monitor yet; **Extract API** pulls clean, token-efficient markdown from guidance PDFs and JS-heavy pages for diffing.
- Our code: a webhook receiver that normalizes Monitor payloads into `ChangeEvent` records (id, source, url, title, detected_at, change_type, raw_diff, status) persisted as JSONL, plus a Search+Extract backfill script to seed history.

### 2. Understand — change intelligence

- **parallel.ai Task API** (`POST /v1/tasks/runs`) runs per change event with our structured output schema: change type (`new_requirement` | `tightened` | `relaxed` | `clarification` | `enforcement_shift`), plain-language summary, affected product codes, affected submission types, severity 1–5, citations, confidence 0–1. The Task API natively returns cited, confidence-scored structured output — exactly this shape.
- Our code: the JSON schemas, the objective builder, async polling to completion, batch analysis via **Task Groups** (`POST /v1beta/tasks/groups`, up to 1000 tasks per POST), and a networkx knowledge graph linking change → product code → submission type → cited regulation, so one change fans out to everything it touches.

### 3. Clone — behavior-pattern clones

A clone is an agent whose behavior profile is **mined from historical data**, not hand-written:

- **Enforcement clone** — mined from warning-letter patterns via **FindAll** (`POST /v1beta/findall/runs`) + Task; predicts enforcement risk for a given practice.
- **Reviewer clone** — mined from 510(k)/PMA decision and deficiency patterns; predicts the questions an FDA reviewer would ask a submission under a new guidance.
- **Sponsor clone** — mined from how sponsors historically adapted submission strategy after guidance changes; predicts industry response.

Clone runtime is the **Chat API** (`POST /v1/chat/completions`, OpenAI-compatible) with web grounding, so every prediction cites live FDA sources. Simulation mode feeds one change analysis to all clones and returns side-by-side predictions; batch simulation goes through Task Groups.

## Build phases

- **Phase 0 — Scaffold:** repo layout, `config.py`, stdlib-only `ParallelClient`, this plan, CI-ready layout. (Done in this repo.)
- **Phase 1 — Sense:** `setup_monitors()` registers Monitor webhooks for the four seed FDA sources; `/webhooks/parallel/monitor` receives, verifies (TODO), normalizes, and stores events; `backfill.py` seeds history via Search+Extract.
- **Phase 2 — Understand:** `analyze_change()` (Extract markdown → Task run with schema → poll → parsed analysis), `analyze_batch()` via Task Groups, `KnowledgeGraph` with save/load.
- **Phase 3 — First clone:** mine enforcement behavior patterns from warning letters (most tractable training signal); `Clone.respond_to_change()` wired to Chat API.
- **Phase 4 — Clone fleet:** reviewer + sponsor clones; `run_simulation()` fans out to all three; `run_batch_simulations()` via Task Groups.
- **Phase 5 — Surface:** `maybe_alert()` on severity ≥ 4 (log + stub sender); FastAPI service with webhook/events/analyze/simulate endpoints.

## Tech stack

- Python for ingestion, pipelines, clones; **parallel.ai** for monitoring, retrieval, extraction, deep research, and grounded generation (no separate LLM provider needed — Chat API covers it).
- networkx for the knowledge graph; FastAPI + uvicorn for the service; JSONL files for event storage (swap for a real DB later).
- `src/par_client.py` is stdlib-only (`urllib`) — the only runtime deps are fastapi/uvicorn/networkx/python-dotenv.

## What we build vs. what parallel.ai handles

| Concern | Owner |
|---|---|
| Change monitoring, web search, extraction, deep research, grounded chat | parallel.ai APIs |
| Webhook receiver, event store, Task schemas, knowledge graph, clone profiles/prompts, simulation orchestration, alerting, dashboard | this repo |

## Open decisions

1. Confirm/extend the four seed FDA sources (guidances, warning letters, recalls, Federal Register).
2. Where the service runs (local machine vs. small cloud VM with a public webhook URL).
3. Real alert sender for Phase 5 (email via SMTP, Slack webhook, etc.).
4. `PARALLEL_API_KEY` — placeholder `REPLACE_ME` in `.env.example`; real key to be supplied later.
