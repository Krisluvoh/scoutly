"""Tests for ScoutlyMemory: update hooks, persistence, context injection."""

import json
import os
import tempfile

from memory import ScoutlyMemory


def test_update_from_account_intake_sets_profile():
    memory = ScoutlyMemory()
    memory.update_from_account_intake(
        {
            "rep_product_name": "CloudGuard",
            "product_category": "Cybersecurity",
            "value_proposition": "Faster breach response",
            "target_customer_name": "VP of IT Security",
            "company_url": "https://example.com",
        }
    )
    assert memory.account_profile["rep_product_name"] == "CloudGuard"
    assert memory.account_profile["company_url"] == "https://example.com"


def test_update_from_company_research_appends_history_and_facts():
    memory = ScoutlyMemory()
    memory.update_from_company_research(
        "https://example.com",
        {
            "company_strategy": "Expanding into mid-market",
            "confidence": "medium",
            "leadership": [{"name": "Jordan Lee", "title": "VP of IT Security"}],
            "key_initiatives": ["Announced SOC 2 certification"],
            "financial_summary": "No public filings found",
        },
    )
    assert len(memory.research_history) == 1
    assert memory.research_history[0]["company_url"] == "https://example.com"
    assert "Jordan Lee (VP of IT Security)" in memory.known_account_facts
    assert "Announced SOC 2 certification" in memory.known_account_facts
    signal = memory.account_signals["https://example.com"]
    assert signal["last_financial_summary"] == "No public filings found"


def test_known_account_facts_do_not_duplicate():
    memory = ScoutlyMemory()
    memory.update_from_company_research("https://example.com", {"key_initiatives": ["Fact A"]})
    memory.update_from_company_research("https://example.com", {"key_initiatives": ["Fact A", "Fact B"]})
    assert memory.known_account_facts.count("Fact A") == 1
    assert "Fact B" in memory.known_account_facts


def test_register_prospect_objection_is_deduplicated():
    memory = ScoutlyMemory()
    memory.register_prospect_objection("already has a vendor")
    memory.register_prospect_objection("already has a vendor")
    assert memory.past_prospect_objections.count("already has a vendor") == 1


def test_as_context_string_caps_research_history_to_five():
    memory = ScoutlyMemory()
    for i in range(8):
        memory.update_from_company_research(f"https://account-{i}.com", {"confidence": "low"})
    context = json.loads(memory.as_context_string())
    assert len(context["research_history"]) == 5
    assert context["research_history"][-1]["company_url"] == "https://account-7.com"


def test_save_and_load_round_trip():
    memory = ScoutlyMemory(account_id="account_test")
    memory.update_from_account_intake({"rep_product_name": "CloudGuard", "company_url": "https://example.com"})

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "memory.json")
        memory.save(path)
        loaded = ScoutlyMemory.load(path)
        assert loaded.account_id == "account_test"
        assert loaded.account_profile["rep_product_name"] == "CloudGuard"


def test_load_returns_fresh_memory_when_file_missing():
    memory = ScoutlyMemory.load("/tmp/definitely_does_not_exist_scoutly.json", account_id="new_account")
    assert memory.account_id == "new_account"
    assert memory.account_profile == {}
