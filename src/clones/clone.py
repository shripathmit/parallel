"""A behavior-pattern clone: profile + parallel.ai Chat API runtime."""
import json

from src.par_client import ParallelClient


def _extract_citations(chat_response: dict) -> list:
    """Pull citation URLs out of a Chat API response, defensively."""
    citations = []
    # TODO: verify the grounding/citation shape in docs.parallel.ai
    for key in ("citations", "sources", "basis"):
        for item in chat_response.get(key, []) or []:
            if isinstance(item, str):
                citations.append(item)
            elif isinstance(item, dict) and item.get("url"):
                citations.append(item["url"])
    try:
        message = chat_response["choices"][0]["message"]
        for item in message.get("citations", []) or []:
            if isinstance(item, dict) and item.get("url"):
                citations.append(item["url"])
    except (KeyError, IndexError, TypeError):
        pass
    return list(dict.fromkeys(citations))


def _extract_content(chat_response: dict) -> str:
    try:
        return chat_response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return json.dumps(chat_response)


class Clone:
    def __init__(self, client: ParallelClient, profile: dict):
        self.client = client
        self.profile = profile

    def ask(self, question: str, context: str = "") -> dict:
        """Ask the clone a question with optional context; returns answer + citations."""
        system = (
            self.profile["system_prompt"]
            + "\n\n"
            + self.profile.get("grounding_instructions", "")
        )
        user = f"Context:\n{context}\n\nQuestion: {question}" if context else question
        resp = self.client.chat([{"role": "user", "content": user}], system=system)
        return {
            "clone": self.profile["name"],
            "answer": _extract_content(resp),
            "citations": _extract_citations(resp),
        }

    def respond_to_change(self, change_analysis: dict) -> dict:
        """Predict this stakeholder's behavior in response to an analyzed change."""
        question = (
            "A new FDA regulatory change has been analyzed (details in Context). "
            f"As a {self.profile['role']}, predict how this stakeholder behaves in "
            "response: concrete actions, likely timelines, and what would change your "
            "prediction. End with a confidence level (high/medium/low) and why."
        )
        context = json.dumps(change_analysis, indent=2)[:12000]
        out = self.ask(question, context=context)
        return {
            "clone": self.profile["name"],
            "role": self.profile["role"],
            "prediction": out["answer"],
            "citations": out["citations"],
        }
