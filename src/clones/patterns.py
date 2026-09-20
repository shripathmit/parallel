"""Behavior-pattern library: the evidence base behind the clones.

A pattern is a distilled, reusable observation of how one stakeholder behaves:
what triggers it, what they typically do, and the FDA records that prove it.

Patterns come from two places:
  1. Mined live via src/clones/mining.py (FindAll + Task) -> PatternStore.add
  2. Seeded demo patterns (seed_demo_patterns) distilled from real FDA
     publications, labeled demo=True.

The matching algorithm (match_patterns) is deterministic and explainable:
score = trigger_coverage x pattern_confidence, no API call needed.
"""
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.store import db as _db


@dataclass
class Pattern:
    name: str
    stakeholder: str  # enforcement | reviewer | sponsor
    triggers: list = field(default_factory=list)  # keywords/phrases that fire it
    description: str = ""
    typical_actions: list = field(default_factory=list)
    evidence_citations: list = field(default_factory=list)
    confidence: float = 0.5  # 0..1, from mining support / curator judgment
    support: int = 0  # number of FDA records behind the pattern
    demo: bool = False
    version: int = 1


_PATTERN_PREFIX = "pattern:"


def _pattern_key(name: str) -> str:
    return f"{_PATTERN_PREFIX}{name}"


class PatternStore:
    """Pattern store: Postgres documents when DATABASE_URL is set, otherwise
    the original data/patterns.json file. Same interface either way."""

    def __init__(self, data_dir):
        self.data_dir = str(data_dir)
        self.use_db = _db.enabled()
        if not self.use_db:
            self.path = Path(data_dir) / "patterns.json"
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self.path.write_text("[]", encoding="utf-8")

    def list(self, stakeholder: str = None) -> list:
        if self.use_db:
            patterns = [Pattern(**d) for d in _db.doc_list(_PATTERN_PREFIX)]
            patterns.sort(key=lambda p: p.name)
            if stakeholder:
                patterns = [p for p in patterns if p.stakeholder == stakeholder]
            return patterns
        patterns = [Pattern(**d) for d in json.loads(self.path.read_text(encoding="utf-8"))]
        if stakeholder:
            patterns = [p for p in patterns if p.stakeholder == stakeholder]
        return patterns

    def add(self, pattern: "Pattern"):
        if self.use_db:
            _db.doc_put(_pattern_key(pattern.name), asdict(pattern))
            return
        patterns = self.list()
        patterns = [p for p in patterns if p.name != pattern.name] + [pattern]
        self.path.write_text(
            json.dumps([asdict(p) for p in patterns], indent=2), encoding="utf-8"
        )

    def clear_demo(self) -> int:
        if self.use_db:
            n = 0
            for key in _db.doc_keys(_PATTERN_PREFIX):
                doc = _db.doc_get(key)
                if doc and doc.get("demo"):
                    _db.doc_delete(key)
                    n += 1
            return n
        patterns = [p for p in self.list() if not p.demo]
        n = len(self.list()) - len(patterns)
        self.path.write_text(
            json.dumps([asdict(p) for p in patterns], indent=2), encoding="utf-8"
        )
        return n


def _analysis_text(analysis: dict) -> str:
    parts = [
        analysis.get("summary", ""),
        analysis.get("change_type", ""),
        " ".join(analysis.get("affected_product_codes", []) or []),
        " ".join(analysis.get("affected_submission_types", []) or []),
    ]
    return " ".join(parts).lower()


def match_patterns(
    analysis: dict, patterns: list, stakeholder: str, top_k: int = 3
) -> list:
    """Score patterns for one stakeholder against an analysis.

    score = (matched_triggers / total_triggers) * pattern.confidence
    Returns [(pattern, score, matched_triggers)] sorted best-first.
    """
    text = _analysis_text(analysis)
    scored = []
    for p in patterns:
        if p.stakeholder != stakeholder or not p.triggers:
            continue
        matched = [t for t in p.triggers if t.lower() in text]
        if not matched:
            continue
        coverage = len(matched) / len(p.triggers)
        score = coverage * p.confidence
        scored.append((p, round(score, 3), matched))
    scored.sort(key=lambda s: s[1], reverse=True)
    return scored[:top_k]


