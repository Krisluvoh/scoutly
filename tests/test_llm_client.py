"""Tests for the provider abstraction layer (mock client + factory)."""

import json

import pytest

from llm_client import MockClient, get_client


def test_mock_client_account_intake_shape():
    client = MockClient()
    raw = client.generate("You are the Account Intake Agent...", "some input")
    data = json.loads(raw)
    assert "rep_product_name" in data
    assert "research_priorities" in data


def test_mock_client_company_research_shape():
    client = MockClient()
    raw = client.generate("You are the Company Research Agent...", "some input")
    data = json.loads(raw)
    assert "leadership" in data
    assert "financial_summary" in data


def test_mock_client_competitor_shape():
    client = MockClient()
    raw = client.generate("You are the Competitor Agent...", "some input")
    data = json.loads(raw)
    assert "competitors" in data
    assert "differentiation_angle" in data


def test_mock_client_sales_recommendation_shape():
    client = MockClient()
    raw = client.generate("You are the Sales Recommendation Agent...", "some input")
    data = json.loads(raw)
    assert "recommended_approach" in data
    assert "next_steps" in data


def test_mock_client_report_shape():
    client = MockClient()
    raw = client.generate("You are the Report Agent...", "some input")
    data = json.loads(raw)
    assert "action_links" in data
    assert "leadership_information" in data


def test_get_client_factory_mock():
    client = get_client("mock")
    assert isinstance(client, MockClient)


def test_get_client_factory_unknown_provider_raises():
    with pytest.raises(ValueError):
        get_client("not-a-real-provider")
