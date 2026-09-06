"""
Integration test for the full Account Intake -> Company Research ->
Competitor -> Sales Recommendation -> Report pipeline, plus the
prospect-objection follow-up path, using the MockClient and MockFetcher.
"""

from llm_client import MockClient
from memory import ScoutlyMemory
from orchestrator import ScoutlyOrchestrator, _guess_company_name_candidates
from web_research import MockFetcher


def _make_orchestrator(memory: ScoutlyMemory | None = None) -> ScoutlyOrchestrator:
    return ScoutlyOrchestrator(MockClient(), memory or ScoutlyMemory(), MockFetcher())


def test_guess_company_name_candidates_tries_both_sides_of_separator():
    # Real-world example: paloaltonetworks.com's <title> puts the tagline
    # first and the actual company name after the dash — a naive "take the
    # first half" heuristic would only ever guess the tagline.
    candidates = _guess_company_name_candidates(
        "Leader in Cybersecurity Protection & Software for the Modern Enterprises - Palo Alto Networks"
    )
    assert "Palo Alto Networks" in candidates


def test_guess_company_name_candidates_returns_empty_list_for_blank_title():
    assert _guess_company_name_candidates("") == []


def test_full_pipeline_produces_all_five_outputs():
    orchestrator = _make_orchestrator()
    result = orchestrator.run_account_brief(
        rep_product_name="CloudGuard",
        value_proposition="Faster breach response",
        target_customer_name="VP of IT Security",
        company_url="https://example-prospect.com",
        competitor_urls=["https://example-competitor.com"],
        practice_area="cybersecurity_risk",
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
    assert result["report"]["engagement_recommendation"]["engagement_type"]


def test_full_pipeline_with_no_practice_area_omits_engagement_recommendation():
    orchestrator = _make_orchestrator()
    result = orchestrator.run_account_brief(
        rep_product_name="CloudGuard",
        value_proposition="Faster breach response",
        target_customer_name="VP of IT Security",
        company_url="https://example-prospect.com",
        competitor_urls=[],
    )
    assert result["sales_recommendation"]["engagement_recommendation"] is None
    assert result["report"]["engagement_recommendation"] is None


def test_practice_playbook_data_is_threaded_into_agent_inputs():
    orchestrator = _make_orchestrator()
    orchestrator.run_account_brief(
        rep_product_name="CloudGuard",
        value_proposition="Faster breach response",
        target_customer_name="VP of IT Security",
        company_url="https://example-prospect.com",
        competitor_urls=[],
        practice_area="cybersecurity_risk",
    )
    company_research_input = next(
        e["input"] for e in orchestrator.transcript if e["agent"] == "company_research"
    )
    sales_recommendation_input = next(
        e["input"] for e in orchestrator.transcript if e["agent"] == "sales_recommendation"
    )
    assert company_research_input["practice_research_signals"]
    assert sales_recommendation_input["practice_trigger_events"]
    assert sales_recommendation_input["engagement_models"]


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


def test_check_for_updates_reports_facts_not_seen_before():
    # MockClient/MockFetcher are deterministic, so pre-seed known_account_facts
    # with something different from what the mock always returns — anything
    # the mock returns that wasn't in this seeded list is genuinely "new" from
    # check_for_updates' point of view, without needing the mocks to vary.
    memory = ScoutlyMemory(account_id="account_to_recheck")
    memory.known_account_facts = ["A fact from a previous, different research run"]
    orchestrator = _make_orchestrator(memory)

    report = orchestrator.check_for_updates(
        company_url="https://example-prospect.com",
        competitor_urls=["https://example-competitor.com"],
    )

    assert report["company_url"] == "https://example-prospect.com"
    assert report["checked_at"]
    assert report["new_facts"]
    assert "A fact from a previous, different research run" not in report["new_facts"]


def test_check_for_updates_only_reruns_company_and_competitor_agents():
    orchestrator = _make_orchestrator()
    orchestrator.check_for_updates(
        company_url="https://example-prospect.com",
        competitor_urls=[],
    )
    agents_logged = [entry["agent"] for entry in orchestrator.transcript]
    assert "account_intake" not in agents_logged
    assert "sales_recommendation" not in agents_logged
    assert "company_research" in agents_logged
    assert "competitor" in agents_logged


def test_pipeline_runs_with_pre_existing_memory():
    memory = ScoutlyMemory(account_id="returning_account")
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
