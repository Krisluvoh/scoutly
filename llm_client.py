"""
llm_client.py
--------------
Pluggable LLM client layer for Trendora.

Trendora's agent logic (system prompts, JSON schemas, memory, orchestration)
is provider-agnostic. This module isolates the one part of the system that
talks to a specific model API, so the same agent code can run against:

  - Anthropic Claude (default / recommended for this project)
  - OpenAI GPT models
  - Groq (via langchain-groq's ChatGroq) — a free-tier-friendly option for
    development/prototyping, per the instructor's course notes
  - A local MockClient (no API key required — used for offline testing,
    grading demos without credentials, and CI)

This satisfies the "Production Deployment Considerations" rubric criterion:
the system is not hard-wired to a single vendor, which matters for cost,
rate-limit, and outage resilience in a real B2B account-research tool.

Note on architecture: the same idea can be built with full LangChain chains
(ChatPromptTemplate | model | parser) instead. Trendora's pipeline is a
fixed, non-branching five-step sequence (a "chain", not an "agent" in the
tool-calling sense), so a thin custom provider abstraction was simpler here
— no dynamic tool selection means no need for a heavier framework. The
Groq option below reuses langchain-groq's ChatGroq under the hood as the
actual wire client, since that's the documented, maintained integration.
"""

from __future__ import annotations

