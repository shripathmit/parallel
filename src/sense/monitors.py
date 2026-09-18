"""Register/teardown parallel.ai Monitors over the seed FDA sources."""
from src.par_client import ParallelClient

FDA_SOURCES = [
    {
        "name": "fda-guidances",
        "url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
        "objective": (
            "Detect newly issued, revised, or withdrawn FDA guidance documents "
            "(CDRH, CDER, CBER). Report the document title, URL, and whether it is "
            "new, a revision, or a withdrawal."
        ),
    },
    {
        "name": "fda-warning-letters",
        "url": "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters",
        "objective": (
            "Detect newly published FDA warning letters. Report the recipient company, "
            "issuing center/office, date, and the cited violations."
        ),
    },
    {
        "name": "fda-recalls",
        "url": "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts",
        "objective": (
            "Detect new FDA recalls, market withdrawals, and safety alerts. Report the "
            "product, recalling firm, classification, and reason."
        ),
    },
    {
        "name": "federal-register-fda",
        "url": "https://www.federalregister.gov/agencies/food-and-drug-administration",
        "objective": (
            "Detect new FDA rules, proposed rules, and notices published in the Federal "
            "Register. Report the document title, type, and URL."
        ),
    },
]


def setup_monitors(client: ParallelClient, webhook_url: str, frequency: str = "daily"):
    """Register one Monitor per FDA source. Returns a list of creation results."""
    created = []
    for src in FDA_SOURCES:
        resp = client.create_monitor(
            name=f"parallel-{src['name']}",
            objective=src["objective"],
            url=src["url"],
            frequency=frequency,  # TODO: verify accepted frequency values
            webhook_url=webhook_url,
        )
        created.append({"source": src["name"], "response": resp})
    return created


def teardown_monitors(client: ParallelClient):
    """Delete every Monitor whose name starts with 'parallel-'."""
    removed = []
    listing = client.list_monitors()
    if isinstance(listing, dict):
        monitors = listing.get("monitors", listing.get("results", []))
    else:
        monitors = listing or []
    for monitor in monitors:
        name = monitor.get("name", "")
        monitor_id = monitor.get("id", monitor.get("monitor_id"))
        if name.startswith("parallel-") and monitor_id:
            client.delete_monitor(monitor_id)
            removed.append(name)
    return removed
