"""DB-path tests for the Postgres stores. No live database needed.

A fake psycopg module (in-memory dicts) stands in for the real driver so we
can exercise every DATABASE_URL code path: branching, parameter order,
row mapping, and upsert/conflict semantics. SQL syntax itself is validated
separately with pglast (see scripts/check_sql.py usage in CI notes).
"""
import sys
import types
import unittest
from unittest import mock

from src.store import db as _db


# ---------------------------------------------------------------- fake driver


class FakeCursor:
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
        s = self.s
        self._rows = []
        self.rowcount = 0

        if q.startswith("insert into parallel_events"):
            eid = p[0]
            if eid not in s["events"]:
                s["events"][eid] = {
                    "id": p[0], "source": p[1], "url": p[2], "title": p[3],
                    "detected_at": p[4], "change_type": p[5], "raw_diff": p[6],
                    "status": p[7], "demo": p[8],
                }
                self.rowcount = 1
        elif "from parallel_events" in q and q.startswith("select"):
            rows = sorted(s["events"].values(), key=lambda r: r["detected_at"])
            if "where status =" in q:
                rows = [r for r in rows if r["status"] == p[0]]
            elif "where id =" in q:
                rows = [r for r in rows if r["id"] == p[0]]
            self._rows = rows
        elif q.startswith("update parallel_events"):
            eid = p[1]
            if eid in s["events"]:
                s["events"][eid]["status"] = p[0]
                self.rowcount = 1
        elif q.startswith("insert into parallel_analyses") or q.startswith(
            "insert into parallel_simulations"
        ):
            table = "analyses" if "parallel_analyses" in q else "simulations"
            s[table][p[0]] = p[1]
            self.rowcount = 1
        elif "from parallel_analyses" in q or "from parallel_simulations" in q:
            table = "analyses" if "parallel_analyses" in q else "simulations"
            if p[0] in s[table]:
                self._rows = [{"payload": s[table][p[0]]}]
        elif q.startswith("insert into parallel_demo_payloads"):
            s["demo_payloads"][(p[0], p[1])] = p[2]
            self.rowcount = 1
        elif "from parallel_demo_payloads" in q:
            key = (p[0], p[1])
            if key in s["demo_payloads"]:
                self._rows = [{"payload": s["demo_payloads"][key]}]
        elif q.startswith("insert into parallel_patterns"):
            name = p[0]
            s["patterns"][name] = {
                "name": p[0], "stakeholder": p[1], "triggers": p[2],
                "description": p[3], "typical_actions": p[4],
                "evidence_citations": p[5], "confidence": p[6],
                "support": p[7], "demo": p[8], "version": p[9],
            }
            self.rowcount = 1
        elif "from parallel_patterns" in q and q.startswith("select"):
            rows = sorted(s["patterns"].values(), key=lambda r: r["name"])
            if "where stakeholder =" in q:
                rows = [r for r in rows if r["stakeholder"] == p[0]]
            self._rows = rows
        elif q.startswith("delete from parallel_patterns"):
            before = len(s["patterns"])
            s["patterns"] = {k: v for k, v in s["patterns"].items() if not v["demo"]}
            self.rowcount = before - len(s["patterns"])
        elif q.startswith("delete from parallel_kg_"):
            if "parallel_kg_edges" in q:
                s["kg_edges"] = []
            else:
                s["kg_nodes"] = {}
        elif q.startswith("insert into parallel_kg_nodes"):
            s["kg_nodes"][p[0]] = p[1]
        elif q.startswith("insert into parallel_kg_edges"):
            s["kg_edges"].append((p[0], p[1], p[2]))
        elif q.startswith("select node_id"):
            self._rows = [
                {"node_id": k, "attrs": v} for k, v in s["kg_nodes"].items()
            ]
        elif q.startswith("select src, dst"):
            self._rows = [
                {"src": a, "dst": b, "attrs": c} for a, b, c in s["kg_edges"]
            ]
        elif q.startswith("insert into parallel_alerts"):
            s["alerts"].append({"severity": p[0], "message": p[1]})
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

    def transaction(self):
        return self.cursor()  # atomicity is a no-op in the fake

    def close(self):
        pass


def _blank_state():
    return {
        "events": {}, "analyses": {}, "simulations": {}, "demo_payloads": {},
        "patterns": {}, "kg_nodes": {}, "kg_edges": [], "alerts": [],
    }


def _install_fake():
    state = _blank_state()
    fake = types.ModuleType("psycopg")
    fake.__path__ = []  # mark as a package so submodule imports resolve
    fake.connect = lambda *a, **k: FakeConn(state)
    fake.rows = types.SimpleNamespace(dict_row="dict_row")
    types_mod = types.ModuleType("psycopg.types")
    types_mod.__path__ = []
    json_mod = types.ModuleType("psycopg.types.json")
    json_mod.Json = lambda v: v
    types_mod.json = json_mod
    fake.types = types_mod
    return state, mock.patch.dict(
        sys.modules,
        {"psycopg": fake, "psycopg.types": types_mod, "psycopg.types.json": json_mod},
    )


# ------------------------------------------------------------------- tests


class DbStoresTest(unittest.TestCase):
    def setUp(self):
        self.state, self._patcher = _install_fake()
        self._patcher.start()
        self._url = mock.patch.object(_db, "DATABASE_URL", "postgresql://fake/db")
        self._url.start()
        self.addCleanup(self._patcher.stop)
        self.addCleanup(self._url.stop)

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
        # append is idempotent on conflict
        store.append(e)
        self.assertEqual(len(store.list()), 1)

    def test_row_to_event_datetime(self):
        from datetime import datetime, timezone
        from src.sense.events import _row_to_event

        row = {
            "id": "a", "source": "s", "url": "u", "title": "t",
            "detected_at": datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc),
            "change_type": "new", "raw_diff": "", "status": "raw", "demo": False,
        }
        self.assertEqual(_row_to_event(row).detected_at, "2026-01-02T03:04:00+00:00")

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
        # empty db -> empty graph, no crash
        self.state["kg_nodes"] = {}
        self.state["kg_edges"] = []
        self.assertEqual(len(KnowledgeGraph.load_db().graph.nodes), 0)

    # alerts ----------------------------------------------------------
    def test_alert_logged(self):
        from src.surface import alerts

        out = alerts.maybe_alert({"severity": 5, "summary": "boom"}, types.SimpleNamespace(data_dir="/tmp/x"))
        self.assertTrue(out["alerted"])
        self.assertEqual(self.state["alerts"][0]["severity"], 5)
        out = alerts.maybe_alert({"severity": 2}, types.SimpleNamespace(data_dir="/tmp/x"))
        self.assertFalse(out["alerted"])
        self.assertEqual(len(self.state["alerts"]), 1)


if __name__ == "__main__":
    unittest.main()
