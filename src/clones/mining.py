"""Mine behavior patterns from FDA records to build/refresh clone profiles."""
import json

from src.par_client import ParallelClient
from src.understand.schemas import BEHAVIOR_PATTERN_SCHEMA

SEED_QUERIES = {
    "enforcement": "FDA warning letters medical device violations and enforcement patterns",
    "reviewer": "FDA 510(k) deficiency letters and reviewer questions for medical devices",
    "sponsor": "how medical device companies adapted submission strategy after FDA guidance changes",
}


def mine_patterns(
    client: ParallelClient,
    stakeholder: str,
    seed_query: str = None,
    max_entities: int = 25,
) -> list:
    """Use FindAll + Task to distill behavior patterns for one stakeholder.

    Returns a list of pattern dicts matching BEHAVIOR_PATTERN_SCHEMA.
    """
    query = seed_query or SEED_QUERIES[stakeholder]
    found = client.findall(
        objective=f"Find FDA records showing {stakeholder} behavior patterns: {query}",
        criteria={"stakeholder": stakeholder, "topic": query, "max_entities": max_entities},
    )
    entities = found.get("entities", found.get("results", [])) or []
    if not entities:
        return []

    run = client.task_run(
        objective=(
            f"Distill recurring {stakeholder} behavior patterns from these FDA records. "
            "Each pattern needs a name, the trigger conditions, and evidence citations.\n\n"
            f"Records:\n{json.dumps(entities)[:15000]}"
        ),
        output_schema={
            "type": "object",
            "required": ["patterns"],
            "properties": {
                "patterns": {"type": "array", "items": BEHAVIOR_PATTERN_SCHEMA},
            },
        },
    )
    run_id = run.get("run_id", run.get("id"))
    output = client.wait_for_task(run_id)
    if isinstance(output, dict):
        return output.get("patterns", [])
    return []
