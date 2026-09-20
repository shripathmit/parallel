"""DB-path tests for the schemaless Postgres document store.

No live database needed. A fake psycopg module (one in-memory dict standing
in for the parallel_docs table) exercises every DATABASE_URL code path:
events, patterns, artifacts, knowledge graph, and alerts. The fake raises on
any SQL it doesn't recognize, so new queries can't slip past the tests.
"""
import sys
import types
import unittest
from unittest import mock

from src.store import db as _db


# ---------------------------------------------------------------- fake driver


class FakeCursor:
    """Emulates the parallel_docs table: {key: doc}."""

    def __init__(self, state):
        self.s = state
        self._rows = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        q = " ".join(sql.split()).lower()
        p = tuple(params or ())
        docs = self.s["docs"]
        self._rows = []
        self.rowcount = 0

        if q.startswith("create table"):
            return  # ensure_schema: idempotent no-op
        if q.startswith("insert into parallel_docs"):
            val = p[1]
            # Real psycopg3 cannot adapt a bare dict ("cannot adapt type
            # 'dict'"); the app must wrap it in Jsonb. Mirror that here so
            # the tests catch a missing wrapper.
            if isinstance(val, dict):
                raise AssertionError(
                    "fake driver: bare dict passed to doc_put; "
                    "real psycopg3 requires psycopg.types.json.Jsonb"
                )
            val = val.obj if hasattr(val, "obj") else val  # unwrap Jsonb
            docs[p[0]] = dict(val)  # upsert, like ON CONFLICT DO UPDATE
            self.rowcount = 1
        elif q == "select doc from parallel_docs where key = %s":
            if p[0] in docs:
                self._rows = [{"doc": dict(docs[p[0]])}]
        elif q == "select key from parallel_docs where key like %s":
            prefix = p[0][:-1]  # trailing "%"
            self._rows = [{"key": k} for k in docs if k.startswith(prefix)]
        elif q == "select doc from parallel_docs where key like %s":
            prefix = p[0][:-1]
            self._rows = [{"doc": dict(docs[k])} for k in docs if k.startswith(prefix)]
        elif q == "delete from parallel_docs where key = %s":
            if p[0] in docs:
                del docs[p[0]]
                self.rowcount = 1
        else:
            raise AssertionError(f"fake driver: unhandled SQL: {sql!r}")

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    def __init__(self, state):
        self.s = state

    def cursor(self):
        return FakeCursor(self.s)

    def close(self):
        pass


def _install_fake():
    state = {"docs": {}}
    fake = types.ModuleType("psycopg")
    fake.__path__ = []
    fake.connect = lambda *a, **k: FakeConn(state)
    fake.rows = types.SimpleNamespace(dict_row="dict_row")

    class Jsonb:
        """Stand-in for psycopg.types.json.Jsonb: wraps the dict in .obj."""

        def __init__(self, obj):
            self.obj = obj

    fake_types = types.ModuleType("psycopg.types")
    fake_types.__path__ = []
    fake_json = types.ModuleType("psycopg.types.json")
    fake_json.Jsonb = Jsonb
    fake.types = fake_types
    fake_types.json = fake_json
    patcher = mock.patch.dict(
        sys.modules,
        {"psycopg": fake, "psycopg.types": fake_types, "psycopg.types.json": fake_json},
    )
    return state, patcher


# ------------------------------------------------------------------- tests


