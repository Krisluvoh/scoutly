"""
schemas.py
----------
Pydantic models that define and enforce the exact JSON contract for each
agent (this is the "models/schemas.py" file from the instructor's suggested
project layout). Agent output is parsed against these models before it is
handed to the next agent or returned to the caller — if a model call drifts
from the required shape, validation fails loudly instead of silently
passing bad data down the pipeline.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Evaluation(BaseModel):
    """Self-scored quality check every agent attaches to its own output."""

    relevance: int = Field(ge=0, le=10)
    clarity: int = Field(ge=0, le=10)
    engagement: int = Field(ge=0, le=10)
    deal_likelihood: int = Field(ge=0, le=10)


class AccountIntakeOutput(BaseModel):
    """Produced by agents/account_intake_agent.py."""

    rep_product_name: str = ""
    product_category: str = ""
    value_proposition: str = ""
    target_customer_name: str = ""
    company_url: str = ""
    competitor_urls: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    research_priorities: list[str] = Field(default_factory=list)
    product_document_summary: str = ""
    evaluation: Evaluation | None = None


class LeadershipContact(BaseModel):
    """One leadership figure surfaced during company research."""

    name: str = ""
    title: str = ""
    quote_or_note: str = ""


class CompanyResearchOutput(BaseModel):
    """Produced by agents/company_research_agent.py."""

    company_strategy: str = ""
    key_initiatives: list[str] = Field(default_factory=list)
    compliance_mentions: list[str] = Field(default_factory=list)
    leadership: list[LeadershipContact] = Field(default_factory=list)
    financial_summary: str = ""
    filing_highlights: list[str] = Field(default_factory=list)
    confidence: str = ""
    sources: list[str] = Field(default_factory=list)
    evaluation: Evaluation | None = None


class CompetitorSummary(BaseModel):
    """Research on one named competitor."""

    name: str = ""
    url: str = ""
    summary: str = ""
    notable_mentions: list[str] = Field(default_factory=list)


class CompetitorOutput(BaseModel):
    """Produced by agents/competitor_agent.py."""

    competitors: list[CompetitorSummary] = Field(default_factory=list)
    competitive_landscape: str = ""
    differentiation_angle: str = ""
    sources: list[str] = Field(default_factory=list)
    evaluation: Evaluation | None = None


class SourcingRecommendation(BaseModel):
    """Which sourcing channel (see sourcing_channels.py) best fits the
    target account's apparent trend focus, and why."""

    channel_type: str = ""
    recommended_platforms: list[str] = Field(default_factory=list)
    margin_notes: str = ""


class SalesRecommendationOutput(BaseModel):
    """Produced by agents/sales_recommendation_agent.py."""

    talking_points: list[str] = Field(default_factory=list)
    anticipated_objections: list[str] = Field(default_factory=list)
    recommended_approach: str = ""
    time_sensitive_signals: list[str] = Field(default_factory=list)
    next_steps: str = ""
    objection_handling: str = ""
    sourcing_recommendation: SourcingRecommendation | None = None
    evaluation: Evaluation | None = None


class AccountBriefOutput(BaseModel):
    """
    Produced by agents/report_agent.py — the one-page Account Intelligence
    Brief the CAP 931 brief asks for, assembled from every prior agent's
    output.
    """

    company_strategy: str = ""
    initiatives_and_compliance: list[str] = Field(default_factory=list)
    competitive_mentions: list[str] = Field(default_factory=list)
    leadership_information: list[LeadershipContact] = Field(default_factory=list)
    financial_summary: str = ""
    filing_highlights: list[str] = Field(default_factory=list)
    recommended_strategy: str = ""
    sourcing_recommendation: SourcingRecommendation | None = None
    action_links: list[str] = Field(default_factory=list)
    evaluation: Evaluation | None = None


SCHEMAS = {
    "account_intake": AccountIntakeOutput,
    "company_research": CompanyResearchOutput,
    "competitor": CompetitorOutput,
    "sales_recommendation": SalesRecommendationOutput,
    "report": AccountBriefOutput,
}