def seed_demo_patterns() -> list:
    """Demo patterns distilled from the real FDA records used in the seed.

    Titles/URLs/dates of the evidence are real; the distillation is illustrative.
    """
    return [
        Pattern(
            name="inspection-refusal-escalation",
            stakeholder="enforcement",
            triggers=["501(j)", "refused inspection", "denied inspection", "delayed inspection", "refusal"],
            description=(
                "When a firm delays, denies, or refuses FDA inspection, CDER deems the drugs "
                "adulterated under 501(j) and escalates faster toward import alert or injunction "
                "than for CGMP findings alone."
            ),
            typical_actions=[
                "Follow-up inspection scheduled to verify correction",
                "Import alert or injunction evaluation within 6 months",
                "State boards notified of the federal action",
            ],
            evidence_citations=[
                "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/new-life-pharma-llc-725661-04142026",
            ],
            confidence=0.9,
            support=12,
            demo=True,
        ),
        Pattern(
            name="cdmo-warning-letter-cluster",
            stakeholder="enforcement",
            triggers=["cdmo", "contract manufacturer", "jabil", "pharmaceutics"],
            description=(
                "Warning letters to large contract manufacturers arrive in clusters as CDER signals "
                "sector-wide expectations, and trigger sponsor audit waves plus heightened reviewer "
                "scrutiny of client submissions naming the CDMO."
            ),
            typical_actions=[
                "Follow-up inspections prioritized across top CDMOs by volume",
                "Further warning letters citing data-integrity and aseptic controls",
            ],
            evidence_citations=[
                "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/jabil-inc-731037-08272026",
            ],
            confidence=0.75,
            support=8,
            demo=True,
        ),
        Pattern(
            name="glp1-compounding-crackdown",
            stakeholder="enforcement",
            triggers=["semaglutide", "tirzepatide", "compounding", "unapproved", "misbranded"],
            description=(
                "CDER runs sustained enforcement initiatives against unapproved GLP-1 copies; "
                "compounding marketed as alternatives to approved drugs draws warning letters that "
                "combine 505(a), 502(o), and 501(a)(2)(B) findings."
            ),
            typical_actions=[
                "Coordinated warning-letter wave across compounders",
                "501(j) findings accelerate cases toward injunction",
            ],
            evidence_citations=[
                "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/new-life-pharma-llc-725661-04142026",
            ],
            confidence=0.85,
            support=15,
            demo=True,
        ),
        Pattern(
            name="class1-recall-scrutiny",
            stakeholder="reviewer",
            triggers=["class i", "class 1", "recall"],
            description=(
                "After a Class I recall, reviewers add targeted questions on the failure mode to every "
                "pending submission in the same product code and challenge predicate comparisons to the "
                "recalled device."
            ),
            typical_actions=[
                "Deficiency letters request worst-case bench testing of the failure mode",
                "Predicate comparisons to the recalled device challenged",
                "Human-factors review of related instructions intensifies",
            ],
            evidence_citations=[
                "https://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/percutaneous-catheter-recall-boston-scientific-removes-enroute-transcarotid-neuroprotection-system",
                "http://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/infusion-pump-recall-fresenius-kabi-removes-ivenix-large-volume-pumps",
            ],
            confidence=0.88,
            support=22,
            demo=True,
        ),
        Pattern(
            name="cyber-device-rta",
            stakeholder="reviewer",
            triggers=["cybersecurity", "sbom", "524b", "cyber device", "vulnerability"],
            description=(
                "Final cybersecurity guidance becomes refuse-to-accept checklist items: SBOM, "
                "vulnerability remediation plans, and patchability labeling for cyber devices."
            ),
            typical_actions=[
                "RTA checklist updated with cybersecurity documentation items",
                "Deficiency letters cite guidance sections by page and line",
                "eSTAR templates gain mandatory cybersecurity annex fields",
            ],
            evidence_citations=[
                "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/cybersecurity-medical-devices-quality-management-system-considerations-and-content-premarket",
            ],
            confidence=0.9,
            support=10,
            demo=True,
        ),
        Pattern(
            name="software-alarm-depth",
            stakeholder="reviewer",
            triggers=["infusion pump", "software", "alarm"],
            description=(
                "Infusion-pump submissions face deep software hazard-analysis and human-factors "
                "questioning after pump recalls, even when the recall reported no injuries."
            ),
            typical_actions=[
                "Deficiency letters probe software hazard analysis and alarm-fatigue mitigations",
                "Human-factors validation expectations rise for pump user interfaces",
            ],
            evidence_citations=[
                "http://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/infusion-pump-recall-fresenius-kabi-removes-ivenix-large-volume-pumps",
            ],
            confidence=0.82,
            support=14,
            demo=True,
        ),
        Pattern(
            name="recall-playbook-execution",
            stakeholder="sponsor",
            triggers=["recall", "field correction", "field action", "consignees"],
            description=(
                "Large strategics execute Class I recalls as rehearsed operations: customer "
                "notification, field correction, and CAPA within one quarter; commercial impact "
                "concentrates in the affected product line while competitors quietly differentiate."
            ),
            typical_actions=[
                "Customer notifications and field correction within weeks",
                "CAPA filed; hospitals review inventory and may pause new orders",
            ],
            evidence_citations=[
                "https://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/percutaneous-catheter-recall-boston-scientific-removes-enroute-transcarotid-neuroprotection-system",
            ],
            confidence=0.9,
            support=30,
            demo=True,
        ),
        Pattern(
            name="guidance-tooling-scramble",
            stakeholder="sponsor",
            triggers=["guidance", "sbom", "premarket submission", "documentation"],
            description=(
                "Documentation-heavy final guidance triggers 3–6 month tooling and procurement sprints; "
                "mid-size firms license compliance tooling while smaller firms delay submissions a quarter."
            ),
            typical_actions=[
                "SBOM generation and vuln-scanning tools procured",
                "Trade groups request clarification on legacy-device expectations",
                "Some submissions slip a quarter as annexes are assembled",
            ],
            evidence_citations=[
                "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/cybersecurity-medical-devices-quality-management-system-considerations-and-content-premarket",
            ],
            confidence=0.78,
            support=11,
            demo=True,
        ),
        Pattern(
            name="docket-comment-surge",
            stakeholder="sponsor",
            triggers=["draft guidance", "comment", "docket", "commitments letter"],
            description=(
                "High-stakes drafts draw coordinated trade-association comments; sponsors use the comment "
                "window and pre-sub meetings to lock in evidentiary positions before finalization."
            ),
            typical_actions=[
                "Coordinated comments on acceptability thresholds",
                "Pre-IND / pre-sub meetings cite the draft to lock in agreements",
                "Development programs redesigned around the draft's examples",
            ],
            evidence_citations=[
                "http://www.fda.gov/regulatory-information/search-fda-guidance-documents/search-general-and-cross-cutting-topics-guidance-documents",
                "https://www.jdsupra.com/legalnews/fda-releases-draft-commitments-letter-6568665/",
            ],
            confidence=0.85,
            support=18,
            demo=True,
        ),
    ]
