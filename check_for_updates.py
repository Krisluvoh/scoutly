"""
check_for_updates.py
----------------------
Reruns Company Research + Competitor research for a previously-researched
account and reports what's genuinely new since the last check — the real,
working half of an "alert system" (see ScoutlyOrchestrator.check_for_updates
in orchestrator.py for the rerun/diff logic itself).

This script does NOT run on a schedule by itself — Streamlit Cloud's free
tier has no persistent background scheduler, and a script has no way to
wake itself up. The honest way to get "periodically rerun and notify"
behavior out of this is to invoke this script from an external scheduler:

    # cron (Linux/macOS), once a day at 7am:
    0 7 * * * cd /path/to/scoutly && uv run check_for_updates.py --account-id account_001

    # Windows Task Scheduler: create a daily trigger whose action runs
    #   uv run check_for_updates.py --account-id account_001
    # with the working directory set to this project's folder.

Usage:
    uv run check_for_updates.py --account-id account_001
    SCOUTLY_ALERT_WEBHOOK_URL=https://... uv run check_for_updates.py --account-id account_001
"""

from __future__ import annotations

import argparse
import json
import os

import requests
from dotenv import load_dotenv

from llm_client import get_client
from memory import ScoutlyMemory
from orchestrator import ScoutlyOrchestrator
from web_research import get_fetcher

load_dotenv()


def check_account(account_id: str, provider: str, fetch_mode: str) -> dict:
    """Loads the saved memory for account_id, reruns research, saves the
    updated memory back, and returns the diff report."""
    memory_path = f"output/memory_{account_id}.json"
    memory = ScoutlyMemory.load(memory_path, account_id=account_id)

    company_url = memory.account_profile.get("company_url")
    competitor_urls = memory.account_profile.get("competitor_urls") or []
    if not company_url:
        raise ValueError(
            f"No company_url found in {memory_path} — run main.py or the Streamlit "
            "app for this account at least once before checking for updates."
        )

    orchestrator = ScoutlyOrchestrator(get_client(provider), memory, get_fetcher(fetch_mode))
    report = orchestrator.check_for_updates(company_url, competitor_urls)

    memory.save(memory_path)

    alerts_path = f"output/alerts_{account_id}.json"
    history = []
    if os.path.exists(alerts_path):
        with open(alerts_path) as f:
            history = json.load(f)
    history.append(report)
    os.makedirs(os.path.dirname(alerts_path) or ".", exist_ok=True)
    with open(alerts_path, "w") as f:
        json.dump(history, f, indent=2)

    return report


def notify_webhook(account_id: str, report: dict) -> None:
    """POSTs a small JSON summary to SCOUTLY_ALERT_WEBHOOK_URL if it's set —
    a no-op otherwise. This is the real-world integration point (Slack,
    Teams, email-via-Zapier, etc. all accept a plain webhook), left
    unconfigured by default since no such endpoint exists in this project."""
    webhook_url = os.environ.get("SCOUTLY_ALERT_WEBHOOK_URL")
    if not webhook_url or not report["new_facts"]:
        return
    try:
        requests.post(
            webhook_url,
            json={
                "text": (
                    f"Scoutly: {len(report['new_facts'])} new signal(s) for "
                    f"{account_id} ({report['company_url']}): {', '.join(report['new_facts'])}"
                )
            },
            timeout=8,
        )
    except requests.RequestException as exc:
        print(f"Webhook notification failed (non-fatal): {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--account-id", required=True, help="Account ID, matching output/memory_<id>.json")
    parser.add_argument("--provider", default=os.environ.get("SCOUTLY_PROVIDER", "mock"))
    parser.add_argument("--fetch-mode", default=os.environ.get("SCOUTLY_FETCH_MODE", "mock"))
    args = parser.parse_args()

    report = check_account(args.account_id, args.provider, args.fetch_mode)

    print(f"Checked {report['company_url']} at {report['checked_at']}")
    if report["new_facts"]:
        print(f"{len(report['new_facts'])} new signal(s):")
        for fact in report["new_facts"]:
            print(f"  - {fact}")
    else:
        print("No new signals since the last check.")

    notify_webhook(args.account_id, report)


if __name__ == "__main__":
    main()
