"""Fan a change analysis out to all clones; batch via Task Groups."""
import json

from src.clones.clone import Clone
from src.clones.profiles import ALL_PROFILES
from src.par_client import ParallelClient


def build_clones(client: ParallelClient):
    return [Clone(client, profile) for profile in ALL_PROFILES]


def run_simulation(client: ParallelClient, change_analysis: dict, clones=None) -> dict:
    """Run every clone against one change analysis; return side-by-side predictions."""
    clones = clones if clones is not None else build_clones(client)
    predictions = {}
    for clone in clones:
        name = clone.profile["name"]
        try:
            predictions[name] = clone.respond_to_change(change_analysis)
        except Exception as exc:  # one clone failing must not kill the batch
            predictions[name] = {"clone": name, "error": str(exc)}
    return {
        "change_summary": change_analysis.get("summary", ""),
        "change_type": change_analysis.get("change_type", ""),
        "severity": change_analysis.get("severity"),
        "predictions": predictions,
    }


def _batch_simulation_objective(analysis: dict, stakeholder: str) -> str:
    return (
        f"You are a clone of FDA {stakeholder} behavior. A regulatory change was analyzed:\n"
        f"{json.dumps(analysis, indent=2)[:10000]}\n\n"
        f"Predict how the {stakeholder} stakeholder responds: concrete actions, "
        "timelines, and confidence (high/medium/low) with reasoning."
    )


def run_batch_simulations(client: ParallelClient, analyses: list) -> dict:
    """Batch-simulate many analyses via a single Task Group submission.

    One task per (analysis x stakeholder); the group runs them in parallel.
    """
    tasks = []
    for analysis in analyses:
        for profile in ALL_PROFILES:
            tasks.append(
                {
                    "objective": _batch_simulation_objective(analysis, profile["name"]),
                    # TODO: verify Task Group task field names against docs.parallel.ai
                }
            )
    return client.task_group(tasks)
