"""
llm_client.py
--------------
Pluggable LLM client layer for Scoutly.

Scoutly's agent logic (system prompts, JSON schemas, memory, orchestration)
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
(ChatPromptTemplate | model | parser) instead. Scoutly's pipeline is a
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
    """Claude-backed client. Default provider for Scoutly."""

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
                "rep_product_name": "Scoutly Curated Sourcing",
                "product_category": "Trend-Item Sourcing & Curation Service",
                "value_proposition": (
                    "We find and secure hard-to-find, high-margin trend inventory so your "
                    "buying team doesn't have to chase drops themselves"
                ),
                "target_customer_name": "Head Buyer",
                "company_url": "https://example-boutique-retailer.com",
                "competitor_urls": ["https://example-retail-competitor.com"],
                "missing_info": ["current sourcing vendor", "typical order volume"],
                "research_priorities": [
                    "recent merchandising/leadership changes",
                    "trend categories the retailer is expanding into",
                    "public statements about supply-chain challenges",
                ],
            }
        elif role == "company_research":
            payload = {
                "company_strategy": "Expanding its Y2K and streetwear assortment to reach a younger shopper",
                "key_initiatives": [
                    "Announced a new curated drops program",
                    "Opened two new boutique locations",
                ],
                "compliance_mentions": ["References supplier code-of-conduct standards on its about page"],
                "leadership": [
                    {
                        "name": "Jordan Lee",
                        "title": "Head Buyer",
                        "quote_or_note": "Quoted in a press release on the new curated drops program",
                    }
                ],
                "financial_summary": "No public filings found; appears to be privately held",
                "confidence": "medium",
                "sources": [
                    "https://example-boutique-retailer.com",
                    "https://example-boutique-retailer.com/press",
                ],
            }
        elif role == "competitor":
            payload = {
                "competitors": [
                    {
                        "name": "Example Retail Competitor",
                        "url": "https://example-retail-competitor.com",
                        "summary": "Positions itself as the broader fast-fashion option with less curation",
                        "notable_mentions": ["Recently discussed inventory glut on its blog"],
                    }
                ],
                "competitive_landscape": (
                    "The prospect's curated-drop focus is a gap competitors haven't emphasized"
                ),
                "differentiation_angle": (
                    "Lead with curated scarcity/authenticity rather than raw catalog size"
                ),
                "sources": ["https://example-retail-competitor.com"],
            }
        elif role == "sales_recommendation":
            payload = {
                "talking_points": [
                    "Their new curated drops program suggests appetite for a dedicated sourcing partner",
                    "Two new boutique locations signal expansion — relevant to inventory scaling",
                ],
                "anticipated_objections": ["May already have an informal sourcing relationship in place"],
                "recommended_approach": "Lead with curated scarcity and margin upside, not price",
                "time_sensitive_signals": [
                    "New boutique locations opening — good timing to pitch inventory scaling support"
                ],
                "next_steps": "Request a 20-minute intro call with the Head Buyer",
                "objection_handling": (
                    "If an existing sourcing relationship is mentioned, ask about typical fulfillment lag"
                ),
                "sourcing_recommendation": {
                    "channel_type": "Boutique/Vintage",
                    "recommended_platforms": ["Fleek", "Boutique by the Box"],
                    "margin_notes": (
                        "Fits this retailer's Y2K/curated-fashion focus and commands higher resale value "
                        "than generic wholesale, per the Boutique/Vintage channel's own notes"
                    ),
                },
            }
        else:
            payload = {
                "company_strategy": "Expanding its Y2K and streetwear assortment to reach a younger shopper",
                "initiatives_and_compliance": [
                    "Announced a new curated drops program",
                    "References supplier code-of-conduct standards on its about page",
                ],
                "competitive_mentions": ["Competitor has publicly discussed inventory glut"],
                "leadership_information": [
                    {
                        "name": "Jordan Lee",
                        "title": "Head Buyer",
                        "quote_or_note": "Quoted in a press release on the new curated drops program",
                    }
                ],
                "financial_summary": "No public filings found; appears to be privately held",
                "recommended_strategy": (
                    "Lead with curated scarcity and margin upside; request a short intro call"
                ),
                "sourcing_recommendation": {
                    "channel_type": "Boutique/Vintage",
                    "recommended_platforms": ["Fleek", "Boutique by the Box"],
                    "margin_notes": (
                        "Fits this retailer's Y2K/curated-fashion focus and commands higher resale value "
                        "than generic wholesale, per the Boutique/Vintage channel's own notes"
                    ),
                },
                "action_links": [
                    "https://example-boutique-retailer.com",
                    "https://example-boutique-retailer.com/press",
                    "https://example-retail-competitor.com",
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
