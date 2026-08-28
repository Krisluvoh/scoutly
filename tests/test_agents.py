"""
Unit tests for each agent in isolation, using the MockClient — per the
instructor's guidance: "test each piece separately... if your workflow
fails, you want to know which component caused the problem."

These run entirely offline (no API key / network required).
"""

import pytest

from agents.account_intake_agent import AccountIntakeAgent
from agents.company_research_agent import CompanyResearchAgent
from agents.competitor_agent import CompetitorAgent
from agents.report_agent import ReportAgent
from agents.sales_recommendation_agent import SalesRecommendationAgent
from llm_client import MockClient
from memory import ScoutlyMemory


@pytest.fixture
def client():
    return MockClient()


@pytest.fixture
def memory():
    return ScoutlyMemory()


def test_account_intake_agent_returns_validated_schema(client, memory):
    agent = AccountIntakeAgent(client)
    result = agent.run(
        memory,
        {"rep_product_name": "CloudGuard", "company_url": "https://example.com", "competitor_urls": []},
    )
    assert isinstance(result["competitor_urls"], list)
    assert isinstance(result["research_priorities"], list)
    assert "rep_product_name" in result


def test_account_intake_agent_never_leaks_other_role_fields(client, memory):
    agent = AccountIntakeAgent(client)
    result = agent.run(memory, {"rep_product_name": "test", "company_url": "https://example.com"})
    assert "recommended_approach" not in result
    assert "leadership" not in result


def test_company_research_agent_returns_validated_schema(client, memory):
    agent = CompanyResearchAgent(client)
    result = agent.run(
        memory,
        {
            "company_url": "https://example.com",
            "fetched_pages": [],
            "edgar_filings": [],
            "intake_summary": {},
        },
    )
    assert "leadership" in result
    assert "sources" in result
    assert isinstance(result["sources"], list)


def test_company_research_agent_never_leaks_other_role_fields(client, memory):
    agent = CompanyResearchAgent(client)
    result = agent.run(memory, {"company_url": "https://example.com", "fetched_pages": []})
    assert "recommended_approach" not in result
    assert "rep_product_name" not in result


def test_competitor_agent_returns_validated_schema(client, memory):
    agent = CompetitorAgent(client)
    result = agent.run(
        memory,
        {"competitor_urls": ["https://competitor.com"], "fetched_pages": {}, "company_research_summary": {}},
    )
    assert "competitors" in result
    assert "differentiation_angle" in result


def test_competitor_agent_never_leaks_other_role_fields(client, memory):
    agent = CompetitorAgent(client)
    result = agent.run(memory, {"competitor_urls": [], "fetched_pages": {}})
    assert "recommended_approach" not in result
    assert "leadership" not in result


def test_sales_recommendation_agent_returns_validated_schema(client, memory):
    agent = SalesRecommendationAgent(client)
    result = agent.run(
        memory,
        {
            "intake_summary": {},
            "company_research_summary": {},
            "competitor_summary": {},
            "sourcing_channels": [],
        },
    )
    assert "recommended_approach" in result
    assert "next_steps" in result
    assert "objection_handling" in result
    assert "sourcing_recommendation" in result
    assert result["sourcing_recommendation"]["channel_type"]


def test_sales_recommendation_agent_never_leaks_other_role_fields(client, memory):
    agent = SalesRecommendationAgent(client)
    result = agent.run(memory, {"intake_summary": {}})
    assert "leadership" not in result
    assert "action_links" not in result


def test_report_agent_returns_validated_schema(client, memory):
    agent = ReportAgent(client)
    result = agent.run(
        memory,
        {
            "intake_summary": {},
            "company_research_summary": {},
            "competitor_summary": {},
            "recommendation_summary": {},
        },
    )
    assert "action_links" in result
    assert "leadership_information" in result
    assert "recommended_strategy" in result
    assert "sourcing_recommendation" in result


def test_evaluation_scores_are_within_bounds_when_present(client, memory):
    agent = AccountIntakeAgent(client)
    result = agent.run(memory, {"rep_product_name": "test", "company_url": "https://example.com"})
    if result.get("evaluation"):
        for score in result["evaluation"].values():
            assert 0 <= score <= 10
