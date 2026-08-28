"""
streamlit_app.py
-----------------
Streamlit front end for Scoutly, built for deployment on Streamlit
Community Cloud (free, and — unlike Hugging Face Spaces' free tier —
supports running real server-side Python with proper secrets management).

Wraps ScoutlyOrchestrator in a small form-driven UI: a sales rep enters
their product, value proposition, target contact, and the prospect's
company/competitor URLs, and gets back a one-page account intelligence
brief. Streamlit reruns this whole script on every interaction, so the
orchestrator + memory for the current browser session live in
st.session_state rather than as local variables.

LLM provider defaults to Groq (free tier) via SCOUTLY_PROVIDER /
GROQ_API_KEY. Page fetching defaults to real HTTP fetches via
SCOUTLY_FETCH_MODE (set to "mock" for a fast, offline walkthrough). On
Streamlit Cloud, set secrets in the app's Settings -> Secrets; they're read
from st.secrets there. Locally, it falls back to a .env file. Falls back to
the mock LLM client if no key is configured, so the app still loads and is
explorable without one — the page-fetch step still runs for real either way.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv
from fpdf import FPDF

from llm_client import get_client
from memory import ScoutlyMemory
from orchestrator import ScoutlyOrchestrator
from web_research import get_fetcher

load_dotenv()

PROVIDER = os.environ.get("SCOUTLY_PROVIDER", "groq")
FETCH_MODE = os.environ.get("SCOUTLY_FETCH_MODE", "http")
SEC_EDGAR_CONTACT_EMAIL = os.environ.get("SEC_EDGAR_CONTACT_EMAIL", "capstone-project@example.com")

try:
    if "GROQ_API_KEY" in st.secrets and not os.environ.get("GROQ_API_KEY"):
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:  # noqa: BLE001 - no secrets.toml locally is expected, not an error
    pass


THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --sc-accent: #B8955C;
    --sc-accent-hover: #A8823C;
    --sc-accent-soft: rgba(184, 149, 92, 0.12);
    --sc-ink: #F1EEE7;
    --sc-muted: #9B9587;
    --sc-panel: #17171A;
    --sc-bg: #0B0B0C;
    --sc-border: rgba(184, 149, 92, 0.22);
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

#MainMenu, footer, header { visibility: hidden; }

.stApp { background: var(--sc-bg); }

.block-container {
    max-width: 760px;
    padding-top: 3rem;
    padding-bottom: 4rem;
}

.sc-hero { text-align: center; margin-bottom: 2.5rem; }
.sc-hero .sc-mark {
    font-family: 'Playfair Display', serif;
    font-size: 2.6rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    color: var(--sc-ink);
    margin: 0;
}
.sc-hero .sc-tagline {
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--sc-muted);
    margin: 0.6rem 0 0 0;
}
.sc-hero .sc-provider {
    font-size: 0.78rem;
    color: var(--sc-muted);
    margin-top: 0.6rem;
}
.sc-hero .sc-provider b { color: var(--sc-accent); font-weight: 600; }

div[data-testid="stForm"] {
    background: var(--sc-panel);
    border: 1px solid var(--sc-border);
    border-radius: 6px;
    padding: 2rem 2rem 1.4rem 2rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
}

label[data-testid="stWidgetLabel"] p {
    font-family: 'Inter', sans-serif;
    font-size: 0.76rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--sc-muted);
}

div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background: var(--sc-bg);
    border: 1px solid var(--sc-border);
    border-radius: 4px;
    color: var(--sc-ink);
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color: var(--sc-accent);
    box-shadow: 0 0 0 3px var(--sc-accent-soft);
}

div[data-testid="stFormSubmitButton"] button,
div[data-testid="stBaseButton-primary"] button {
    width: 100%;
    background: var(--sc-accent);
    color: #16140F;
    border: 1px solid var(--sc-accent);
    border-radius: 4px;
    font-family: 'Inter', sans-serif;
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 0.6rem 0;
    transition: background 0.15s ease, border-color 0.15s ease;
}
div[data-testid="stFormSubmitButton"] button:hover {
    background: var(--sc-accent-hover);
    border-color: var(--sc-accent-hover);
}

div[data-testid="stDownloadButton"] button {
    width: 100%;
    background: transparent;
    color: var(--sc-accent);
    border: 1px solid var(--sc-accent);
    border-radius: 4px;
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 0.55rem 0;
    transition: background 0.15s ease, color 0.15s ease;
}
div[data-testid="stDownloadButton"] button:hover {
    background: var(--sc-accent-soft);
}

.sc-panel {
    border: 1px solid var(--sc-border);
    border-top: 2px solid var(--sc-accent);
    background: var(--sc-panel);
    padding: 1.6rem 1.8rem;
    margin-top: 1.4rem;
    border-radius: 6px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}
.sc-panel .sc-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--sc-accent);
    margin-bottom: 0.9rem;
}
.sc-panel .sc-row { margin-bottom: 0.55rem; font-size: 0.95rem; line-height: 1.5; color: var(--sc-ink); }
.sc-panel .sc-row:last-child { margin-bottom: 0; }
.sc-panel .sc-row .sc-key {
    color: var(--sc-muted);
    font-size: 0.76rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    font-weight: 600;
    margin-right: 0.4rem;
}
.sc-panel .sc-verdict {
    font-family: 'Playfair Display', serif;
    font-style: italic;
    font-weight: 600;
    font-size: 1.35rem;
    color: var(--sc-ink);
    margin-bottom: 0.8rem;
}
.sc-panel a { color: var(--sc-accent); }

div[data-testid="stAlertContainer"] {
    background: var(--sc-accent-soft) !important;
    border: 1px solid var(--sc-border) !important;
    border-radius: 4px !important;
}
div[data-testid="stAlertContainer"] p {
    color: var(--sc-ink) !important;
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem;
}
div[data-testid="stAlertContainer"] svg { fill: var(--sc-accent) !important; }

.sc-divider {
    text-align: center;
    color: var(--sc-border);
    letter-spacing: 0.4em;
    margin: 2.2rem 0 1.4rem 0;
    font-size: 0.8rem;
}

.sc-loading {
    position: relative;
    text-align: center;
    margin-top: 1.2rem;
    padding: 0.6rem 0;
}
.sc-loading .sc-loading-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.76rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--sc-accent);
    margin-bottom: 0.8rem;
}
.sc-loading .sc-loading-label .sc-dots span {
    opacity: 0;
    animation: sc-dot-fade 1.4s infinite;
}
.sc-loading .sc-loading-label .sc-dots span:nth-child(1) { animation-delay: 0s; }
.sc-loading .sc-loading-label .sc-dots span:nth-child(2) { animation-delay: 0.2s; }
.sc-loading .sc-loading-label .sc-dots span:nth-child(3) { animation-delay: 0.4s; }
.sc-loading .sc-loading-track {
    position: relative;
    width: 100%;
    height: 2px;
    background: var(--sc-border);
    border-radius: 2px;
    overflow: hidden;
}
.sc-loading .sc-loading-fill {
    position: absolute;
    top: 0;
    left: -35%;
    height: 100%;
    width: 35%;
    background: var(--sc-accent);
    border-radius: 2px;
    animation: sc-sweep 1.6s ease-in-out infinite;
}
@keyframes sc-dot-fade {
    0%, 80%, 100% { opacity: 0; }
    40% { opacity: 1; }
}
@keyframes sc-sweep {
    0% { left: -35%; }
    100% { left: 100%; }
}
</style>
"""

