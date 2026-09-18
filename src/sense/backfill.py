"""Seed the event store with historical FDA changes via Search + Extract."""
import argparse

from config import load_settings
from src.par_client import ParallelClient, ParallelAPIError
from src.sense.events import ChangeEvent, EventStore


def backfill(client: ParallelClient, store: EventStore, query: str, max_results: int = 20):
    """Discover historical changes for a query and store them as raw events."""
    resp = client.search(
        objective=(
            f"Find FDA regulatory changes related to: {query}. "
            "Prefer fda.gov and federalregister.gov sources."
        ),
        search_queries=[
            f"FDA {query}",
            f"FDA guidance {query}",
            f"FDA warning letter {query}",
        ],
        max_results=max_results,
    )
    results = resp.get("results", []) or []
    events = []
    for result in results:
        url = result.get("url", "")
        title = result.get("title", "Untitled")
        content = ""
        if url:
            try:
                doc = client.extract(url, objective=f"Extract the regulatory change: {query}")
                content = doc.get("markdown", doc.get("content", "")) or ""
            except ParallelAPIError:
                content = ""
        event = ChangeEvent(
            source="backfill",
            url=url,
            title=title,
            change_type="discovered",
            raw_diff=content[:8000],
            status="raw",
        )
        store.append(event)
        events.append(event)
    return events


def main():
    parser = argparse.ArgumentParser(description="Backfill historical FDA change events.")
    parser.add_argument("query", help="Topic to backfill, e.g. 'AI/ML medical device guidance'")
    parser.add_argument("--max-results", type=int, default=20)
    args = parser.parse_args()

    settings = load_settings()
    events = backfill(ParallelClient(), EventStore(settings.data_dir), args.query, args.max_results)
    print(f"Stored {len(events)} events.")


if __name__ == "__main__":
    main()