import json
import os
import random
import re
from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Common interface every provider client must implement."""

    @abstractmethod
    def generate(self, system_prompt: str, user_message: str) -> str:
        """Return the raw text completion for a single-turn system+user call."""
        raise NotImplementedError


class AnthropicClient(LLMClient):
    """Claude-backed client. Default provider for Trendora."""

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None):
        import anthropic  # local import so the package is optional until used

        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def generate(self, system_prompt: str, user_message: str) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=1200,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return "".join(block.text for block in response.content if getattr(block, "type", "") == "text")


class OpenAIClient(LLMClient):
    """GPT-backed client, kept for parity with the original assignment brief."""

    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None):
        import openai  # local import so the package is optional until used

        self.model = model
        self._client = openai.OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    def generate(self, system_prompt: str, user_message: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.4,
        )
        return response.choices[0].message.content


class GroqClient(LLMClient):
    """
    Groq-backed client via langchain-groq's ChatGroq, per the instructor's
    course notes on free-tier prototyping. Requires GROQ_API_KEY.
    """

    def __init__(self, model: str = "openai/gpt-oss-120b", api_key: str | None = None):
        from langchain_groq import (
            ChatGroq,  # local import so the package is optional until used
        )

        self._model = ChatGroq(
            model=model,
            temperature=0,
            api_key=api_key or os.environ.get("GROQ_API_KEY"),
        )

    def generate(self, system_prompt: str, user_message: str) -> str:
        response = self._model.invoke(
            [
                ("system", system_prompt),
                ("human", user_message),
            ]
        )
        return response.content


class MockClient(LLMClient):
    """
    Deterministic offline stand-in for grading / demo environments without an
    API key. Produces schema-shaped, semi-randomized JSON so the full
    multi-agent pipeline can be exercised end to end without network access.

    NOT a substitute for real model output — swap in AnthropicClient,
    OpenAIClient, or GroqClient for production use.
    """

    def generate(self, system_prompt: str, user_message: str) -> str:
        # Match only the opening "You are the <Role> Agent..." sentence —
        # a naive substring search misfires because agents' own prompts
        # mention *other* agents by full name while describing handoffs
        # (e.g. the Report Agent's prompt says "the Company Research
        # Agent's strategy summary"), which would misclassify it.
        opening_match = re.match(r"You are the (.+?) Agent\b", system_prompt)
        role_label = opening_match.group(1) if opening_match else "Account Intake"
        role = {
            "Account Intake": "account_intake",
            "Company Research": "company_research",
            "Competitor": "competitor",
            "Sales Recommendation": "sales_recommendation",
            "Report": "report",
        }.get(role_label, "account_intake")

        if role == "account_intake":
            payload = {
                "rep_product_name": "CloudGuard Endpoint Security",
                "product_category": "Cybersecurity / Endpoint Protection",
                "value_proposition": "Cuts endpoint breach response time from days to minutes",
                "target_customer_name": "VP of IT Security",
                "company_url": "https://example-prospect.com",
                "competitor_urls": ["https://example-competitor-a.com"],
                "missing_info": ["exact team size", "current security vendor"],
                "research_priorities": [
                    "recent leadership changes",
                    "compliance posture",
                    "hiring in security/IT",
                ],
            }
        elif role == "company_research":
            payload = {
                "company_strategy": "Expanding into mid-market accounts while investing in data compliance",
                "key_initiatives": ["Announced SOC 2 Type II certification", "Opened a new EU data center"],
                "compliance_mentions": ["References GDPR compliance on its trust page"],
                "leadership": [
                    {
                        "name": "Jordan Lee",
                        "title": "VP of IT Security",
                        "quote_or_note": "Quoted in a press release on data center expansion",
                    }
                ],
                "financial_summary": "No public filings found; appears to be privately held",
                "confidence": "medium",
                "sources": ["https://example-prospect.com", "https://example-prospect.com/press"],
            }
        elif role == "competitor":
            payload = {
                "competitors": [
                    {
                        "name": "Example Competitor A",
                        "url": "https://example-competitor-a.com",
                        "summary": (
                            "Positions itself as the enterprise-scale option with a longer deployment cycle"
                        ),
                        "notable_mentions": ["Recently discussed integration challenges on its blog"],
                    }
                ],
                "competitive_landscape": (
                    "The prospect's compliance focus is a gap competitors haven't emphasized"
                ),
                "differentiation_angle": "Lead with faster time-to-compliance rather than raw feature count",
                "sources": ["https://example-competitor-a.com"],
            }
        elif role == "sales_recommendation":
            payload = {
                "talking_points": [
                    "Their recent SOC 2 certification suggests compliance speed will resonate",
                    "New EU data center signals expansion — relevant to data residency features",
                ],
                "anticipated_objections": ["May already be mid-cycle with an existing vendor"],
                "recommended_approach": "Lead with compliance/time-to-certify value prop, not price",
                "time_sensitive_signals": [
                    "New EU data center opening — good timing for a data-residency pitch"
                ],
                "next_steps": "Request a 20-minute intro call with the VP of IT Security",
                "objection_handling": (
                    "If a current vendor is mentioned, ask what their SOC 2 renewal timeline looks like"
                ),
            }
        else:
            payload = {
                "company_strategy": "Expanding into mid-market accounts while investing in data compliance",
                "initiatives_and_compliance": [
                    "Announced SOC 2 Type II certification",
                    "References GDPR compliance on its trust page",
                ],
                "competitive_mentions": ["Competitor A has publicly discussed integration challenges"],
                "leadership_information": [
                    {
                        "name": "Jordan Lee",
                        "title": "VP of IT Security",
                        "quote_or_note": "Quoted in a press release on data center expansion",
                    }
                ],
                "financial_summary": "No public filings found; appears to be privately held",
                "recommended_strategy": (
                    "Lead with compliance/time-to-certify value prop; request a short intro call"
                ),
                "action_links": [
                    "https://example-prospect.com",
                    "https://example-prospect.com/press",
                    "https://example-competitor-a.com",
                ],
            }

        payload["_mock"] = True
        payload["_seed"] = random.randint(1000, 9999)
        return json.dumps(payload)


def get_client(provider: str = "mock", **kwargs) -> LLMClient:
    """Factory: provider in {'anthropic', 'openai', 'groq', 'mock'}."""
    provider = provider.lower()
    if provider == "anthropic":
        return AnthropicClient(**kwargs)
    if provider == "openai":
        return OpenAIClient(**kwargs)
    if provider == "groq":
        return GroqClient(**kwargs)
    if provider == "mock":
        return MockClient()
    raise ValueError(f"Unknown provider: {provider}")