_LOADING_HTML = """
<div class="sc-loading">
    <p class="sc-loading-label">{label}<span class="sc-dots">
        <span>.</span><span>.</span><span>.</span>
    </span></p>
    <div class="sc-loading-track">
        <div class="sc-loading-fill"></div>
    </div>
</div>
"""


def _build_orchestrator() -> tuple[ScoutlyOrchestrator, str | None]:
    """Returns (orchestrator, warning). Falls back to a mock LLM if the provider
    errors out; the page-fetch layer is independent and always runs for real
    unless SCOUTLY_FETCH_MODE=mock."""
    fetcher = get_fetcher(FETCH_MODE)
    try:
        client = get_client(PROVIDER)
        orchestrator = ScoutlyOrchestrator(
            client, ScoutlyMemory(account_id="web_guest"), fetcher, SEC_EDGAR_CONTACT_EMAIL
        )
        return orchestrator, None
    except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
        client = get_client("mock")
        orchestrator = ScoutlyOrchestrator(
            client, ScoutlyMemory(account_id="web_guest"), fetcher, SEC_EDGAR_CONTACT_EMAIL
        )
        warning = (
            f"Could not start the '{PROVIDER}' provider ({exc}). "
            "Falling back to mock LLM responses — set GROQ_API_KEY in this app's secrets to use a real model."
        )
        return orchestrator, warning


