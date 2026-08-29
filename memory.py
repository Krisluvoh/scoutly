"""
memory.py
---------
Contextual memory shared across Scoutly's five agents within a session,
and persisted to disk so it survives across sessions for a returning
account. This is what lets the Sales Recommendation Agent say things like
"this prospect already pushed back on price last time we researched them,
lead with the budget tier" instead of treating every research run on the
same account as stateless.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime


@dataclass
class ScoutlyMemory:
    """
    One instance per account (prospective company). Each agent calls one of
    the update_from_* methods below with its own output after it runs (see
    orchestrator.py), so by the time the Sales Recommendation Agent runs,
    memory already has everything Intake, Company Research, and Competitor
    research learned. as_context_string() is what actually gets shown to
    the model each turn.
    """

    account_id: str = "guest"
    account_profile: dict = field(default_factory=dict)
    known_account_facts: list = field(default_factory=list)
    past_prospect_objections: list = field(default_factory=list)
    research_history: list = field(default_factory=list)
    account_signals: dict = field(default_factory=dict)
    last_updated: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # ---------- update hooks, one per agent ----------

    def update_from_account_intake(self, intake_output: dict) -> None:
        """Called after the Account Intake Agent runs. Saves the rep's
        product/company framing for this account."""
        self.account_profile.update(
            {
                "rep_product_name": intake_output.get("rep_product_name"),
                "product_category": intake_output.get("product_category"),
                "value_proposition": intake_output.get("value_proposition"),
                "target_customer_name": intake_output.get("target_customer_name"),
                "company_url": intake_output.get("company_url"),
                # Kept so a later check_for_updates() run knows what to
                # re-check without the rep re-entering competitor URLs.
                "competitor_urls": intake_output.get("competitor_urls"),
            }
        )
        self._touch()

    def update_from_company_research(self, company_url: str, research_output: dict) -> None:
        """Called after the Company Research Agent runs. Logs this research
        pass to history and caches durable facts (leadership, strategy)."""
        self.research_history.append(
            {
                "company_url": company_url,
                "confidence": research_output.get("confidence"),
                "summary": research_output.get("company_strategy"),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        leadership_names = [
            f"{p.get('name')} ({p.get('title')})"
            for p in research_output.get("leadership", [])
            if p.get("name")
        ]
        self._merge_unique(self.known_account_facts, leadership_names)
        self._merge_unique(self.known_account_facts, research_output.get("key_initiatives", []))
        self.account_signals.setdefault(company_url, {})["last_financial_summary"] = (
            research_output.get("financial_summary")
        )
        self._touch()

    def update_from_competitor_research(self, competitor_output: dict) -> None:
        """Called after the Competitor Agent runs. Remembers the
        differentiation angle so it stays consistent across follow-up runs."""
        angle = competitor_output.get("differentiation_angle")
        if angle:
            self.account_profile["last_differentiation_angle"] = angle
        self._touch()

    def update_from_sales_recommendation(self, recommendation_output: dict) -> None:
        """Called after the Sales Recommendation Agent runs. Remembers its
        recommended approach so a later turn can keep it consistent."""
        approach = recommendation_output.get("recommended_approach")
        if approach:
            self.account_profile["last_recommended_approach"] = approach
        self._touch()

    def register_prospect_objection(self, objection: str) -> None:
        """Called directly by orchestrator.handle_prospect_objection, before
        the follow-up turn even runs, so the Sales Recommendation Agent sees
        it as prior context."""
        self._merge_unique(self.past_prospect_objections, [objection])
        self._touch()

    # ---------- helpers ----------

    @staticmethod
    def _merge_unique(target: list, new_items: list) -> None:
        """Appends items not already present, in place, so repeated facts/
        objections across research runs don't get duplicated."""
        for item in new_items or []:
            if item not in target:
                target.append(item)

    def _touch(self) -> None:
        self.last_updated = datetime.now(UTC).isoformat()

    def as_context_string(self) -> str:
        """Compact summary injected into every agent prompt as MEMORY context."""
        return json.dumps(
            {
                "account_profile": self.account_profile,
                "known_account_facts": self.known_account_facts,
                "past_prospect_objections": self.past_prospect_objections,
                "research_history": self.research_history[-5:],
                "account_signals": self.account_signals,
            },
            indent=2,
        )

    # ---------- persistence ----------

    def save(self, path: str) -> None:
        """Writes this memory to a JSON file, creating parent folders if needed."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, path: str, account_id: str = "guest") -> ScoutlyMemory:
        """Loads a saved memory file if one exists for this account, otherwise starts a fresh one."""
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            return cls(**data)
        return cls(account_id=account_id)
