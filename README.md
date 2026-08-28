# Scoutly — Multi-Agent B2B Account Intelligence Assistant (CAP 931 Capstone)

Scoutly helps a B2B sales rep research a prospective company before
outreach. Give it what you're selling, your value proposition, the target
company's URL, and its competitors' URLs, and five AI agents chain
together to produce a one-page account intelligence brief: company
strategy, leadership, press/compliance initiatives, competitive
positioning, a public-filing summary, a sourcing-strategy recommendation,
and a recommended approach — with real, clickable source links.

This was built for the Per Scholas CAP 931 capstone assignment ("Build a
Sales Agent Prototype Using Multi-Agent GPT Models"). It runs on Claude by
default, with OpenAI and Groq available as drop-in alternatives.

Setup and dependencies are managed with **[uv](https://docs.astral.sh/uv/)**.

## 1. Quick start

There are two ways to run Scoutly: the command-line demo, and a
browser-based version.

**Command line** (three scripted account-research scenarios, printed to the
terminal):

```bash
uv sync                  # installs everything from pyproject.toml / uv.lock
uv run main.py            # runs the 3-scenario demo — no API key or network needed (mock LLM + mock fetcher)
uv run pytest -q          # runs the test suite — also no API key or network needed
```

**Web UI** (a single browser form, built with Streamlit):

```bash
uv sync
uv run streamlit run streamlit_app.py
```

That opens a local page where you enter your product, value proposition,
target contact, and the prospect's company + competitor URLs, and get back
an Account Snapshot → Company Research → Competitive Landscape →
Recommended Sourcing Strategy → one-page Account Brief, plus a follow-up
box for logging a prospect's objection. Without an API key it falls back
to mock LLM responses (the page-fetch step still runs for real against
whatever URLs you enter, since that doesn't need a key).

<p align="center">
  <img src="docs/screenshots/web-ui-form.png" alt="Scoutly web UI: account research form" width="480">
  <br><em>The intake form</em>
</p>

<p align="center">
  <img src="docs/screenshots/web-ui-result.png" alt="Scoutly web UI: account research results" width="480">
  <br><em>Account Snapshot and Company Research results for one scenario</em>
</p>

To run either one against a real model, copy `.env.example` to `.env`, add
your API key(s), and set which provider to use:

```bash
cp .env.example .env
# edit .env: set SCOUTLY_PROVIDER=anthropic, ANTHROPIC_API_KEY=sk-ant-..., SCOUTLY_FETCH_MODE=http
uv run main.py
```

Supported LLM providers: `anthropic` (recommended default), `openai`, `groq`, `mock`.
Supported fetch modes: `http` (real page fetches), `mock` (offline canned pages).

## 2. Technologies used

| Technology | What it's doing here |
|---|---|
| **Python 3.12** | The language the whole project is written in. |
| **uv** | Installs dependencies and manages the virtual environment. Replaces `pip` + `requirements.txt` with one tool that also pins exact versions (`uv.lock`). |
| **Anthropic SDK (Claude)** | The default LLM provider — the model that reads research input and writes the JSON responses. |
| **OpenAI SDK** | An alternate LLM provider, kept for parity with the original assignment brief. |
| **langchain-groq** | An alternate, free-tier LLM provider (Groq), used through LangChain's `ChatGroq` wrapper since Groq doesn't have its own lightweight SDK. |
| **requests** | Fetches the target company's and competitors' actual web pages server-side. |
| **beautifulsoup4** | Parses fetched HTML into clean text plus a filtered list of leadership/press/careers subpage links. |
| **SEC EDGAR full-text search API** | Free, no-key lookup of a public company's real 10-K filings (accession numbers, dates, filing URLs) — satisfies the brief's "insight from public 10-K reports" requirement with verifiable data. |
| **Pydantic** | Defines the exact JSON shape each agent must return (`schemas.py`) and rejects anything that doesn't match, before it can break the next step in the pipeline. |
| **python-dotenv** | Loads API keys from a local `.env` file so they never get hardcoded or committed. |
| **Streamlit** | Builds the browser-based web UI (`streamlit_app.py`) and hosts it for free on Streamlit Community Cloud. |
| **pytest** | Runs the 37 automated tests. |
| **ruff** | Lints and formats the code (catches unused imports, style issues, common bugs). |

Everything above is declared in `pyproject.toml`, with exact versions
pinned in `uv.lock`. `requirements.txt` is a second copy of the same
dependency list, generated for Streamlit Cloud's build system, which reads
`requirements.txt` instead of `uv.lock`.

## 3. How it's put together

```
pyproject.toml / uv.lock   uv-managed dependencies
requirements.txt           dependency list for Streamlit Cloud's build (mirrors uv.lock)
main.py                    command-line demo entry point / scenario runner
streamlit_app.py           browser-based web UI, same pipeline as main.py
.streamlit/config.toml     Streamlit theme (dark, brass accent — refined, not boutique-luxury)
orchestrator.py            wires the five agents together, fetches pages, manages memory
memory.py                  ScoutlyMemory: cross-run contextual memory for one account
schemas.py                 pydantic schemas — one per agent's required JSON shape
llm_client.py              pluggable model backend: Anthropic / OpenAI / Groq / Mock
web_research.py            pluggable page-fetching backend: real HTTP+BeautifulSoup / Mock, plus SEC EDGAR lookup
sourcing_channels.py       reference data on real trend-item sourcing channels (wholesale/liquidation/etc)
agents/
  base_agent.py                 shared prompt-building, JSON parsing, retry, validation
  account_intake_agent.py       Agent 1 — structures the rep's product/company/competitor input
  company_research_agent.py     Agent 2 — extracts strategy/leadership/compliance/10-K from fetched pages
  competitor_agent.py           Agent 3 — extracts competitive positioning from fetched competitor pages
  sales_recommendation_agent.py Agent 4 — talking points, objections, approach, sourcing/margin recommendation
  report_agent.py               Agent 5 — assembles the one-page Account Intelligence Brief
tests/
  test_llm_client.py          provider factory + mock output shape (all 5 roles)
  test_web_research.py        HTML/EDGAR-JSON parsing (pure functions, no live network) + mock fetcher
  test_memory.py              memory update hooks, dedup, persistence
  test_agents.py               each agent in isolation, role-boundary checks
  test_orchestrator.py         full pipeline + objection-handling integration tests
docs/
  ASSIGNMENT_BRIEF.md            original capstone assignment, transcribed
  screenshots/                   web UI screenshots
examples/
  sample_run_output/             a committed mock run (transcripts + memory) so you can see output without running anything
```

Each agent sticks to its own lane: it has its own system prompt, only
returns JSON matching a fixed schema (see `schemas.py`), and that output
gets checked with pydantic before the orchestrator or the next agent trusts
it. All five agents read and write to a shared `ScoutlyMemory` object, so
by the time the Sales Recommendation Agent runs, it already knows what
Account Intake, Company Research, and Competitor research found — and if a
prospect raised an objection on a past research run for the same account,
that carries forward too.

The orchestrator is the only piece of code that talks to all five agents —
no agent calls another agent directly. It's also the only piece of code
that fetches web pages: real page content is retrieved *before* an agent
runs and handed to it as plain input data, so no agent ever reasons about a
bare URL from general knowledge. In standard agentic-system terms, this
makes it a **chain** rather than a model-driven agent with tools: the
sequence is fixed by the orchestrator, not decided by the model, which
fits fine since nothing here needs dynamic tool selection.

## 4. What it takes as input — mapped to the CAP 931 brief

**Example scenario used throughout this README and `main.py`:** Scoutly
is pitched as a curated trend-item **sourcing service** — "we find and
secure hard-to-find, high-margin inventory so your buying team doesn't
have to chase drops themselves" — sold to real boutique/retail companies
(the target company). This keeps the sales direction ordinary (a rep
selling a service to a prospect, not the reverse) while staying in the
trend-item/resale space the sourcing-strategy feature is built around —
see section 7 for how that resale-margin angle becomes a real feature, not
just flavor text.

The brief asks for: product name, target company URL, product category,
competitors, value proposition, and target customer. Scoutly's intake
form (`streamlit_app.py`) and `main.py` scenarios collect exactly these:

| CAP 931 input | Where it's collected |
|---|---|
| Product Name | `rep_product_name` |
| Company URL | `company_url` |
| Product Category (LLM infers if blank) | `product_category` — Account Intake Agent infers it when left blank |
| Competitors | `competitor_urls` (one or more) |
| Value Proposition | `value_proposition` |
| Target Customer | `target_customer_name` |

You can also send a follow-up prospect objection, which routes straight to
the Sales Recommendation Agent since handling objections is its job.

## 5. What it outputs — mapped to the CAP 931 brief

The brief asks for a comprehensive one-page report covering company
strategy, initiatives/press/compliance, competitive mentions, leadership
information, a public 10-K/financial summary, and action links. That's
exactly `AccountBriefOutput` (`schemas.py`), produced by the Report Agent:

| CAP 931 output requirement | Where it's produced |
|---|---|
| Company Strategy | `report.company_strategy` — Company Research Agent's `company_strategy`, condensed by the Report Agent |
| Sign-ups, press releases, key initiatives, regulatory compliance (GDPR/CCPA etc.) | `report.initiatives_and_compliance` — merged from Company Research's `key_initiatives` + `compliance_mentions` |
| Competitive Mentions | `report.competitive_mentions` — from the Competitor Agent's `notable_mentions` / `competitive_landscape` |
| Leadership Information (with quotes where available) | `report.leadership_information` — Company Research Agent's `leadership` list (name, title, quote/note), carried through unchanged |
| Product/Rating Summary from public 10-K reports | `report.financial_summary` — grounded in a real SEC EDGAR full-text-search lookup (`web_research.lookup_public_filings`); says "no public filings found" honestly for private companies |
| Action Links to source articles/press releases | `report.action_links` — every real URL an agent actually drew from, deduplicated |

Beyond the brief's required fields, `report.sourcing_recommendation` adds
one more: given the target company's apparent trend focus (from Company
Research), the Sales Recommendation Agent picks the best-fit sourcing
channel and named platforms from `sourcing_channels.py` — a small
reference table of real wholesale/liquidation/dropshipping/boutique/
category-specific sourcing options — with margin reasoning grounded in
that table's own notes, never invented.

Every agent turn also produces a small self-scored evaluation block:

```json
{
  "evaluation": {
    "relevance": "0-10",
    "clarity": "0-10",
    "engagement": "0-10",
    "deal_likelihood": "0-10"
  }
}
```

Full transcripts (every agent's input/output for each account) get saved
to `output/transcript_<account_id>.json`, and each account's memory gets
saved to `output/memory_<account_id>.json`. Both are generated at runtime
and git-ignored.

## 6. Which model, and why

By default this runs on **Claude** (`claude-sonnet-4-6`) through the
`anthropic` SDK. I picked Claude because it's reliably good at sticking to
a strict JSON schema — that's the biggest technical risk in this project,
since one stray sentence outside the JSON breaks the whole pipeline.

You can switch providers with `SCOUTLY_PROVIDER`:
- `openai` — GPT-4o-mini by default, via the `openai` SDK.
- `groq` — GPT-OSS 120B by default, via `langchain-groq`'s `ChatGroq`. A
  good free-tier option for prototyping, though Groq's free lineup changes
  often — see the challenges table below.
- `mock` — canned offline responses, no API calls at all. This is the
  default, so `uv run main.py` and `uv run pytest` both work out of the box
  with zero setup.

Independently, `SCOUTLY_FETCH_MODE` controls the page-fetching backend
(`web_research.py`):
- `http` — real `requests` GETs against the company/competitor URLs
  entered, parsed with BeautifulSoup. Default for the deployed web app.
- `mock` — canned offline page content, no network calls. Default for
  `main.py` and the test suite, so grading and CI stay free and reliable.

## 7. Optional enhancements implemented

| CAP 931 optional enhancement | How Scoutly implements it |
|---|---|
| Alert system for regulatory/product/hiring signals | `sales_recommendation.time_sensitive_signals` — the Sales Recommendation Agent flags anything worth acting on quickly (a leadership change, a hiring surge, a compliance deadline) directly in the brief, rather than a separate notification system a prototype has no way to actually deliver |
| Improved output strategy | The Report Agent exists specifically to synthesize four agents' output into one coherent one-pager instead of handing the rep four separate JSON blobs |
| Domain-specific value-add beyond the base brief | `sourcing_recommendation` (see section 5) — a real, table-grounded resale-channel/margin recommendation, not just generic sales advice |
| Deployment | Streamlit Community Cloud (see section 9) |

## 8. A guardrail built in on purpose

The assignment didn't ask for this, but the Sales Recommendation Agent is
explicitly instructed not to pressure a prospect who's raised a real
objection, and to address it plainly rather than talk past it. An agent
that just pushes "buy now" no matter what the prospect says isn't a very
trustworthy sales tool, so this felt worth building in even though it
wasn't spelled out in the brief.

## 9. Testing

```bash
uv run pytest -q
```

37 tests cover the LLM provider factory (all 5 agent roles' mock output
shapes), the page-fetching layer (HTML/EDGAR-JSON parsing as pure
functions, no live network calls), memory update/dedup/persistence, each
agent in isolation (schema validation, plus checks that no agent's output
leaks fields that belong to another role), and the full pipeline end to
end (all five agents running in sequence, memory updating correctly,
objection follow-ups routing to the right agent). Everything runs against
the mock LLM client and mock fetcher, so the whole suite is free and works
without internet access.

## 10. Security note: fetching user-supplied URLs

Because the app fetches company/competitor URLs a user types into a public
form, `web_research._is_safe_url()` blocks non-http(s) schemes and resolves
the hostname to reject loopback/private/link-local addresses before any
request is made — a basic SSRF guard, since a URL-fetching feature exposed
on a public deployment is otherwise a way to probe internal network
addresses from the server.

## 11. Timeline

- Architecture, schemas, memory model, mock client, pipeline wiring,
  provider integrations, and initial test suite for the five-agent
  account-research pipeline.
- Added the real page-fetching layer (`web_research.py`, `requests` +
  BeautifulSoup) and the free SEC EDGAR full-text-search lookup, so
  research is grounded in actually-retrieved public information instead of
  an LLM guessing about a URL it never saw.
- Added the table-grounded sourcing-strategy recommendation
  (`sourcing_recommendation`, `sourcing_channels.py`) so the resale-margin
  angle became a real, differentiated feature rather than generic sales
  advice.
- Split into its own standalone repository under the name Scoutly, with a
  full visual redesign to a clean B2B SaaS look.
- Refined the visual identity further into a quieter, high-end look —
  deep charcoal palette, serif display type, muted brass accent — to
  better match the boutique/luxury retail clientele Scoutly's example
  scenarios target, without reverting to the earlier boutique-concierge
  styling's sparkle effects.

## 12. Problems I ran into, and how I fixed them

| Problem | Fix |
|---|---|
| Models sometimes wrap JSON in prose or code fences even when told not to | `BaseAgent._extract_json` strips that out and retries once with a corrective message before giving up |
| Agents drifting into another agent's job over a longer research run | Each system prompt states its role boundary twice, and `tests/test_agents.py` checks directly that no cross-role fields leak through |
| The Report Agent's own prompt describes handing off from "the Company Research Agent" and "the Competitor Agent" by name, which broke `MockClient`'s naive substring-based role detection (it matched the *first* agent name mentioned, not the agent actually running) | Switched `MockClient.generate` to match only the opening "You are the `<Role>` Agent" sentence via regex instead of scanning the whole prompt for any agent name |
| SEC EDGAR's legacy `browse-edgar` atom endpoint returns zero entries for a plain company-name search (it only returns filing entries for an exact single-CIK match) | Switched to EDGAR's full-text-search JSON API (`efts.sec.gov`), which matches by company name against real filed documents and returns genuine accession numbers/dates/URLs — verified live against Palo Alto Networks' real 10-K filings |
| A URL-fetching feature on a public form is a potential SSRF vector | Added `_is_safe_url()`: blocks non-http(s) schemes and resolves+rejects private/loopback/link-local hostnames before fetching |
| Needing to test and demo without burning API credits, requiring a key, or depending on live network access | `MockClient` + `MockFetcher` produce schema-valid fixture data for offline runs and the whole test suite |
| Wanting pinned, reproducible dependencies instead of a loose `requirements.txt` | Switched to `uv init` / `uv add`, which gives you `pyproject.toml` plus a fully pinned `uv.lock` |
| Hugging Face Spaces turned out to require a paid plan for anything that runs real Python (Gradio/Docker); the free tier is Static-only, which can't call an API without exposing the key in the browser | Built the web UI in Streamlit instead and deployed to Streamlit Community Cloud, which is free and has real server-side secrets |
| The Groq model this project defaulted to got discontinued after deployment, which only showed up as a `groq.NotFoundError` once the app was live | Swapped to `openai/gpt-oss-120b`, Groq's flagship production chat model — Groq's free-tier lineup turns over fast enough that this default may need to change again; check `console.groq.com/docs/models` for the current production list |
| `st.secrets` raises an exception instead of just returning nothing when there's no `secrets.toml` file, which crashed the app for anyone running it locally without Streamlit Cloud secrets configured | Wrapped that check in a try/except so a missing secrets file is treated as "no key yet," not a crash |

## 13. Requirements coverage

Scoutly meets the full scope of the CAP 931 brief:

| Area | Status | Details |
|---|---|---|
| Inputs (product, company URL, category, competitors, value prop, target customer) | ✅ | Section 4 |
| LLM model selection & prompt engineering (5 distinct agent roles) | ✅ | Sections 3, 6 |
| Memory retention across research runs | ✅ | `memory.py`, section 3 |
| Data integration (real page fetches + real SEC EDGAR filings) | ✅ | Section 5, `web_research.py` |
| Outputs (strategy, initiatives/compliance, competitive mentions, leadership, 10-K summary, action links) | ✅ | Section 5 |
| Optional enhancements (alert system, output-strategy synthesis, sourcing/margin recommendation) | ✅ | Section 7 |
| Production deployment considerations | ✅ | Section 14 |
| Documentation (setup, time management, challenges, requirements, system outputs) | ✅ | This README + `examples/sample_run_output/` + `docs/screenshots/` |

The one brief item intentionally not implemented is the optional
"upload a proprietary internal sheet" input — the brief marks it optional,
and every other input path already covers the required data.

## 14. If this went to production

- **Swappable LLM providers**: switching between Anthropic/OpenAI/Groq/mock is one factory call or one environment variable.
- **Swappable fetch backend**: same pattern for the page-fetching layer (`web_research.get_fetcher`), so a production deployment could swap in a headless-browser fetcher for JS-heavy sites without touching agent code.
- **Schema enforcement**: pydantic catches any drift in the model's output before it reaches a user or the next agent.
- **Memory**: right now it's just JSON files — fine for a prototype, but a real deployment would use an actual account/CRM database.
- **Retries**: currently one corrective re-prompt if the model messes up the JSON. Production would need real exponential backoff and rate-limit handling — for both the LLM calls and the page fetches (SEC EDGAR especially expects well-behaved, rate-limited traffic).
- **Observability**: transcripts are saved per account already; in production these would feed into structured logging so the eval scores could actually be monitored.
- **Cost control**: mock mode is already fully separate from paid inference and live fetches, so tests, CI, and grading never touch API quota or the network.
- **Reproducibility**: `uv.lock` pins the exact dependency graph, so `uv sync` gives you the same environment anywhere.
