-- ============================================================================
-- PARKED 2026-09-20: the 8-table relational schema below is NOT used.
-- parallel now persists to ONE schemaless table (parallel_docs, created
-- automatically by the app on first use), so unfinished features never need
-- migrations. Kept here for reference only -- do NOT run this.
-- ============================================================================
--
-- parallel: persistent storage for the FDA change-intelligence pipeline.
--
-- Run this once in the Supabase SQL editor of the dedicated parallel project:
--   https://uvmdawkhmptzoqvmkcgi.supabase.co
-- It replaces the ephemeral JSON files under DATA_DIR (/app/data) on Railway.
--
-- Tables are server-side only: RLS is enabled with NO policies, so only the
-- service_role / postgres roles (which bypass RLS) can touch them. The public
-- anon key gets nothing through PostgREST.

-- ---------------------------------------------------------------- events
create table if not exists parallel_events (
  id          text primary key,
  source      text        not null default '',
  url         text        not null default '',
  title       text        not null default '',
  detected_at timestamptz not null default now(),
  change_type text        not null default 'unknown',
  raw_diff    text        not null default '',
  status      text        not null default 'raw',
  demo        boolean     not null default false,
  created_at  timestamptz not null default now()
);
create index if not exists parallel_events_status_idx   on parallel_events (status);
create index if not exists parallel_events_detected_idx on parallel_events (detected_at desc);

-- ------------------------------------------------- analyses / simulations
create table if not exists parallel_analyses (
  event_id   text primary key references parallel_events (id) on delete cascade,
  payload    jsonb      not null,
  updated_at timestamptz not null default now()
);

create table if not exists parallel_simulations (
  event_id   text primary key references parallel_events (id) on delete cascade,
  payload    jsonb      not null,
  updated_at timestamptz not null default now()
);

-- ------------------------------------------------------- demo payloads
-- Canned demo analysis/simulation payloads, materialized into the tables
-- above only when the user clicks through the demo flow.
create table if not exists parallel_demo_payloads (
  event_id text  not null,
  kind     text  not null check (kind in ('analysis', 'simulation')),
  payload  jsonb not null,
  primary key (event_id, kind)
);

-- --------------------------------------------------------------- patterns
create table if not exists parallel_patterns (
  name               text primary key,
  stakeholder        text             not null,
  triggers           jsonb            not null default '[]',
  description        text             not null default '',
  typical_actions    jsonb            not null default '[]',
  evidence_citations jsonb            not null default '[]',
  confidence         double precision not null default 0.5,
  support            integer          not null default 0,
  demo               boolean          not null default false,
  version            integer          not null default 1
);
create index if not exists parallel_patterns_stakeholder_idx on parallel_patterns (stakeholder);

-- ------------------------------------------------------- knowledge graph
create table if not exists parallel_kg_nodes (
  node_id text  primary key,
  attrs   jsonb not null default '{}'
);

create table if not exists parallel_kg_edges (
  src   text not null,
  dst   text not null,
  attrs jsonb not null default '{}',
  primary key (src, dst)
);

-- ----------------------------------------------------------------- alerts
create table if not exists parallel_alerts (
  id         bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  severity   integer     not null,
  message    text        not null
);

-- ------------------------------------------------- lock down to server role
alter table parallel_events        enable row level security;
alter table parallel_analyses      enable row level security;
alter table parallel_simulations   enable row level security;
alter table parallel_demo_payloads enable row level security;
alter table parallel_patterns      enable row level security;
alter table parallel_kg_nodes      enable row level security;
alter table parallel_kg_edges      enable row level security;
alter table parallel_alerts        enable row level security;
-- No policies created: only service_role / postgres (RLS-bypass roles) can
-- read or write. The app connects with the database password, so it bypasses
-- RLS; the public anon key is denied everything.