class DbStoresTest(unittest.TestCase):
    def setUp(self):
        self.state, self._patcher = _install_fake()
        self._patcher.start()
        self._url = mock.patch.object(_db, "DATABASE_URL", "postgresql://fake/db")
        self._url.start()
        _db._schema_ready = False
        self.addCleanup(self._patcher.stop)
        self.addCleanup(self._url.stop)

    # schema ---------------------------------------------------------
    def test_ensure_schema_idempotent(self):
        _db.ensure_schema()
        _db.ensure_schema()  # second call is a no-op (per-process flag)
        self.assertTrue(_db._schema_ready)

    # events ---------------------------------------------------------
    def test_events_roundtrip(self):
        from src.sense.events import ChangeEvent, EventStore

        store = EventStore("/tmp/ignored")
        self.assertTrue(store.use_db)
        e = store.append(ChangeEvent(title="T", url="https://x", source="s"))
        self.assertEqual(store.get(e.id).title, "T")
        self.assertEqual(len(store.list()), 1)
        self.assertEqual(len(store.list(status="raw")), 1)
        store.mark_processed(e.id, "analyzed")
        self.assertEqual(store.get(e.id).status, "analyzed")
        self.assertEqual(store.list(status="raw"), [])
        with self.assertRaises(KeyError):
            store.mark_processed("missing", "analyzed")
        with self.assertRaises(ValueError):
            store.mark_processed(e.id, "bogus")
        # re-append upserts instead of duplicating
        store.append(e)
        self.assertEqual(len(store.list()), 1)
        self.assertIsNone(store.get("missing"))

    def test_events_list_order(self):
        from src.sense.events import ChangeEvent, EventStore

        store = EventStore("/tmp/ignored")
        store.append(ChangeEvent(id="b", detected_at="2026-09-02T00:00:00+00:00"))
        store.append(ChangeEvent(id="a", detected_at="2026-09-01T00:00:00+00:00"))
        self.assertEqual([e.id for e in store.list()], ["a", "b"])

    # patterns -------------------------------------------------------
    def test_patterns_roundtrip(self):
        from src.clones.patterns import Pattern, PatternStore

        store = PatternStore("/tmp/ignored")
        p = Pattern(name="p1", stakeholder="enforcement", triggers=["a", "b"],
                    typical_actions=["x"], evidence_citations=["u"],
                    confidence=0.9, support=3, demo=True)
        store.add(p)
        got = store.list()[0]
        self.assertEqual(got.name, "p1")
        self.assertEqual(got.triggers, ["a", "b"])
        self.assertEqual(got.confidence, 0.9)
        self.assertEqual(store.list(stakeholder="reviewer"), [])
        # add() upserts by name
        store.add(Pattern(name="p1", stakeholder="sponsor"))
        self.assertEqual(store.list()[0].stakeholder, "sponsor")
        self.assertEqual(store.clear_demo(), 0)  # demo flag was replaced
        store.add(Pattern(name="p2", stakeholder="sponsor", demo=True))
        self.assertEqual(store.clear_demo(), 1)
        self.assertEqual(len(store.list()), 1)

    # artifacts ------------------------------------------------------
    def test_artifacts_roundtrip(self):
        from src.store import artifacts

        self.assertIsNone(artifacts.load_analysis("/tmp/x", "nope"))
        artifacts.save_analysis("/tmp/x", "e1", {"severity": 5})
        self.assertEqual(artifacts.load_analysis("/tmp/x", "e1")["severity"], 5)
        artifacts.save_simulation("/tmp/x", "e1", {"predictions": {}})
        self.assertEqual(artifacts.load_simulation("/tmp/x", "e1"), {"predictions": {}})
        artifacts.save_demo_payload("/tmp/x", "e1", "analysis", {"demo": True})
        self.assertTrue(artifacts.load_demo_payload("/tmp/x", "e1", "analysis")["demo"])
        self.assertIsNone(artifacts.load_demo_payload("/tmp/x", "e1", "simulation"))
        with self.assertRaises(ValueError):
            artifacts.save_demo_payload("/tmp/x", "e1", "bogus", {})

    # knowledge graph -----------------------------------------------
    def test_kg_roundtrip(self):
        from src.sense.events import ChangeEvent
        from src.understand.knowledge_graph import KnowledgeGraph

        kg = KnowledgeGraph()
        event = ChangeEvent(id="e1", title="T", url="u", source="s")
        kg.add_analysis(event, {"severity": 4, "change_type": "new",
                                "affected_product_codes": ["DXY"],
                                "affected_submission_types": [],
                                "citations": ["cite1"]})
        kg.save_db()
        kg2 = KnowledgeGraph.load_db()
        self.assertIn("change:e1", kg2.graph.nodes)
        self.assertIn("product:DXY", kg2.graph.nodes)
        self.assertEqual(kg2.graph.nodes["change:e1"]["severity"], 4)
        self.assertEqual(len(kg2.impacts_of("DXY")), 1)
        # missing doc -> empty graph, no crash
        _db.doc_delete("kg")
        self.assertEqual(len(KnowledgeGraph.load_db().graph.nodes), 0)

    # alerts ----------------------------------------------------------
    def test_alert_logged(self):
        from src.surface import alerts

        out = alerts.maybe_alert({"severity": 5, "summary": "boom"},
                                 types.SimpleNamespace(data_dir="/tmp/x"))
        self.assertTrue(out["alerted"])
        keys = _db.doc_keys("alert:")
        self.assertEqual(len(keys), 1)
        self.assertEqual(_db.doc_get(keys[0])["severity"], 5)
        out = alerts.maybe_alert({"severity": 2},
                                 types.SimpleNamespace(data_dir="/tmp/x"))
        self.assertFalse(out["alerted"])
        self.assertEqual(len(_db.doc_keys("alert:")), 1)


if __name__ == "__main__":
    unittest.main()
