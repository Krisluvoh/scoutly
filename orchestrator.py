"""
orchestrator.py
----------------
Coordinates Scoutly's five agents into a single account-research run and
keeps ScoutlyMemory in sync between them. This is the "system" in
"multi-agent system" — each agent only ever sees its own role's system
prompt; the orchestrator is what fetches real page content, stitches agent
outputs together, and is the only piece of code that talks to all five.

In standard agentic-system terms, this is a "chain" (a fixed,
orchestrator-defined sequence), not a model-driven agent-with-tools —
appropriate since Scoutly's workflow doesn't need dynamic tool selection.
Page fetching happens here, before an agent ever runs, so fetched text is
just another piece of plain input data to the agent — no tool-calling loop
needed.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from agents.account_intake_agent import AccountIntakeAgent
from agents.company_research_agent import CompanyResearchAgent
from agents.competitor_agent import CompetitorAgent
from agents.report_agent import ReportAgent
from agents.sales_recommendation_agent import SalesRecommendationAgent
from llm_client import LLMClient
from memory import ScoutlyMemory
from sourcing_channels import SOURCING_CHANNELS
from web_research import (
    Fetcher,
    HttpFetcher,
    PageContent,
    fetch_filing_sections,
    get_fetcher,
    lookup_public_filings,
)

# Homepage + up to this many discovered subpages (leadership/press/about/etc)
# per company. Bounds how many HTTP requests one research run can trigger.
_MAX_COMPANY_SUBPAGES = 3


def _guess_company_name_candidates(title: str) -> list[str]:
    """
    Pure function: a fetched homepage's <title> -> candidate company names to
    try against SEC EDGAR, in order. Titles vary in which half holds the
    actual name — "Palo Alto Networks — Cybersecurity Leader" vs "Leader in
    Cybersecurity... - Palo Alto Networks" both appear in the wild — so try
    both halves of the first separator rather than assuming one order.
    """
    if not title:
        return []
    for sep in ("—", "-", "|"):
        if sep in title:
            parts = [p.strip() for p in title.split(sep, 1)]
            return [p for p in parts if p]
    return [title.strip()]


class ScoutlyOrchestrator:
    """
    Runs one account's research through all five agents in order and keeps
    a single ScoutlyMemory in sync as each agent's output comes back. One
    instance = one account's research history; the memory and transcript
    both accumulate across every run_account_brief/handle_prospect_objection
    call made on the same instance.
    """

    def __init__(
        self,
        client: LLMClient,
        memory: ScoutlyMemory | None = None,
        fetcher: Fetcher | None = None,
        sec_edgar_contact_email: str = "capstone-project@example.com",
    ):
        self.client = client
        self.memory = memory or ScoutlyMemory()
        self.fetcher = fetcher or get_fetcher("mock")
        self.sec_edgar_contact_email = sec_edgar_contact_email
        self.account_intake_agent = AccountIntakeAgent(client)
        self.company_research_agent = CompanyResearchAgent(client)
        self.competitor_agent = CompetitorAgent(client)
        self.sales_recommendation_agent = SalesRecommendationAgent(client)
        self.report_agent = ReportAgent(client)
        self.transcript: list[dict] = []

    def _log(self, agent: str, input_payload: dict, output_payload: dict) -> None:
        self.transcript.append({"agent": agent, "input": input_payload, "output": output_payload})

    def _fetch_pages_with_subpages(self, url: str) -> list[PageContent]:
        """Fetches a homepage plus a few discovered subpages (leadership/
        press/about/etc), capped so one run can't fan out unboundedly. Used
        for both the target company and each competitor — a competitor's
        public research deserves the same depth as the prospect's."""
        pages = [self.fetcher.fetch_page(url)]
        for link in pages[0].links[:_MAX_COMPANY_SUBPAGES]:
            pages.append(self.fetcher.fetch_page(link))
        return pages

    @staticmethod
    def _pages_as_dicts(pages: list[PageContent]) -> list[dict]:
        """BaseAgent.build_user_message() runs json.dumps() on turn_input, so
        fetched pages need to be plain dicts, not PageContent dataclasses."""
        return [
            {"url": p.url, "title": p.title, "text": p.text, "error": p.error} for p in pages
        ]

    def _lookup_filings_for(self, company_pages: list[PageContent]) -> list:
        """Tries each name candidate from the fetched homepage's title
        against EDGAR in turn, stopping at the first one that returns real
        filings — see _guess_company_name_candidates for why more than one
        candidate is needed."""
        for candidate in _guess_company_name_candidates(company_pages[0].title):
            filings = lookup_public_filings(candidate, contact_email=self.sec_edgar_contact_email)
            if filings:
                return filings
        return []

    def run_account_brief(
        self,
        rep_product_name: str,
        value_proposition: str,
        target_customer_name: str,
        company_url: str,
        competitor_urls: list[str],
        product_category: str = "",
        product_document_text: str = "",
    ) -> dict:
        """
        Runs one full Account Intake -> Company Research -> Competitor ->
        Sales Recommendation -> Report pass for a single target account,
        updating self.memory at each step. Returns every agent's structured
        output plus a flattened list of real source URLs for the UI's
        Action Links section. product_document_text is the optional
        extracted text of an uploaded product-overview file (see
        document_intake.py) — the CAP 931 brief's optional "upload a
        proprietary internal sheet" input.
        """
        intake_input = {
            "rep_product_name": rep_product_name,
            "product_category": product_category,
            "value_proposition": value_proposition,
            "target_customer_name": target_customer_name,
            "company_url": company_url,
            "competitor_urls": competitor_urls,
            "product_document_text": product_document_text,
        }
        intake_output = self.account_intake_agent.run(self.memory, intake_input)
        self.memory.update_from_account_intake(intake_output)
        self._log("account_intake", intake_input, intake_output)

        company_pages = self._fetch_pages_with_subpages(company_url)
        edgar_filings = self._lookup_filings_for(company_pages)

        # Only fetch full filing text for the single most recent filing, and
        # only against a real fetcher — mock mode should never make network
        # calls, and fetching every filing's full text would be needlessly
        # slow/costly for one research run.
        filing_sections: dict[str, str] = {}
        if edgar_filings and isinstance(self.fetcher, HttpFetcher):
            filing_sections = fetch_filing_sections(
                edgar_filings[0].filing_url, contact_email=self.sec_edgar_contact_email
            )

        company_research_input = {
            "company_url": company_url,
            "fetched_pages": self._pages_as_dicts(company_pages),
            "edgar_filings": [vars(f) for f in edgar_filings],  # FilingInfo -> dict, same reason as above
            "filing_sections": filing_sections,
            "intake_summary": intake_output,
        }
        company_research_output = self.company_research_agent.run(self.memory, company_research_input)
        self.memory.update_from_company_research(company_url, company_research_output)
        self._log("company_research", company_research_input, company_research_output)

        competitor_pages = {url: self._fetch_pages_with_subpages(url) for url in competitor_urls}
        competitor_input = {
            "competitor_urls": competitor_urls,
            "fetched_pages": {
                url: self._pages_as_dicts(pages) for url, pages in competitor_pages.items()
            },
            "value_proposition": value_proposition,
            "company_research_summary": company_research_output,
        }
        competitor_output = self.competitor_agent.run(self.memory, competitor_input)
        self.memory.update_from_competitor_research(competitor_output)
        self._log("competitor", competitor_input, competitor_output)

        recommendation_input = {
            "intake_summary": intake_output,
            "company_research_summary": company_research_output,
            "competitor_summary": competitor_output,
            # Static reference data, not fetched — grounds the agent's channel/platform
            # pick in real options instead of letting it invent platform names.
            "sourcing_channels": SOURCING_CHANNELS,
        }
        recommendation_output = self.sales_recommendation_agent.run(self.memory, recommendation_input)
        self.memory.update_from_sales_recommendation(recommendation_output)
        self._log("sales_recommendation", recommendation_input, recommendation_output)

        report_input = {
            "intake_summary": intake_output,
            "company_research_summary": company_research_output,
            "competitor_summary": competitor_output,
            "recommendation_summary": recommendation_output,
        }
        report_output = self.report_agent.run(self.memory, report_input)
        self._log("report", report_input, report_output)

        # dict.fromkeys() dedupes while preserving first-seen order — plain
        # set() would scramble the order sources appear in the final brief.
        sources = list(
            dict.fromkeys(
                company_research_output.get("sources", []) + competitor_output.get("sources", [])
            )
        )

        return {
            "company_url": company_url,
            "account_intake": intake_output,
            "company_research": company_research_output,
            "competitor": competitor_output,
            "sales_recommendation": recommendation_output,
            "report": report_output,
            "sources": sources,
        }

    def check_for_updates(self, company_url: str, competitor_urls: list[str]) -> dict:
        """
        Re-fetches the target company and competitor pages and reruns just
        Company Research + Competitor (not the full five-agent chain —
        intake and the sales recommendation don't need rerunning to detect
        whether anything changed), then reports which known_account_facts
        are genuinely new since the last time this account was researched.

        This is the real, working half of an "alert system": rerun +
        detect changes. It does not run itself on a schedule — Streamlit
        Cloud's free tier has no persistent background scheduler for that —
        see check_for_updates.py, which is meant to be invoked by an
        external scheduler (cron / Task Scheduler) for the "periodically
        rerun and notify" behavior.
        """
        facts_before = list(self.memory.known_account_facts)

        company_pages = self._fetch_pages_with_subpages(company_url)
        edgar_filings = self._lookup_filings_for(company_pages)
        company_research_input = {
            "company_url": company_url,
            "fetched_pages": self._pages_as_dicts(company_pages),
            "edgar_filings": [vars(f) for f in edgar_filings],
            "filing_sections": {},  # deep filing text rarely changes day-to-day; skip for speed
            "intake_summary": {},
        }
        company_research_output = self.company_research_agent.run(self.memory, company_research_input)
        self.memory.update_from_company_research(company_url, company_research_output)
        self._log("company_research", company_research_input, company_research_output)

        competitor_pages = {url: self._fetch_pages_with_subpages(url) for url in competitor_urls}
        competitor_input = {
            "competitor_urls": competitor_urls,
            "fetched_pages": {url: self._pages_as_dicts(pages) for url, pages in competitor_pages.items()},
            "value_proposition": self.memory.account_profile.get("value_proposition", ""),
            "company_research_summary": company_research_output,
        }
        competitor_output = self.competitor_agent.run(self.memory, competitor_input)
        self.memory.update_from_competitor_research(competitor_output)
        self._log("competitor", competitor_input, competitor_output)

        new_facts = [fact for fact in self.memory.known_account_facts if fact not in facts_before]
        return {
            "company_url": company_url,
            "new_facts": new_facts,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    def handle_prospect_objection(self, objection_text: str) -> dict:
        """
        Follow-up turn: the prospect pushed back after outreach. Routes
        straight to the Sales Recommendation Agent (objection handling is
        its job), with the objection recorded to memory first so
        objection_handling reflects it.
        """
        self.memory.register_prospect_objection(objection_text)

        recommendation_input = {
            "user_objection": objection_text,
            "instruction": "The prospect has raised a new objection. Address it directly.",
        }
        recommendation_output = self.sales_recommendation_agent.run(self.memory, recommendation_input)
        self.memory.update_from_sales_recommendation(recommendation_output)
        self._log("sales_recommendation_followup", recommendation_input, recommendation_output)
        return recommendation_output

    def save_transcript(self, path: str) -> None:
        """Writes every agent turn logged so far (via _log) to a JSON file."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.transcript, f, indent=2)
