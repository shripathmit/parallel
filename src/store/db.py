"""Postgres persistence for parallel -- a schemaless document store.

When the DATABASE_URL env var is set (e.g. Railway's Postgres plugin), the
file-backed stores delegate to ONE schemaless table instead of local JSON
files. When it is unset, everything works exactly as before on files: no
DATABASE_URL, no behavior change.

Why one table and no schema: the feature set is still being finalized, so
every entity is stored as a JSONB document under a namespaced key
("event:{id}", "pattern:{name}", "analysis:{id}", "kg", ...). New fields and
new entity kinds never need migrations -- the app just starts writing new
keys. The table itself is created on first use (create table if not exists),
so there is no manual migration step at all.

Connection notes:
  - psycopg is imported lazily so file mode works without it installed.
  - sslmode=require is enforced (Railway Postgres supports TLS).
  - prepare_threshold=None disables server-side prepared statements: safe
    for transaction poolers, harmless for direct connections.
  - One short-lived connection per operation (autocommit): this app's write
    volume is tiny, and fresh connections can't go stale across deploys.
"""
import os
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

_DOCS_DDL = """
create table if not exists parallel_docs (
  key        text primary key,
  doc        jsonb not null,
  updated_at timestamptz not null default now()
)
"""

_schema_ready = False


def enabled() -> bool:
    """True when Postgres persistence is configured."""
    return bool(DATABASE_URL)


@contextmanager
def connection():
    """Yield a fresh autocommitting psycopg connection, then close it."""
    import psycopg

    dsn = DATABASE_URL
    if "sslmode=" not in dsn:
        dsn += ("&" if "?" in dsn else "?") + "sslmode=require"
    conn = psycopg.connect(dsn, autocommit=True, prepare_threshold=None,
                           row_factory=psycopg.rows.dict_row)
    try:
        yield conn
    finally:
        conn.close()


def ensure_schema():
    """Create parallel_docs if missing. Idempotent; runs once per process."""
    global _schema_ready
    if _schema_ready:
        return
    with connection() as conn, conn.cursor() as cur:
        cur.execute(_DOCS_DDL)
    _schema_ready = True


# ------------------------------------------------------------------ documents
# Writes wrap the dict in psycopg.types.json.Jsonb: psycopg3 cannot adapt a
# bare dict ("cannot adapt type 'dict'"). dict_row returns the jsonb column
# as a dict on reads, so no manual serialization anywhere.


def doc_put(key: str, doc: dict):
    """Upsert one JSON document under key."""
    from psycopg.types.json import Jsonb

    ensure_schema()
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            insert into parallel_docs (key, doc, updated_at)
            values (%s, %s, now())
            on conflict (key) do update
            set doc = excluded.doc, updated_at = now()
            """,
            (key, Jsonb(doc)),
        )


def doc_get(key: str):
    """Return the document dict for key, or None."""
    ensure_schema()
    with connection() as conn, conn.cursor() as cur:
        cur.execute("select doc from parallel_docs where key = %s", (key,))
        row = cur.fetchone()
        return dict(row["doc"]) if row else None


def doc_delete(key: str) -> bool:
    """Delete one document. True when a row was removed."""
    ensure_schema()
    with connection() as conn, conn.cursor() as cur:
        cur.execute("delete from parallel_docs where key = %s", (key,))
        return cur.rowcount > 0


def doc_keys(prefix: str) -> list:
    """All keys starting with prefix."""
    ensure_schema()
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select key from parallel_docs where key like %s", (prefix + "%",)
        )
        return [row["key"] for row in cur.fetchall()]


def doc_list(prefix: str) -> list:
    """All document dicts under prefix."""
    ensure_schema()
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select doc from parallel_docs where key like %s", (prefix + "%",)
        )
        return [dict(row["doc"]) for row in cur.fetchall()]
