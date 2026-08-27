"""
main.py
-------
Demo entry point. Runs representative Trendora account-research scenarios
end to end (Account Intake -> Company Research -> Competitor -> Sales
Recommendation -> Report, plus one prospect-objection follow-up), printing
each agent's structured JSON output and saving a full transcript.

Usage (with uv):
    uv run main.py                                   # MockClient + MockFetcher, no API key/network needed
    TRENDORA_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... TRENDORA_FETCH_MODE=http uv run main.py
    TRENDORA_PROVIDER=openai OPENAI_API_KEY=sk-... TRENDORA_FETCH_MODE=http uv run main.py
    TRENDORA_PROVIDER=groq GROQ_API_KEY=gsk-... TRENDORA_FETCH_MODE=http uv run main.py
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv

from llm_client import get_client
from memory import TrendoraMemory
from orchestrator import TrendoraOrchestrator
from web_research import get_fetcher

load_dotenv()

SCENARIOS = [
    {
        "account_id": "account_001",
        "rep_product_name": "CloudGuard Endpoint Security",
        "product_category": "Cybersecurity / Endpoint Protection",
        "value_proposition": "Cuts endpoint breach response time from days to minutes",
        "target_customer_name": "VP of IT Security",
        "company_url": "https://www.paloaltonetworks.com",
        "competitor_urls": ["https://www.crowdstrike.com", "https://www.sentinelone.com"],
        "follow_up_objection": "We already renewed our contract with our current vendor last quarter.",
    },
    {
        "account_id": "account_002",
        "rep_product_name": "Meridian Payroll Cloud",
        "product_category": "HR / Payroll SaaS",
        "value_proposition": "Automates multi-state payroll compliance for growing companies",
        "target_customer_name": "Head of People Operations",
        "company_url": "https://www.gusto.com",
        "competitor_urls": ["https://www.rippling.com"],
        "follow_up_objection": None,
    },
    {
        "account_id": "account_003",
        "rep_product_name": "Nimbus Data Warehouse",
        "product_category": "Cloud Data Platform",
        "value_proposition": "Cuts analytics query costs by consolidating warehouses into one platform",
        "target_customer_name": "Director of Data Engineering",
        "company_url": "https://www.snowflake.com",
        "competitor_urls": ["https://www.databricks.com"],
        "follow_up_objection": "We're already mid-migration to a competitor's platform.",
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
        memory = TrendoraMemory.load(memory_path, account_id=scenario["account_id"])
        orchestrator = TrendoraOrchestrator(client, memory, fetcher)

        result = orchestrator.run_account_brief(
            rep_product_name=scenario["rep_product_name"],
            value_proposition=scenario["value_proposition"],
            target_customer_name=scenario["target_customer_name"],
            company_url=scenario["company_url"],
            competitor_urls=scenario["competitor_urls"],
            product_category=scenario["product_category"],
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
        provider=os.environ.get("TRENDORA_PROVIDER", "mock"),
        fetch_mode=os.environ.get("TRENDORA_FETCH_MODE", "mock"),
    )
