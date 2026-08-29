"""
eval_models.py
----------------
Empirical comparison of Claude, GPT-4o-mini, and Groq's GPT-OSS on the
same fixed account-research scenario, measuring JSON/schema compliance,
an automatable "unsupported claims" proxy, latency, and estimated cost.

Deliberately runs with fetch_mode="mock" — that holds the fetched page
content identical across providers, so the LLM is the only thing that
varies between runs. That's the correct controlled variable for this
comparison; comparing against live, possibly-changing web pages would
confound "which model is better" with "which run got different input."

Any provider without its API key set in the environment is skipped with a
clear message — this script will not fabricate a result row for a
provider it couldn't actually call. Run it once you have real keys
configured to get a real comparison; no results are committed to the repo
sight-unseen.

Usage:
    ANTHROPIC_API_KEY=sk-ant-... OPENAI_API_KEY=sk-... GROQ_API_KEY=gsk-... \
        uv run eval_models.py
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

from dotenv import load_dotenv

from agents.base_agent import AgentError
from llm_client import LLMClient, get_client
from main import SCENARIOS
from memory import ScoutlyMemory
from orchestrator import ScoutlyOrchestrator
from web_research import MockFetcher

load_dotenv()

_SCENARIO = SCENARIOS[0]

# Approximate, illustrative list prices in USD per million tokens (input, output),
# as of the time this script was written. Real prices change; this is meant to
# give a rough order-of-magnitude cost comparison, not a billing-grade figure —
# always check the provider's current pricing page before relying on this.
_PRICING_PER_MILLION_TOKENS = {
    "anthropic": (3.00, 15.00),  # Claude Sonnet-tier pricing
    "openai": (0.15, 0.60),  # GPT-4o-mini pricing
    "groq": (0.15, 0.75),  # gpt-oss-120b on Groq, approximate
}

_REQUIRED_ENV_VAR = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
}


class CountingClient(LLMClient):
    """Wraps a real LLMClient to count generate() calls (more than 5 across
    a 5-agent run means at least one agent needed its built-in JSON retry)
    and accumulate real token usage for cost estimation."""

    def __init__(self, inner: LLMClient):
        self._inner = inner
        self.call_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def generate(self, system_prompt: str, user_message: str) -> str:
        self.call_count += 1
        text = self._inner.generate(system_prompt, user_message)
        if self._inner.last_usage:
            self.total_input_tokens += self._inner.last_usage.get("input_tokens", 0)
            self.total_output_tokens += self._inner.last_usage.get("output_tokens", 0)
        return text


@dataclass
class ProviderResult:
    provider: str
    ran: bool
    schema_compliant: bool = False
    generate_calls: int = 0
    retries_needed: int = 0
    unsupported_sources: list[str] = field(default_factory=list)
    latency_seconds: float = 0.0
    estimated_cost_usd: float | None = None
    skip_reason: str = ""


def _expected_mock_sources(company_url: str, competitor_urls: list[str]) -> set[str]:
    """
    Pure function: replicates exactly which URLs MockFetcher makes
    available for a given scenario (homepage + its fixed /about,
    /leadership, /press links, for the company and each competitor) — the
    known-safe set that a well-grounded agent's "sources" should be a
    subset of.
    """
    urls = {company_url, *competitor_urls}
    expected = set(urls)
    for url in urls:
        expected.update(urljoin(url, path) for path in ("/about", "/leadership", "/press"))
    return expected


def _estimate_cost(provider: str, input_tokens: int, output_tokens: int) -> float | None:
    """Pure function: real token counts x the illustrative pricing table above."""
    pricing = _PRICING_PER_MILLION_TOKENS.get(provider)
    if pricing is None:
        return None
    input_price, output_price = pricing
    return (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price


def evaluate_provider(provider: str) -> ProviderResult:
    env_var = _REQUIRED_ENV_VAR[provider]
    if not os.environ.get(env_var):
        return ProviderResult(provider=provider, ran=False, skip_reason=f"{env_var} not set")

    client = CountingClient(get_client(provider))
    memory = ScoutlyMemory(account_id="eval_scenario")
    orchestrator = ScoutlyOrchestrator(client, memory, MockFetcher())

    expected_sources = _expected_mock_sources(_SCENARIO["company_url"], _SCENARIO["competitor_urls"])

    start = time.perf_counter()
    try:
        result = orchestrator.run_account_brief(
            rep_product_name=_SCENARIO["rep_product_name"],
            value_proposition=_SCENARIO["value_proposition"],
            target_customer_name=_SCENARIO["target_customer_name"],
            company_url=_SCENARIO["company_url"],
            competitor_urls=_SCENARIO["competitor_urls"],
            product_category=_SCENARIO["product_category"],
        )
        schema_compliant = True
    except AgentError:
        result = None
        schema_compliant = False
    latency = time.perf_counter() - start

    unsupported = []
    if result:
        cited = set(result["company_research"].get("sources", []))
        cited |= set(result["competitor"].get("sources", []))
        unsupported = sorted(cited - expected_sources)

    return ProviderResult(
        provider=provider,
        ran=True,
        schema_compliant=schema_compliant,
        generate_calls=client.call_count,
        retries_needed=max(0, client.call_count - 5),
        unsupported_sources=unsupported,
        latency_seconds=latency,
        estimated_cost_usd=_estimate_cost(provider, client.total_input_tokens, client.total_output_tokens),
    )


def _format_report(results: list[ProviderResult]) -> str:
    ran = [r for r in results if r.ran]
    skipped = [r for r in results if not r.ran]

    lines = [
        "# Model comparison",
        "",
        f"Scenario: `{_SCENARIO['company_url']}` (fetch_mode=mock, held constant across providers)",
        "",
    ]

    if ran:
        lines += [
            "| Provider | Schema OK | Generate calls | Retries needed | Unsupported sources "
            "| Latency (s) | Est. cost (USD) |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in ran:
            lines.append(
                f"| {r.provider} | {'yes' if r.schema_compliant else 'no'} | {r.generate_calls} | "
                f"{r.retries_needed} | {len(r.unsupported_sources)} | {r.latency_seconds:.2f} | "
                f"{'n/a' if r.estimated_cost_usd is None else f'${r.estimated_cost_usd:.5f}'} |"
            )
        lines.append("")

    if skipped:
        lines.append("Skipped (no API key configured):")
        for r in skipped:
            lines.append(f"- {r.provider}: {r.skip_reason}")
        lines.append("")

    if not ran:
        lines.append(
            "No provider had an API key configured, so no real comparison ran. "
            "Set ANTHROPIC_API_KEY / OPENAI_API_KEY / GROQ_API_KEY and rerun."
        )

    return "\n".join(lines)


def main() -> None:
    results = [evaluate_provider(p) for p in ("anthropic", "openai", "groq")]
    report = _format_report(results)
    print(report)

    if any(r.ran for r in results):
        with open("docs/model_comparison.md", "w") as f:
            f.write(report + "\n")
        print("\nSaved to docs/model_comparison.md")


if __name__ == "__main__":
    main()