def _panel(label: str, rows: list[tuple[str, str]], extra_class: str = "") -> str:
    body = "".join(
        f'<div class="sc-row"><span class="sc-key">{key}</span>{value}</div>' for key, value in rows if value
    )
    return f'<div class="sc-panel {extra_class}"><div class="sc-label">{label}</div>{body}</div>'


def _links_html(urls: list[str]) -> str:
    return "<br>".join(f'<a href="{u}" target="_blank">{u}</a>' for u in urls) if urls else "—"


def _render_result(result: dict) -> None:
    intake = result["account_intake"]
    research = result["company_research"]
    competitor = result["competitor"]
    rec = result["sales_recommendation"]
    report = result["report"]

    st.markdown(
        _panel(
            "Account Snapshot",
            [
                ("Selling", intake.get("rep_product_name")),
                ("Category", intake.get("product_category")),
                ("Target contact", intake.get("target_customer_name")),
                ("Research priorities", ", ".join(intake.get("research_priorities") or []) or "—"),
            ],
        ),
        unsafe_allow_html=True,
    )

    leadership = ", ".join(
        f"{p.get('name')} ({p.get('title')})" for p in research.get("leadership", []) if p.get("name")
    )
    st.markdown(
        _panel(
            "Company Research",
            [
                ("Strategy", research.get("company_strategy")),
                ("Key initiatives", ", ".join(research.get("key_initiatives") or []) or "—"),
                ("Leadership", leadership or "—"),
                ("Financials", research.get("financial_summary")),
                ("Confidence", research.get("confidence")),
            ],
        ),
        unsafe_allow_html=True,
    )

    st.markdown(
        _panel(
            "Competitive Landscape",
            [
                ("Landscape", competitor.get("competitive_landscape")),
                ("Differentiation angle", competitor.get("differentiation_angle")),
            ],
        ),
        unsafe_allow_html=True,
    )

    sourcing = report.get("sourcing_recommendation") or rec.get("sourcing_recommendation")
    if sourcing:
        st.markdown(
            _panel(
                "Recommended Sourcing Strategy",
                [
                    ("Channel", sourcing.get("channel_type")),
                    ("Platforms", ", ".join(sourcing.get("recommended_platforms") or []) or "—"),
                    ("Margin notes", sourcing.get("margin_notes")),
                ],
            ),
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="sc-panel"><div class="sc-label">One-Page Account Brief</div>'
        f'<div class="sc-verdict">"{report.get("recommended_strategy")}"</div>'
        + "".join(
            f'<div class="sc-row"><span class="sc-key">{key}</span>{value}</div>'
            for key, value in [
                ("Company strategy", report.get("company_strategy")),
                (
                    "Initiatives & compliance",
                    ", ".join(report.get("initiatives_and_compliance") or []) or None,
                ),
                ("Competitive mentions", ", ".join(report.get("competitive_mentions") or []) or None),
                ("Financials", report.get("financial_summary")),
                ("Next steps", rec.get("next_steps")),
                ("Action links", _links_html(report.get("action_links") or [])),
            ]
            if value
        )
        + "</div>",
        unsafe_allow_html=True,
    )


_PDF_ACCENT = (168, 130, 60)
_PDF_INK = (30, 28, 24)
_PDF_MUTED = (120, 112, 96)

# fpdf2's core Times font only encodes latin-1; real LLM output routinely uses
# smart quotes, em/en dashes, and ellipses that latin-1 can't represent, which
# raises rather than silently dropping. Normalize to ASCII lookalikes first, then
# replace anything that still doesn't fit instead of crashing the download.
_PDF_CHAR_MAP = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "…": "...",
        "•": "-",
        " ": " ",
    }
)


def _pdf_text(value: object) -> str:
    text = str(value).translate(_PDF_CHAR_MAP)
    return text.encode("latin-1", "replace").decode("latin-1")


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "account"


