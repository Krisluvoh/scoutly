"""
Integration test for the full Account Intake -> Company Research ->
Competitor -> Sales Recommendation -> Report pipeline, plus the
prospect-objection follow-up path, using the MockClient and MockFetcher.
"""

from llm_client import MockClient
from memory import TrendoraMemory
from orchestrator import TrendoraOrchestrator
from web_research import MockFetcher


def _make_orchestrator(memory: TrendoraMemory | None = None) -> TrendoraOrchestrator:
    return TrendoraOrchestrator(MockClient(), memory or TrendoraMemory(), MockFetcher())


def test_full_pipeline_produces_all_five_outputs():
    orchestrator = _make_orchestrator()
    result = orchestrator.run_account_brief(
        rep_product_name="CloudGuard",
        value_proposition="Faster breach response",
        target_customer_name="VP of IT Security",
        company_url="https://example-prospect.com",
        competitor_urls=["https://example-competitor.com"],
    )
    assert set(result.keys()) == {
        "company_url",
        "account_intake",
        "company_research",
        "competitor",
        "sales_recommendation",
        "report",
        "sources",
    }
    assert result["account_intake"]["rep_product_name"]
    assert result["company_research"]["leadership"]
    assert result["report"]["action_links"]


def test_memory_updated_after_full_pipeline_run():
    orchestrator = _make_orchestrator()
    orchestrator.run_account_brief(
        rep_product_name="CloudGuard",
        value_proposition="Faster breach response",
        target_customer_name="VP of IT Security",
        company_url="https://example-prospect.com",
        competitor_urls=[],
    )
    assert orchestrator.memory.account_profile.get("rep_product_name")
    assert len(orchestrator.memory.research_history) == 1
    assert "https://example-prospect.com" in orchestrator.memory.account_signals


def test_transcript_logs_all_five_agent_turns():
    orchestrator = _make_orchestrator()
    orchestrator.run_account_brief(
        rep_product_name="CloudGuard",
        value_proposition="Faster breach response",
        target_customer_name="VP of IT Security",
        company_url="https://example-prospect.com",
        competitor_urls=[],
    )
    agents_logged = [entry["agent"] for entry in orchestrator.transcript]
    assert agents_logged == [
        "account_intake",
        "company_research",
        "competitor",
        "sales_recommendation",
        "report",
    ]


def test_objection_followup_routes_to_sales_recommendation_only():
    orchestrator = _make_orchestrator()
    orchestrator.run_account_brief(
        rep_product_name="CloudGuard",
        value_proposition="Faster breach response",
        target_customer_name="VP of IT Security",
        company_url="https://example-prospect.com",
        competitor_urls=[],
    )
    followup = orchestrator.handle_prospect_objection("already has a vendor")
    assert "recommended_approach" in followup
    assert "already has a vendor" in orchestrator.memory.past_prospect_objections
    assert orchestrator.transcript[-1]["agent"] == "sales_recommendation_followup"


def test_pipeline_runs_with_pre_existing_memory():
    memory = TrendoraMemory(account_id="returning_account")
    memory.register_prospect_objection("burned by a slow onboarding once before")
    orchestrator = _make_orchestrator(memory)
    result = orchestrator.run_account_brief(
        rep_product_name="CloudGuard",
        value_proposition="Faster breach response",
        target_customer_name="VP of IT Security",
        company_url="https://example-prospect.com",
        competitor_urls=[],
    )
    assert result["sales_recommendation"]["recommended_approach"]
    assert "burned by a slow onboarding once before" in orchestrator.memory.past_prospect_objections
