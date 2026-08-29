"""
Tests for eval_models.py's pure-function pieces. The live-provider path
(evaluate_provider) needs real API keys and is exercised manually by the
user, not by this offline suite.
"""

from eval_models import _estimate_cost, _expected_mock_sources


def test_expected_mock_sources_includes_homepage_and_fixed_subpages():
    expected = _expected_mock_sources("https://example.com", ["https://competitor.com"])
    assert "https://example.com" in expected
    assert "https://example.com/about" in expected
    assert "https://example.com/leadership" in expected
    assert "https://example.com/press" in expected
    assert "https://competitor.com" in expected
    assert "https://competitor.com/press" in expected


def test_expected_mock_sources_excludes_unrelated_urls():
    expected = _expected_mock_sources("https://example.com", [])
    assert "https://some-other-site.com" not in expected


def test_estimate_cost_computes_from_real_token_counts():
    cost = _estimate_cost("openai", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 0.15 + 0.60


def test_estimate_cost_returns_none_for_unknown_provider():
    assert _estimate_cost("mock", input_tokens=100, output_tokens=100) is None
