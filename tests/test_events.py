"""Unit tests for the Sense layer. No API key or network needed."""
import json
import tempfile
import unittest
from pathlib import Path

from src.sense.events import ChangeEvent, EventStore
from src.sense.webhook import normalize_monitor_payload, verify_signature


class TestEventStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = EventStore(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_and_get(self):
        event = ChangeEvent(source="monitor", url="https://example.com/a", title="A")
        self.store.append(event)
        fetched = self.store.get(event.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "A")
        self.assertEqual(fetched.url, "https://example.com/a")

    def test_list_and_status_filter(self):
        self.store.append(ChangeEvent(source="s1", title="one"))
        self.store.append(ChangeEvent(source="s2", title="two", status="analyzed"))
        self.assertEqual(len(self.store.list()), 2)
        self.assertEqual(len(self.store.list(status="raw")), 1)
        self.assertEqual(self.store.list(status="raw")[0].title, "one")

    def test_mark_processed(self):
        event = self.store.append(ChangeEvent(title="x"))
        self.store.mark_processed(event.id, "analyzed")
        self.assertEqual(self.store.get(event.id).status, "analyzed")

    def test_mark_processed_unknown_id(self):
        with self.assertRaises(KeyError):
            self.store.mark_processed("nope", "analyzed")

    def test_mark_processed_bad_status(self):
        event = self.store.append(ChangeEvent(title="x"))
        with self.assertRaises(ValueError):
            self.store.mark_processed(event.id, "bogus")

    def test_roundtrip_serialization(self):
        event = ChangeEvent(
            source="backfill", title="T", change_type="discovered", raw_diff="diff text"
        )
        restored = ChangeEvent.from_dict(json.loads(json.dumps(event.to_dict())))
        self.assertEqual(restored.to_dict(), event.to_dict())


class TestWebhookNormalization(unittest.TestCase):
    def test_full_payload(self):
        payload = {
            "monitor": {"name": "parallel-fda-guidances"},
            "change": {
                "url": "https://www.fda.gov/guidance-1",
                "title": "New guidance",
                "change_type": "new",
                "diff": "added section 4",
            },
        }
        event = normalize_monitor_payload(payload)
        self.assertEqual(event.source, "parallel-fda-guidances")
        self.assertEqual(event.url, "https://www.fda.gov/guidance-1")
        self.assertEqual(event.title, "New guidance")
        self.assertEqual(event.change_type, "new")
        self.assertEqual(event.raw_diff, "added section 4")
        self.assertEqual(event.status, "raw")

    def test_minimal_payload(self):
        event = normalize_monitor_payload({})
        self.assertIsInstance(event, ChangeEvent)
        self.assertEqual(event.status, "raw")
        self.assertTrue(event.id)

    def test_verify_signature_rejects_empty(self):
        self.assertFalse(verify_signature(b"body", "", ""))
        self.assertFalse(verify_signature(b"body", "abc", ""))


if __name__ == "__main__":
    unittest.main()
