"""Seed the event store with realistic DEMO data.

Every item below is based on a real FDA publication (title, URL, date are
real; the analysis and clone predictions are illustrative dummy content).
All seeded records carry ``demo: True`` and the UI calls that out.

Run:  python -m src.demo_seed [data_dir]
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DEMO_DIRNAME = "demo"  # data/demo/<event_id>.analysis.json etc.


def _dt(y, m, d, hh=9, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc).isoformat()


EVENTS = [
    {
        "id": "evt-cyber-guidance",
        "source": "FDA guidance monitor",
        "url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/cybersecurity-medical-devices-quality-management-system-considerations-and-content-premarket",
        "title": "Final guidance: Cybersecurity in Medical Devices — QMS Considerations and Content of Premarket Submissions (Feb 2026)",
        "detected_at": _dt(2026, 2, 20),
        "change_type": "revised",
        "raw_diff": (
            "SUPERSEDES: 'Cybersecurity in Medical Devices: Quality System Considerations "
            "and Content of Premarket Submissions' (June 27, 2025).\n"
            "NEW IN THIS REVISION:\n"
            "- Addresses section 524B of the FD&C Act: premarket submissions for 'cyber devices' "
            "must now include a software bill of materials (SBOM), vulnerability remediation plans, "
            "and evidence of a coordinated vulnerability disclosure process.\n"
            "- Design documentation expectations moved into QMSR-aligned language (21 CFR Part 820, "
            "ISO 13485 clauses 7.3/8.5).\n"
            "- Labeling recommendations expanded: instructions for applying patches/updates must be "
            "included in device labeling.\n"
            "Docket: FDA-2021-D-1158. Issued by CDRH and CBER."
        ),
        "status": "simulated",
    },
    {
        "id": "evt-substantial-evidence",
        "source": "FDA guidance monitor",
        "url": "http://www.fda.gov/regulatory-information/search-fda-guidance-documents/search-general-and-cross-cutting-topics-guidance-documents",
        "title": "Draft guidance: Demonstrating Substantial Evidence of Effectiveness for Human Drug and Biological Products (Jun 24, 2026)",
        "detected_at": _dt(2026, 6, 25),
        "change_type": "new",
        "raw_diff": (
            "NEW DRAFT GUIDANCE (docket FDA-2019-D-4964), comment period open through 09/22/2026.\n"
            "Describes the 'one adequate and well-controlled investigation plus confirmatory evidence' "
            "pathway in detail: what counts as confirmatory evidence, standards for real-world evidence "
            "supplementation, and expectations for subgroup consistency.\n"
            "Cross-center scope: CDER and CBER."
        ),
        "status": "analyzed",
    },
    {
        "id": "evt-mdufa",
        "source": "Federal Register monitor",
        "url": "https://www.jdsupra.com/legalnews/fda-releases-draft-commitments-letter-6568665/",
        "title": "MDUFA reauthorization: draft commitments letter published; public meeting Aug 5, 2026",
        "detected_at": _dt(2026, 7, 8),
        "change_type": "new",
        "raw_diff": (
            "Federal Register notice (July 7, 2026): availability of the draft MDUFA commitments letter "
            "for reauthorization. Outlines device review policies, performance goals, and hiring plans "
            "agreed by FDA and industry. Public meeting scheduled August 5, 2026. HHS must transmit a "
            "formal agreement to Congress by January 15, 2027. House Energy & Commerce held an "
            "educational hearing July 15, 2026."
        ),
        "status": "analyzed",
    },
    {
        "id": "evt-jabil-wl",
        "source": "FDA warning letters",
        "url": "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/jabil-inc-731037-08272026",
        "title": "Warning Letter 320-26-120 to Jabil Inc. (Aug 27, 2026): CGMP violations at Pharmaceutics International, Cockeysville MD",
        "detected_at": _dt(2026, 8, 28),
        "change_type": "discovered",
        "raw_diff": (
            "CDER warning letter following Feb 23–Mar 6, 2026 inspection of Pharmaceutics International, "
            "Inc. (FEI 3006503102), a Jabil company. Significant violations of CGMP for finished "
            "pharmaceuticals (21 CFR parts 210/211). Letter warns that failure to correct may result in "
            "seizure and injunction without further notice."
        ),
        "status": "simulated",
    },
    {
        "id": "evt-newlife-wl",
        "source": "FDA warning letters",
        "url": "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/new-life-pharma-llc-725661-04142026",
        "title": "Warning Letter 320-26-65 to New Life Pharma LLC (Apr 14, 2026): unapproved semaglutide/tirzepatide products",
        "detected_at": _dt(2026, 4, 15),
        "change_type": "discovered",
        "raw_diff": (
            "CDER warning letter after Feb 3–13, 2026 inspection. Firm's 'Semaglutide Sterile Multi-Dose "
            "Vial' and 'Tirzepatide Sterile Multi-Dose Vial' deemed unapproved new drugs (505(a)) and "
            "misbranded (502(o)) — firm failed to register/list. CGMP nonconformance (501(a)(2)(B)). "
            "Investigators documented delay/denial of inspection (501(j) adulteration)."
        ),
        "status": "raw",
    },
    {
        "id": "evt-enroute-recall",
        "source": "FDA recalls",
        "url": "https://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/percutaneous-catheter-recall-boston-scientific-removes-enroute-transcarotid-neuroprotection-system",
        "title": "Class I recall: Boston Scientific ENROUTE Transcarotid Neuroprotection System (Aug 26, 2026)",
        "detected_at": _dt(2026, 8, 27),
        "change_type": "discovered",
        "raw_diff": (
            "Classified Class I on 08/26/2026 (Early Alert issued 07/24/2026). Device reverses blood flow "
            "at the carotid treatment site during lesion manipulation. As of July 9, one serious injury "
            "reported, no deaths."
        ),
        "status": "simulated",
    },
    {
        "id": "evt-ivenix-recall",
        "source": "FDA recalls",
        "url": "http://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/infusion-pump-recall-fresenius-kabi-removes-ivenix-large-volume-pumps",
        "title": "Class I recall: Fresenius Kabi Ivenix Large Volume Infusion Pumps (Jan 5, 2026)",
        "detected_at": _dt(2026, 1, 6),
        "change_type": "discovered",
        "raw_diff": (
            "Classified Class I on 01/05/2026 (Early Alert 11/24/2025). Large volume infusion pump for "
            "fluids/medications via single outlet. As of Oct 30, 2025: no serious injuries or deaths "
            "reported."
        ),
        "status": "analyzed",
    },
    {
        "id": "evt-medline-recall",
        "source": "FDA recalls",
        "url": "http://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/catheter-recall-expansion-medline-industries-removes-reprocessed-electrophysiology-and-ultrasound",
        "title": "Recall expansion: Medline reprocessed EP and ultrasound catheters, new lots added (Sep 2, 2026)",
        "detected_at": _dt(2026, 9, 3),
        "change_type": "revised",
        "raw_diff": (
            "Update 09/02/2026 adds lot numbers to the affected product list (prior updates 06/18/2026, "
            "recall summary 03/05/2026 classified Class I). Reprocessed electrophysiology diagnostic "
            "catheters for EP mapping/stimulation. As of May 18: no serious injuries or deaths."
        ),
        "status": "raw",
    },
]

ANALYSES = {
    "evt-cyber-guidance": {
        "change_type": "tightened",
        "summary": (
            "The final cybersecurity guidance hardens premarket expectations: SBOMs, vulnerability "
            "remediation plans, and coordinated disclosure processes are now explicit 524B submission "
            "requirements rather than recommendations. Submissions lacking them should expect refuse-to-accept "
            "or major deficiency findings."
        ),
        "affected_product_codes": ["QIH", "QEL", "LLZ"],
        "affected_submission_types": ["510(k)", "PMA", "De Novo"],
        "severity": 4,
        "citations": [
            "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/cybersecurity-medical-devices-quality-management-system-considerations-and-content-premarket",
            "https://www.fda.gov/media/190774/download?attachment",
        ],
        "confidence": 0.86,
    },
    "evt-substantial-evidence": {
        "change_type": "clarification",
        "summary": (
            "Draft guidance codifies when a single adequate and well-controlled trial plus confirmatory "
            "evidence can support approval, with new detail on real-world evidence as confirmatory support. "
            "Opens a comment window through Sep 22, 2026 — sponsors should weigh in now because the final "
            "version will shape evidence planning for years."
        ),
        "affected_product_codes": [],
        "affected_submission_types": ["NDA", "BLA"],
        "severity": 3,
        "citations": [
            "http://www.fda.gov/regulatory-information/search-fda-guidance-documents/search-general-and-cross-cutting-topics-guidance-documents",
        ],
        "confidence": 0.78,
    },
    "evt-mdufa": {
        "change_type": "new_requirement",
        "summary": (
            "The draft MDUFA commitments letter sets the review-performance bargain for the next five "
            "years: goal timelines, pre-submission program terms, and digital-health review capacity. "
            "The Aug 5 public meeting is the main venue to influence the final agreement before it goes "
            "to Congress in January 2027."
        ),
        "affected_product_codes": [],
        "affected_submission_types": ["510(k)", "PMA", "De Novo", "Q-Sub"],
        "severity": 3,
        "citations": [
            "https://www.jdsupra.com/legalnews/fda-releases-draft-commitments-letter-6568665/",
        ],
        "confidence": 0.72,
    },
    "evt-jabil-wl": {
        "change_type": "enforcement_shift",
        "summary": (
            "A warning letter to a large CDMO (Jabil/Pharmaceutics International) signals that CDER is "
            "willing to escalate against major contract manufacturers, not just small compounders. The "
            "seizure/injunction language is boilerplate but the target profile is the signal: CDMOs face "
            "the same CGMP bar as originators."
        ),
        "affected_product_codes": [],
        "affected_submission_types": [],
        "severity": 5,
        "citations": [
            "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/jabil-inc-731037-08272026",
        ],
        "confidence": 0.9,
    },
    "evt-newlife-wl": {
        "change_type": "enforcement_shift",
        "summary": (
            "CDER's letter to New Life Pharma combines three escalation markers: unapproved GLP-1 copies, "
            "CGMP adulteration, and documented inspection refusal (501(j)). The 501(j) finding is the "
            "sharpest — it independently adulterates the drugs and historically precedes import-alert or "
            "injunction action."
        ),
        "affected_product_codes": [],
        "affected_submission_types": [],
        "severity": 4,
        "citations": [
            "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/new-life-pharma-llc-725661-04142026",
        ],
        "confidence": 0.88,
    },
    "evt-enroute-recall": {
        "change_type": "enforcement_shift",
        "summary": (
            "Class I classification of the ENROUTE neuroprotection system — one serious injury so far — "
            "puts transcarotid devices under a spotlight. Expect heightened reviewer scrutiny of flow-reversal "
            "mechanisms in pending 510(k)s and possible special-controls discussion for the product code."
        ),
        "affected_product_codes": ["NTE", "DQY"],
        "affected_submission_types": ["510(k)", "PMA"],
        "severity": 5,
        "citations": [
            "https://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/percutaneous-catheter-recall-boston-scientific-removes-enroute-transcarotid-neuroprotection-system",
        ],
        "confidence": 0.84,
    },
    "evt-ivenix-recall": {
        "change_type": "enforcement_shift",
        "summary": (
            "A Class I recall on a large-volume infusion pump with no injuries reported yet shows CDRH "
            "classifying on risk potential, not outcomes. Infusion-pump software and alarm-system "
            "submissions should anticipate tougher human-factors and fault-tolerance questions."
        ),
        "affected_product_codes": ["FRN", "FRI"],
        "affected_submission_types": ["510(k)"],
        "severity": 4,
        "citations": [
            "http://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/infusion-pump-recall-fresenius-kabi-removes-ivenix-large-volume-pumps",
        ],
        "confidence": 0.8,
    },
    "evt-medline-recall": {
        "change_type": "tightened",
        "summary": (
            "The third expansion of the Medline reprocessed-catheter recall (new lots, Sep 2026) suggests "
            "the scope of the underlying reprocessing validation problem is still growing. Reprocessors "
            "should expect FDA to probe cleaning/sterilization validation depth across product families, "
            "not just the listed lots."
        ),
        "affected_product_codes": ["OAD", "NLH"],
        "affected_submission_types": ["510(k)"],
        "severity": 3,
        "citations": [
            "http://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/catheter-recall-expansion-medline-industries-removes-reprocessed-electrophysiology-and-ultrasound",
        ],
        "confidence": 0.76,
    },
}

SIMULATIONS = {
    "evt-cyber-guidance": {
        "enforcement": {
            "verdict": "Expect targeted inspections of cyber-device QMS documentation within 12 months",
            "actions": [
                "ORA adds SBOM and vulnerability-management records to routine QSIT inspection checklists for cyber devices",
                "First 483 observations cite missing coordinated-disclosure procedures under 21 CFR 820",
                "No immediate warning letters — 6–9 month education window before citations escalate",
            ],
            "timeline": "Inspections reflecting the guidance begin Q1 2027; first 483s by mid-2027",
            "confidence": "high",
            "reasoning": "Final guidance with explicit 524B requirements historically precedes inspection checklist updates, and the QMSR transition gives investigators a clean citation path.",
        },
        "reviewer": {
            "verdict": "Reviewers will refuse-to-accept submissions missing SBOM or remediation plans",
            "actions": [
                "RTA checklist updated: SBOM, known-vulnerability assessment, and patchability labeling become RTA items",
                "Deficiency letters cite guidance section on 'cybersecurity documentation' by page and line",
                "eSTAR templates gain mandatory cybersecurity annex fields",
            ],
            "timeline": "Applies to submissions received after the guidance's implementation date; reviewers trained within one review cycle",
            "confidence": "high",
            "reasoning": "Reviewers follow final guidance as de facto requirements, and the 524B statute gives them refusal authority for cyber devices.",
        },
        "sponsor": {
            "verdict": "Sponsors rush to bolt on SBOM tooling; smaller firms delay submissions",
            "actions": [
                "Mid-size device firms license SBOM generation and vuln-scanning tools; 3–6 month remediation sprints",
                "Trade groups (AdvaMed) request clarification on legacy-device expectations via comments",
                "Some 510(k)s slip a quarter as cybersecurity annexes are assembled",
            ],
            "timeline": "Tooling procurement Q4 2026; submission delays visible in H1 2027",
            "confidence": "medium",
            "reasoning": "Past cybersecurity guidance rollouts produced the same tooling scramble, but the statutory 524B backing makes delay costlier this time.",
        },
    },
    "evt-jabil-wl": {
        "enforcement": {
            "verdict": "CDMO sector enters a heightened inspection cycle; expect 2–3 more large-CDMO letters",
            "actions": [
                "CDER prioritizes follow-up inspections of the top 20 CDMOs by volume",
                "Warning letters to CDMOs cite data-integrity and aseptic-process controls, mirroring this letter's pattern",
                "Import alerts considered for foreign CDMOs with repeat 483s",
            ],
            "timeline": "Next wave of letters within 6–9 months",
            "confidence": "medium",
            "reasoning": "Warning letters to marquee CDMOs historically come in clusters as the Centers signal sector-wide expectations.",
        },
        "reviewer": {
            "verdict": "Reviewers increase manufacturing-section scrutiny for ANDAs/NDAs naming CDMOs",
            "actions": [
                "Information requests ask for CDMO inspection history and 483 responses",
                "Pre-approval inspections triggered more readily for first-time CDMO relationships",
            ],
            "timeline": "Immediate — reviewers cross-check the public warning-letter database",
            "confidence": "high",
            "reasoning": "Reviewers routinely check compliance status of listed manufacturing sites; a fresh letter to a major CDMO raises the bar for all its clients.",
        },
        "sponsor": {
            "verdict": "Sponsors audit CDMO partners and diversify manufacturing risk",
            "actions": [
                "Quality agreements renegotiated with enhanced audit rights",
                "Dual-sourcing evaluations accelerate for critical products",
                "Sponsors request 483/close-out letters from CDMOs before signing new work",
            ],
            "timeline": "Audit wave over the next two quarters",
            "confidence": "high",
            "reasoning": "A warning letter to your CDMO is a direct supply-chain risk; procurement and quality teams act on it immediately.",
        },
    },
    "evt-newlife-wl": {
        "enforcement": {
            "verdict": "GLP-1 compounders face continued escalation; 501(j) finding points toward injunction or import alert",
            "actions": [
                "Follow-up inspection scheduled to verify correction; failure invites consent decree discussions",
                "State pharmacy boards notified of the federal action",
                "Pattern feeds into CDER's ongoing GLP-1 compounding enforcement initiative",
            ],
            "timeline": "Escalation decision within 6 months of the letter",
            "confidence": "high",
            "reasoning": "Documented inspection refusal (501(j)) is one of the strongest escalation predictors in CDER's toolkit.",
        },
        "reviewer": {
            "verdict": "Minimal direct review impact — unapproved products sit outside the premarket system",
            "actions": [
                "No submission-pathway effects; reviewers note the letter only as market context",
            ],
            "timeline": "N/A",
            "confidence": "high",
            "reasoning": "Warning letters for unapproved/misbranded drugs don't change review standards for legitimate NDAs/ANDAs.",
        },
        "sponsor": {
            "verdict": "Legitimate sponsors treat it as competitive cleanup; compounders go quiet or exit",
            "actions": [
                "Branded GLP-1 sponsors cite the letter in payer discussions as a safety differentiator",
                "Compounding pharmacies tighten 503A/503B boundary compliance",
            ],
            "timeline": "Market effects over 2–3 quarters",
            "confidence": "medium",
            "reasoning": "Enforcement against gray-market GLP-1s historically benefits compliant sponsors while chilling borderline compounders.",
        },
    },
    "evt-enroute-recall": {
        "enforcement": {
            "verdict": "CDRH opens a product-code-level safety review; possible safety communication if injuries grow",
            "actions": [
                "MDR analysis for the transcarotid device category over the next two quarters",
                "If additional serious injuries surface, a public safety communication follows",
                "Inspection of the manufacturing site for CAPA adequacy",
            ],
            "timeline": "MDR trend review within 6 months",
            "confidence": "medium",
            "reasoning": "Class I recalls with serious injury in neurovascular devices routinely trigger category surveillance.",
        },
        "reviewer": {
            "verdict": "Pending transcarotid 510(k)s get additional flow-reversal safety questions",
            "actions": [
                "Deficiency letters request bench testing of embolic-protection performance under worst-case flow",
                "Predicate comparisons to ENROUTE challenged — reviewers ask how the new device differs in the failure mode",
                "Human-factors review of deployment instructions intensifies",
            ],
            "timeline": "Immediate for submissions currently under review",
            "confidence": "high",
            "reasoning": "Reviewers reflexively apply the failure mode of a Class I recall to every pending submission in the same product code.",
        },
        "sponsor": {
            "verdict": "Boston Scientific executes the recall playbook; competitors quietly differentiate",
            "actions": [
                "Customer notifications, field correction, and CAPA filed within weeks",
                "Competitors brief reviewers proactively on how their designs avoid the failure mode",
                "Hospitals review inventory and may pause new ENROUTE orders pending the fix",
            ],
            "timeline": "Field action complete within one quarter",
            "confidence": "high",
            "reasoning": "Large strategics run Class I recalls as rehearsed operations; the commercial impact concentrates in the affected product line.",
        },
    },
    "evt-substantial-evidence": {
        "enforcement": {
            "verdict": "No near-term enforcement signal — draft guidance is a review-policy document",
            "actions": [
                "Promotional enforcement (OPDP) may later reference the final guidance when challenging efficacy claims",
            ],
            "timeline": "Only after finalization",
            "confidence": "medium",
            "reasoning": "Draft guidances don't create enforceable expectations; the enforcement read-through comes with the final version.",
        },
        "reviewer": {
            "verdict": "Review divisions begin aligning on confirmatory-evidence standards during the comment period",
            "actions": [
                "Internal training on RWE-as-confirmatory-evidence criteria",
                "Sponsors submitting under the single-trial-plus-confirmatory path get early informal feedback referencing the draft",
            ],
            "timeline": "Alignment visible in review behavior within 2–3 quarters",
            "confidence": "medium",
            "reasoning": "Reviewers start applying draft thinking well before finalization, especially on high-profile evidentiary standards.",
        },
        "sponsor": {
            "verdict": "Sponsors flood the docket with comments; evidence-planning strategies shift",
            "actions": [
                "Trade associations coordinate comments on RWE acceptability thresholds",
                "Development programs redesign confirmatory packages around the draft's examples",
                "Pre-IND meetings cite the draft to lock in evidentiary agreements",
            ],
            "timeline": "Comments by Sep 22, 2026; program redesigns through 2027",
            "confidence": "high",
            "reasoning": "A draft on the single-trial pathway is a once-a-decade event for evidence strategy — industry engages heavily.",
        },
    },
    "evt-mdufa": {
        "enforcement": {
            "verdict": "No direct enforcement impact — user-fee negotiations govern review resources, not compliance",
            "actions": [],
            "timeline": "N/A",
            "confidence": "high",
            "reasoning": "MDUFA sets review performance goals; enforcement posture is set by the Centers' compliance offices independently.",
        },
        "reviewer": {
            "verdict": "Reviewers anticipate workload and timeline changes; pre-sub program terms may tighten",
            "actions": [
                "Q-Sub review timelines and meeting-grant rates adjust to the new goals",
                "Hiring under the agreement gradually reduces reviewer workload over 2–3 years",
            ],
            "timeline": "Takes effect with the reauthorized agreement (FY2028)",
            "confidence": "medium",
            "reasoning": "Each MDUFA cycle reshapes review capacity; reviewers adapt their queue management to the new goal structure.",
        },
        "sponsor": {
            "verdict": "Industry lobbies the Aug 5 meeting hard on review timelines and digital-health capacity",
            "actions": [
                "AdvaMed/MDVA submit detailed comments on pre-sub and breakthrough-device timelines",
                "Sponsors time major submissions around the transition to avoid goal-date ambiguity",
            ],
            "timeline": "Lobbying peaks at the Aug 5 public meeting; submission timing effects in late 2027",
            "confidence": "high",
            "reasoning": "The commitments letter is industry's main lever on review performance — engagement is always intense.",
        },
    },
    "evt-ivenix-recall": {
        "enforcement": {
            "verdict": "Infusion-pump software remains a CDRH priority; expect continued Class I classifications on risk potential",
            "actions": [
                "CDRH maintains heightened classification posture for infusion-pump software anomalies",
                "Firms with pump software updates face closer postmarket surveillance",
            ],
            "timeline": "Ongoing through 2026–2027",
            "confidence": "medium",
            "reasoning": "The Ivenix classification continues CDRH's pattern of treating infusion-pump failures as high-risk regardless of reported injuries.",
        },
        "reviewer": {
            "verdict": "Infusion-pump 510(k)s face deeper software and alarm-system questioning",
            "actions": [
                "Deficiency letters probe software hazard analysis and alarm-fatigue mitigations",
                "Human-factors validation expectations rise for pump user interfaces",
            ],
            "timeline": "Immediate",
            "confidence": "high",
            "reasoning": "A Class I pump recall resets reviewer priors on software reliability for the whole device category.",
        },
        "sponsor": {
            "verdict": "Pump manufacturers preemptively audit software QA; hospitals scrutinize fleets",
            "actions": [
                "Internal software CAPA reviews across pump portfolios",
                "Health systems request field-safety notices and software version audits",
            ],
            "timeline": "One to two quarters",
            "confidence": "medium",
            "reasoning": "Hospitals are sensitive to pump recalls after a decade of high-profile incidents; procurement teams act fast.",
        },
    },
    "evt-medline-recall": {
        "enforcement": {
            "verdict": "Reprocessing validation under a microscope; ORA may expand inspections to other reprocessors",
            "actions": [
                "Follow-up inspection of Medline's reprocessing validation protocols",
                "Other third-party reprocessors receive for-cause or surveillance inspections",
            ],
            "timeline": "Inspection wave within 6 months",
            "confidence": "medium",
            "reasoning": "Repeated recall expansions signal systemic validation gaps, which historically draw sector-wide inspection attention.",
        },
        "reviewer": {
            "verdict": "Reprocessed-device 510(k)s get tougher cleaning/sterilization validation questions",
            "actions": [
                "Reviewers request worst-case soiling and simulated-use validation data",
                "Predicate comparisons limited to reprocessed (not original) devices",
            ],
            "timeline": "Immediate",
            "confidence": "high",
            "reasoning": "Each expansion of this recall reinforces reviewer skepticism about reprocessing validation claims.",
        },
        "sponsor": {
            "verdict": "Hospitals reconsider reprocessed catheter sourcing; OEMs highlight single-use safety",
            "actions": [
                "Supply-chain teams reassess reprocessor contracts",
                "OEMs market single-use alternatives with safety messaging",
            ],
            "timeline": "Purchasing shifts over 2–3 quarters",
            "confidence": "medium",
            "reasoning": "Recall expansions erode hospital confidence in reprocessed devices faster than the initial recall.",
        },
    },
}


def seed(data_dir: str) -> dict:
    """Write demo events + demo payloads. Idempotent: skips if events exist."""
    from src.clones.patterns import PatternStore, match_patterns, seed_demo_patterns
    from src.sense.events import EventStore, ChangeEvent

    data = Path(data_dir)
    store = EventStore(str(data))
    if store.list():
        return {"seeded": False, "reason": "store not empty"}

    demo_dir = data / DEMO_DIRNAME
    demo_dir.mkdir(parents=True, exist_ok=True)

    # Seed the pattern library first; predictions below attach patterns_used
    # using the real match_patterns algorithm (not hand-picked).
    pattern_store = PatternStore(str(data))
    for pattern in seed_demo_patterns():
        pattern_store.add(pattern)
    all_patterns = pattern_store.list()

    for spec in EVENTS:
        event = ChangeEvent(
            id=spec["id"],
            source=spec["source"],
            url=spec["url"],
            title=spec["title"],
            detected_at=spec["detected_at"],
            change_type=spec["change_type"],
            raw_diff=spec["raw_diff"],
            status=spec["status"],
            demo=True,
        )
        store.append(event)
        eid = spec["id"]
        (demo_dir / f"{eid}.analysis.json").write_text(
            json.dumps({"demo": True, **ANALYSES[eid]}, indent=2), encoding="utf-8"
        )
        analysis = ANALYSES[eid]
        sim = {
            "demo": True,
            "change_summary": analysis["summary"],
            "change_type": analysis["change_type"],
            "severity": analysis["severity"],
            "predictions": {
                name: {
                    "clone": name,
                    **SIMULATIONS[eid][name],
                    "patterns_used": [
                        {
                            "name": p.name,
                            "score": score,
                            "confidence": p.confidence,
                            "matched_triggers": matched,
                        }
                        for p, score, matched in match_patterns(
                            analysis, all_patterns, name
                        )
                    ],
                }
                for name in ("enforcement", "reviewer", "sponsor")
            },
        }
        (demo_dir / f"{eid}.simulation.json").write_text(
            json.dumps(sim, indent=2), encoding="utf-8"
        )

    # Materialize payloads for events already past "raw"
    analyses_dir = data / "analyses"
    analyses_dir.mkdir(exist_ok=True)
    sims_dir = data / "simulations"
    sims_dir.mkdir(exist_ok=True)
    for spec in EVENTS:
        eid = spec["id"]
        if spec["status"] in ("analyzed", "simulated", "alerted"):
            (analyses_dir / f"{eid}.json").write_text(
                (demo_dir / f"{eid}.analysis.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        if spec["status"] in ("simulated", "alerted"):
            (sims_dir / f"{eid}.json").write_text(
                (demo_dir / f"{eid}.simulation.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    return {"seeded": True, "events": len(EVENTS)}


if __name__ == "__main__":
    print(json.dumps(seed(sys.argv[1] if len(sys.argv) > 1 else "data"), indent=2))