def _pdf_section(pdf: FPDF, title: str, rows: list[tuple[str, str]], verdict: str | None = None) -> None:
    pdf.set_font("Times", "B", 12)
    pdf.set_text_color(*_PDF_ACCENT)
    pdf.cell(0, 8, _pdf_text(title.upper()), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*_PDF_ACCENT)
    pdf.set_line_width(0.4)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(3)

    if verdict:
        pdf.set_font("Times", "BI", 12)
        pdf.set_text_color(*_PDF_INK)
        pdf.multi_cell(0, 7, _pdf_text(f'"{verdict}"'))
        pdf.ln(2)

    pdf.set_font("Times", "", 10.5)
    for key, value in rows:
        if not value:
            continue
        pdf.set_font("Times", "B", 9)
        pdf.set_text_color(*_PDF_MUTED)
        pdf.cell(0, 6, _pdf_text(key.upper()), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Times", "", 10.5)
        pdf.set_text_color(*_PDF_INK)
        pdf.multi_cell(0, 6, _pdf_text(value))
        pdf.ln(1)
    pdf.ln(4)


def _build_pdf(company_url: str, result: dict, followup: dict | None = None) -> bytes:
    report = result["report"]
    rec = result["sales_recommendation"]

    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(20, 20, 20)
    pdf.add_page()

    pdf.set_font("Times", "B", 22)
    pdf.set_text_color(*_PDF_INK)
    pdf.cell(0, 12, "S C O U T L Y", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Times", "I", 10)
    pdf.set_text_color(*_PDF_MUTED)
    pdf.cell(0, 6, "Account Intelligence Brief", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(2)

    pdf.set_draw_color(*_PDF_ACCENT)
    pdf.set_line_width(0.6)
    mid = pdf.w / 2
    pdf.line(mid - 15, pdf.get_y(), mid + 15, pdf.get_y())
    pdf.ln(8)

    pdf.set_font("Times", "", 10)
    pdf.set_text_color(*_PDF_MUTED)
    pdf.cell(0, 6, _pdf_text(f"Target Account: {company_url}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Prepared {datetime.now().strftime('%B %d, %Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    _pdf_section(
        pdf,
        "Company Strategy",
        [
            ("Initiatives & compliance", ", ".join(report.get("initiatives_and_compliance") or []) or None),
            ("Financial summary", report.get("financial_summary")),
        ],
        verdict=report.get("company_strategy"),
    )
    leadership_text = "; ".join(
        f"{p.get('name')} ({p.get('title')}) — {p.get('quote_or_note')}".strip(" —")
        for p in report.get("leadership_information", [])
        if p.get("name")
    )
    _pdf_section(
        pdf,
        "Leadership Information",
        [("Key leaders", leadership_text or None)],
    )
    _pdf_section(
        pdf,
        "Competitive Mentions",
        [("Notable mentions", ", ".join(report.get("competitive_mentions") or []) or None)],
    )
    sourcing = report.get("sourcing_recommendation") or rec.get("sourcing_recommendation")
    if sourcing:
        _pdf_section(
            pdf,
            "Recommended Sourcing Strategy",
            [
                ("Channel", sourcing.get("channel_type")),
                ("Platforms", ", ".join(sourcing.get("recommended_platforms") or []) or None),
                ("Margin notes", sourcing.get("margin_notes")),
            ],
        )
    _pdf_section(
        pdf,
        "Recommended Strategy",
        [("Next steps", rec.get("next_steps"))],
        verdict=report.get("recommended_strategy"),
    )
    _pdf_section(
        pdf,
        "Action Links",
        [("Sources used", "\n".join(report.get("action_links") or []) or None)],
    )

    if followup:
        _pdf_section(
            pdf,
            "Revised Counsel",
            [
                ("Addressing the objection", followup.get("objection_handling")),
                ("Next steps", followup.get("next_steps")),
            ],
            verdict=followup.get("recommended_approach"),
        )

    return bytes(pdf.output())


st.set_page_config(page_title="Scoutly — Account Intelligence", page_icon="🧭", layout="centered")
st.markdown(THEME_CSS, unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="sc-hero">
        <p class="sc-mark">Scoutly</p>
        <p class="sc-tagline">Account intelligence for B2B sales reps</p>
        <p class="sc-provider">Advised by <b>{PROVIDER}</b> · Fetching pages via <b>{FETCH_MODE}</b></p>
    </div>
    """,
    unsafe_allow_html=True,
)

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = None
    st.session_state.company_url = None
    st.session_state.result = None
    st.session_state.warning = None
    st.session_state.followup = None

with st.form("intake_form"):
    rep_product_name = st.text_input(
        "What Are You Selling", placeholder="e.g. Scoutly Curated Sourcing"
    )
    value_proposition = st.text_area(
        "Value Proposition",
        placeholder="e.g. We find and secure hard-to-find trend inventory so your buyers don't have to",
    )
    target_customer_name = st.text_input("Target Customer / Role", placeholder="e.g. Head Buyer")
    product_category = st.text_input(
        "Product Category (optional)", placeholder="Leave blank to let the agent infer it"
    )
    company_url = st.text_input("Target Company URL", placeholder="https://www.example-boutique-retailer.com")
    competitor_urls_raw = st.text_area(
        "Competitor URLs (one per line)",
        placeholder="https://www.retail-competitor-a.com\nhttps://www.retail-competitor-b.com",
    )
    submitted = st.form_submit_button("Research This Account")

if submitted:
    competitor_urls = [u.strip() for u in competitor_urls_raw.splitlines() if u.strip()]
    if not rep_product_name.strip() or not value_proposition.strip() or not company_url.strip():
        st.warning("Enter at least what you're selling, your value proposition, and the target company URL.")
    else:
        loading = st.empty()
        loading.markdown(_LOADING_HTML.format(label="Researching Account"), unsafe_allow_html=True)
        time.sleep(0.35)  # guarantee the widget paints before a fast response clears it
        orchestrator, warning = _build_orchestrator()
        result = orchestrator.run_account_brief(
            rep_product_name=rep_product_name,
            value_proposition=value_proposition,
            target_customer_name=target_customer_name,
            company_url=company_url,
            competitor_urls=competitor_urls,
            product_category=product_category,
        )
        loading.empty()
        st.session_state.orchestrator = orchestrator
        st.session_state.company_url = company_url
        st.session_state.result = result
        st.session_state.warning = warning
        st.session_state.followup = None

if st.session_state.warning:
    st.warning(st.session_state.warning)

if st.session_state.result:
    _render_result(st.session_state.result)

    st.markdown('<div class="sc-divider">• • •</div>', unsafe_allow_html=True)
    with st.form("objection_form"):
        objection_text = st.text_input(
            "Prospect Pushed Back?",
            placeholder="e.g. We already have an informal relationship with a few boutique suppliers.",
        )
        objection_submitted = st.form_submit_button("Log Their Objection")

    if objection_submitted:
        if not objection_text.strip():
            st.warning("Enter the objection first.")
        else:
            loading = st.empty()
            loading.markdown(_LOADING_HTML.format(label="Reconsidering Approach"), unsafe_allow_html=True)
            time.sleep(0.35)  # guarantee the widget paints before a fast response clears it
            followup = st.session_state.orchestrator.handle_prospect_objection(objection_text)
            loading.empty()
            st.session_state.followup = followup

    if st.session_state.followup:
        f = st.session_state.followup
        st.markdown(
            f'<div class="sc-panel"><div class="sc-label">Revised Approach</div>'
            f'<div class="sc-verdict">"{f.get("recommended_approach")}"</div>'
            + "".join(
                f'<div class="sc-row"><span class="sc-key">{key}</span>{value}</div>'
                for key, value in [
                    ("Addressing the objection", f.get("objection_handling")),
                    ("Next steps", f.get("next_steps")),
                ]
                if value
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    pdf_bytes = _build_pdf(st.session_state.company_url, st.session_state.result, st.session_state.followup)
    company_slug = _slugify(urlparse(st.session_state.company_url).netloc or st.session_state.company_url)
    _, pdf_col, _ = st.columns([1, 2, 1])
    with pdf_col:
        st.download_button(
            "Download Account Brief (PDF)",
            data=pdf_bytes,
            file_name=f"scoutly-{company_slug}-brief.pdf",
            mime="application/pdf",
        )
