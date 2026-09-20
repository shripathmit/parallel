"""Postgres (Supabase) connection helper for parallel.

When the DATABASE_URL env var is set, the file-backed stores delegate to
Postgres. When it is unset, everything keeps working exactly as before on
local JSON files -- no DATABASE_URL, no behavior change.

Connection notes:
  - psycopg is imported lazily so file mode works without it installed.
  - sslmode=require is enforced (Supabase mandates TLS).
  - prepare_threshold=None disables server-side prepared statements, which
    Supavisor's transaction pooling mode cannot hold across checkouts.
  - One short-lived connection per operation (autocommit): this app's write
    volume is tiny, and fresh connections can't go stale across deploys.
"""
import os
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


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
