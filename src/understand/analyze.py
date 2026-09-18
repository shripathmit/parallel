"""Analyze change events with the parallel.ai Task API."""
from src.par_client import ParallelClient
from src.sense.events import ChangeEvent
from src.understand.schemas import CHANGE_ANALYSIS_SCHEMA


def _analysis_objective(event: ChangeEvent, content: str) -> str:
    return (
        "You are an FDA regulatory analyst. Analyze the following regulatory change.\n"
        f"Source: {event.source}\n"
        f"URL: {event.url}\n"
        f"Title: {event.title}\n\n"
        f"Content:\n{content}\n\n"
        "Classify the change, summarize its practical impact, list affected FDA product "
        "codes and submission types, score severity 1-5, and cite your sources."
    )


def analyze_change(client: ParallelClient, event: ChangeEvent, poll: bool = True) -> dict:
    """Run a Task analysis for one event; poll to completion and return the analysis."""
    content = event.raw_diff
    if not content and event.url:
        doc = client.extract(
            event.url,
            objective="Extract the full regulatory content: requirements, dates, scope.",
        )
        content = doc.get("markdown", doc.get("content", "")) or ""
    content = content[:30000]

    run = client.task_run(
        objective=_analysis_objective(event, content),
        output_schema=CHANGE_ANALYSIS_SCHEMA,
    )
    run_id = run.get("run_id", run.get("id"))
    if not poll:
        return {"run_id": run_id, "status": "submitted"}
    output = client.wait_for_task(run_id)
    if isinstance(output, dict):
        return output
    return {"raw_output": output}


def analyze_batch(client: ParallelClient, events: list) -> dict:
    """Submit one Task per event as a Task Group for batch processing."""
    tasks = []
    for event in events:
        content = (event.raw_diff or "")[:30000]
        tasks.append(
            {
                "objective": _analysis_objective(event, content),
                "output_schema": CHANGE_ANALYSIS_SCHEMA,
                # TODO: verify Task Group task field names against docs.parallel.ai
            }
        )
    return client.task_group(tasks)
