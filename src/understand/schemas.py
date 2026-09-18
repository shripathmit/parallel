"""Structured output schemas for the parallel.ai Task API."""
CHANGE_ANALYSIS_SCHEMA = {
    "type": "object",
    "required": ["change_type", "summary", "severity", "confidence"],
    "properties": {
        "change_type": {
            "type": "string",
            "enum": [
                "new_requirement",
                "tightened",
                "relaxed",
                "clarification",
                "enforcement_shift",
            ],
            "description": "How the regulatory posture changed.",
        },
        "summary": {
            "type": "string",
            "description": "Plain-language summary of what changed and why it matters.",
        },
        "affected_product_codes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "FDA product codes touched by this change (e.g. 'QIH').",
        },
        "affected_submission_types": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Submission pathways affected (e.g. '510(k)', 'PMA', 'De Novo', 'EUA').",
        },
        "severity": {
            "type": "integer",
            "enum": [1, 2, 3, 4, 5],
            "description": "1 = informational, 5 = business-critical compliance impact.",
        },
        "citations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "URLs or document references supporting each claim.",
        },
        "confidence": {
            "type": "number",
            "description": "Model confidence in the analysis, 0 to 1.",
        },
    },
}

BEHAVIOR_PATTERN_SCHEMA = {
    "type": "object",
    "required": ["pattern_name", "stakeholder", "description", "confidence"],
    "properties": {
        "pattern_name": {
            "type": "string",
            "description": "Short name for the recurring behavior pattern.",
        },
        "stakeholder": {
            "type": "string",
            "enum": ["enforcement", "reviewer", "sponsor"],
            "description": "Whose behavior this pattern describes.",
        },
        "description": {
            "type": "string",
            "description": "What the stakeholder repeatedly does, and under what trigger conditions.",
        },
        "evidence_citations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "URLs of the FDA records this pattern was distilled from.",
        },
        "confidence": {
            "type": "number",
            "description": "Confidence in this pattern, 0 to 1.",
        },
    },
}
