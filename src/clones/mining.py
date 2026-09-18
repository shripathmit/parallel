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


def mine_and_store(client: ParallelClient, data_dir: str, stakeholder: str) -> list:
    """Mine patterns for one stakeholder and persist them to the PatternStore.

    This closes the loop: FindAll + Task distill patterns -> stored as evidence
    -> match_patterns fires them -> clones reason from them.
    """
    from src.clones.patterns import Pattern, PatternStore

    mined = mine_patterns(client, stakeholder)
    store = PatternStore(data_dir)
    stored = []
    for m in mined:
        pattern = Pattern(
            name=m.get("pattern_name", f"{stakeholder}-pattern"),
            stakeholder=m.get("stakeholder", stakeholder),
            triggers=[],  # triggers are curated when a human reviews the pattern
            description=m.get("description", ""),
            typical_actions=[],
            evidence_citations=m.get("evidence_citations", []),
            confidence=float(m.get("confidence", 0.5)),
            support=1,
            demo=False,
        )
        store.add(pattern)
        stored.append(pattern)
    return stored
