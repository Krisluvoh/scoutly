"""
main.py
-------
Demo entry point. Runs representative Scoutly account-research scenarios
end to end (Account Intake -> Company Research -> Competitor -> Sales
Recommendation -> Report, plus one prospect-objection follow-up), printing
each agent's structured JSON output and saving a full transcript.

Usage (with uv):
    uv run main.py                                   # MockClient + MockFetcher, no API key/network needed
    SCOUTLY_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... SCOUTLY_FETCH_MODE=http uv run main.py
    SCOUTLY_PROVIDER=openai OPENAI_API_KEY=sk-... SCOUTLY_FETCH_MODE=http uv run main.py
    SCOUTLY_PROVIDER=groq GROQ_API_KEY=gsk-... SCOUTLY_FETCH_MODE=http uv run main.py
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv

from llm_client import get_client
from memory import ScoutlyMemory
from orchestrator import ScoutlyOrchestrator
from web_research import get_fetcher

load_dotenv()

SCENARIOS = [
    {
        "account_id": "account_001",
        "rep_product_name": "Scoutly Curated Sourcing",
        "product_category": "Trend-Item Sourcing & Curation Service",
        "value_proposition": (
            "We find and secure hard-to-find, high-margin trend inventory so your buying "
            "team doesn't have to chase drops themselves"
        ),
        "target_customer_name": "Head Buyer",
        "company_url": "https://www.urbanoutfitters.com",
        "competitor_urls": ["https://www.freepeople.com", "https://www.princesspolly.com"],
        "practice_area": "retail_trend_sourcing",
        "follow_up_objection": "We already have an informal relationship with a few boutique suppliers.",
    },
    {
        "account_id": "account_002",
        "rep_product_name": "Scoutly Curated Sourcing",
        "product_category": "Trend-Item Sourcing & Curation Service",
        "value_proposition": (
            "We monitor scarcity and drop timing across wholesale, liquidation, and boutique "
            "channels so you always know where to source the next trend item at the best margin"
        ),
        "target_customer_name": "Merchandising Director",
        "company_url": "https://www.asos.com",
        "competitor_urls": ["https://www.prettylittlething.com"],
        "practice_area": "retail_trend_sourcing",
        "follow_up_objection": None,
    },
    {
        "account_id": "account_003",
        "rep_product_name": "Scoutly Curated Sourcing",
        "product_category": "Trend-Item Sourcing & Curation Service",
        "value_proposition": (
            "We turn liquidation and overstock inventory into curated, sellable drops "
            "without your team taking on the sourcing risk"
        ),
        "target_customer_name": "VP of Merchandising",
        "company_url": "https://www.thredup.com",
        "competitor_urls": ["https://www.therealreal.com"],
        "practice_area": "retail_trend_sourcing",
        "follow_up_objection": "We're already committed to a liquidation vendor through year-end.",
    },
]


def run_all(provider: str = "mock", fetch_mode: str = "mock") -> None:
    """Runs every scenario in SCENARIOS through the full pipeline, printing and saving each one."""
    client = get_client(provider)
    fetcher = get_fetcher(fetch_mode)
    os.makedirs("output", exist_ok=True)

    for scenario in SCENARIOS:
        print("=" * 80)
        print(f"SCENARIO: {scenario['rep_product_name']} -> {scenario['company_url']}  "
              f"(account: {scenario['account_id']})")
        print("=" * 80)

        memory_path = f"output/memory_{scenario['account_id']}.json"
        memory = ScoutlyMemory.load(memory_path, account_id=scenario["account_id"])
        orchestrator = ScoutlyOrchestrator(client, memory, fetcher)

        result = orchestrator.run_account_brief(
            rep_product_name=scenario["rep_product_name"],
            value_proposition=scenario["value_proposition"],
            target_customer_name=scenario["target_customer_name"],
            company_url=scenario["company_url"],
            competitor_urls=scenario["competitor_urls"],
            product_category=scenario["product_category"],
            practice_area=scenario["practice_area"],
        )

        print("\n--- ACCOUNT INTAKE AGENT OUTPUT ---")
        print(json.dumps(result["account_intake"], indent=2))
        print("\n--- COMPANY RESEARCH AGENT OUTPUT ---")
        print(json.dumps(result["company_research"], indent=2))
        print("\n--- COMPETITOR AGENT OUTPUT ---")
        print(json.dumps(result["competitor"], indent=2))
        print("\n--- SALES RECOMMENDATION AGENT OUTPUT ---")
        print(json.dumps(result["sales_recommendation"], indent=2))
        print("\n--- ONE-PAGE ACCOUNT BRIEF (REPORT AGENT) ---")
        print(json.dumps(result["report"], indent=2))

        if scenario["follow_up_objection"]:
            print("\n--- PROSPECT OBJECTION FOLLOW-UP ---")
            followup = orchestrator.handle_prospect_objection(scenario["follow_up_objection"])
            print(json.dumps(followup, indent=2))

        orchestrator.memory.save(memory_path)
        orchestrator.save_transcript(f"output/transcript_{scenario['account_id']}.json")
        print(f"\nMemory saved to {memory_path}")
        print(f"Transcript saved to output/transcript_{scenario['account_id']}.json\n")


if __name__ == "__main__":
    run_all(
        provider=os.environ.get("SCOUTLY_PROVIDER", "mock"),
        fetch_mode=os.environ.get("SCOUTLY_FETCH_MODE", "mock"),
    )
