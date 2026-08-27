"""
streamlit_app.py
-----------------
Streamlit front end for Trendora, built for deployment on Streamlit
Community Cloud (free, and — unlike Hugging Face Spaces' free tier —
supports running real server-side Python with proper secrets management).

Wraps TrendoraOrchestrator in a small form-driven UI: a sales rep enters
their product, value proposition, target contact, and the prospect's
company/competitor URLs, and gets back a one-page account intelligence
brief. Streamlit reruns this whole script on every interaction, so the
orchestrator + memory for the current browser session live in
st.session_state rather than as local variables.

LLM provider defaults to Groq (free tier) via TRENDORA_PROVIDER /
GROQ_API_KEY. Page fetching defaults to real HTTP fetches via
TRENDORA_FETCH_MODE (set to "mock" for a fast, offline walkthrough). On
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
from memory import TrendoraMemory
from orchestrator import TrendoraOrchestrator
from web_research import get_fetcher

load_dotenv()

PROVIDER = os.environ.get("TRENDORA_PROVIDER", "groq")
FETCH_MODE = os.environ.get("TRENDORA_FETCH_MODE", "http")
SEC_EDGAR_CONTACT_EMAIL = os.environ.get("SEC_EDGAR_CONTACT_EMAIL", "capstone-project@example.com")

try:
    if "GROQ_API_KEY" in st.secrets and not os.environ.get("GROQ_API_KEY"):
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:  # noqa: BLE001 - no secrets.toml locally is expected, not an error
    pass


THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Jost:wght@300;400;500&display=swap');

:root {
    --tr-gold: #C6A15B;
    --tr-gold-soft: rgba(198, 161, 91, 0.35);
    --tr-ink: #ECE7DA;
    --tr-muted: #9B9587;
    --tr-panel: #17171A;
    --tr-bg: #0E0E10;
}

html, body, [class*="css"] { font-family: 'Jost', sans-serif; }

#MainMenu, footer, header { visibility: hidden; }

.block-container {
    max-width: 760px;
    padding-top: 3rem;
    padding-bottom: 4rem;
}

.tr-hero { text-align: center; margin-bottom: 2.5rem; }
.tr-hero .tr-mark {
    font-family: 'Cormorant Garamond', serif;
    font-size: 3rem;
    font-weight: 500;
    letter-spacing: 0.35em;
    color: var(--tr-ink);
    margin: 0;
    text-transform: uppercase;
}
.tr-hero .tr-rule {
    width: 64px;
    height: 1px;
    background: var(--tr-gold);
    margin: 0.9rem auto;
    border: none;
}
.tr-hero .tr-tagline {
    font-family: 'Jost', sans-serif;
    font-size: 0.78rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--tr-muted);
    margin: 0;
}
.tr-hero .tr-provider {
    font-size: 0.7rem;
    color: var(--tr-muted);
    margin-top: 0.6rem;
    letter-spacing: 0.08em;
}
.tr-hero .tr-provider b { color: var(--tr-gold); font-weight: 500; }

div[data-testid="stForm"] {
    background: var(--tr-panel);
    border: 1px solid var(--tr-gold-soft);
    border-radius: 2px;
    padding: 2rem 2rem 1.4rem 2rem;
}

label[data-testid="stWidgetLabel"] p {
    font-family: 'Jost', sans-serif;
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--tr-muted);
}

div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background: var(--tr-bg);
    border: 1px solid rgba(198, 161, 91, 0.25);
    border-radius: 2px;
    color: var(--tr-ink);
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color: var(--tr-gold);
    box-shadow: none;
}

div[data-testid="stFormSubmitButton"] button,
div[data-testid="stBaseButton-primary"] button {
    width: 100%;
    background: transparent;
    color: var(--tr-gold);
    border: 1px solid var(--tr-gold);
    border-radius: 2px;
    font-family: 'Jost', sans-serif;
    font-size: 0.76rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    padding: 0.6rem 0;
    transition: background 0.2s ease, color 0.2s ease;
}
div[data-testid="stFormSubmitButton"] button:hover {
    background: var(--tr-gold);
    color: var(--tr-bg);
}

div[data-testid="stDownloadButton"] button {
    width: 100%;
    background: transparent;
    color: var(--tr-gold);
    border: 1px solid var(--tr-gold-soft);
    border-radius: 2px;
    font-family: 'Jost', sans-serif;
    font-size: 0.7rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    padding: 0.5rem 0;
    transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease;
}
div[data-testid="stDownloadButton"] button:hover {
    background: var(--tr-gold);
    color: var(--tr-bg);
    border-color: var(--tr-gold);
}

.tr-panel {
    border: 1px solid rgba(198, 161, 91, 0.2);
    border-top: 2px solid var(--tr-gold);
    background: var(--tr-panel);
    padding: 1.6rem 1.8rem;
    margin-top: 1.6rem;
    border-radius: 2px;
}
.tr-panel .tr-label {
    font-family: 'Jost', sans-serif;
    font-size: 0.72rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--tr-gold);
    margin-bottom: 0.9rem;
}
.tr-panel .tr-row { margin-bottom: 0.55rem; font-size: 0.95rem; line-height: 1.5; }
.tr-panel .tr-row:last-child { margin-bottom: 0; }
.tr-panel .tr-row .tr-key {
    color: var(--tr-muted);
    font-size: 0.78rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-right: 0.4rem;
}
.tr-panel.tr-recommendation { border-top-color: var(--tr-gold); }
.tr-panel .tr-verdict {
    font-family: 'Cormorant Garamond', serif;
    font-style: italic;
    font-size: 1.3rem;
    color: var(--tr-ink);
    margin-bottom: 0.8rem;
}
.tr-panel a { color: var(--tr-gold); }

div[data-testid="stAlertContainer"] {
    background: rgba(198, 161, 91, 0.08) !important;
    border: 1px solid var(--tr-gold-soft) !important;
    border-radius: 2px !important;
}
div[data-testid="stAlertContainer"] p {
    color: var(--tr-ink) !important;
    font-family: 'Jost', sans-serif;
    font-size: 0.88rem;
}
div[data-testid="stAlertContainer"] svg { fill: var(--tr-gold) !important; }

.tr-divider {
    text-align: center;
    color: var(--tr-gold-soft);
    letter-spacing: 0.5em;
    margin: 2.4rem 0 1.6rem 0;
    font-size: 0.8rem;
}

.tr-loading {
    position: relative;
    text-align: center;
    margin-top: 1.2rem;
    padding: 0.6rem 0;
}
.tr-loading .tr-loading-label {
    font-family: 'Jost', sans-serif;
    font-size: 0.72rem;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--tr-gold);
    margin-bottom: 0.8rem;
}
.tr-loading .tr-loading-label .tr-dots span {
    opacity: 0;
    animation: tr-dot-fade 1.4s infinite;
}
.tr-loading .tr-loading-label .tr-dots span:nth-child(1) { animation-delay: 0s; }
.tr-loading .tr-loading-label .tr-dots span:nth-child(2) { animation-delay: 0.2s; }
.tr-loading .tr-loading-label .tr-dots span:nth-child(3) { animation-delay: 0.4s; }
.tr-loading .tr-loading-track {
    position: relative;
    width: 100%;
    height: 2px;
    background: rgba(198, 161, 91, 0.15);
    border-radius: 2px;
}
.tr-loading .tr-loading-fill {
    position: absolute;
    top: 0;
    left: -35%;
    height: 100%;
    width: 35%;
    background: linear-gradient(90deg, transparent, var(--tr-gold) 85%, var(--tr-ink) 100%);
    animation: tr-sweep 1.9s ease-in-out infinite;
}
.tr-loading .tr-loading-spark {
    position: absolute;
    top: 50%;
    right: -2px;
    width: 5px;
    height: 5px;
    background: var(--tr-ink);
    border-radius: 50%;
    transform: translate(50%, -50%);
    box-shadow: 0 0 6px 2px var(--tr-gold), 0 0 14px 5px var(--tr-gold-soft);
}
.tr-loading .tr-glitter {
    position: absolute;
    inset: 0;
    pointer-events: none;
}
.tr-loading .tr-glitter span {
    position: absolute;
    width: 2px;
    height: 2px;
    background: var(--tr-gold);
    border-radius: 50%;
    opacity: 0;
    box-shadow: 0 0 5px 1px var(--tr-gold-soft);
    animation: tr-twinkle 2.3s ease-in-out infinite;
}
.tr-loading .tr-glitter span:nth-child(1) { left: 12%; top: 4px;  animation-delay: 0s; }
.tr-loading .tr-glitter span:nth-child(2) { left: 28%; top: 30px; animation-delay: 0.5s; }
.tr-loading .tr-glitter span:nth-child(3) { left: 47%; top: 2px;  animation-delay: 1.05s; }
.tr-loading .tr-glitter span:nth-child(4) { left: 63%; top: 32px; animation-delay: 0.3s; }
.tr-loading .tr-glitter span:nth-child(5) { left: 80%; top: 6px;  animation-delay: 1.5s; }
.tr-loading .tr-glitter span:nth-child(6) { left: 91%; top: 28px; animation-delay: 0.85s; }
@keyframes tr-dot-fade {
    0%, 80%, 100% { opacity: 0; }
    40% { opacity: 1; }
}
@keyframes tr-sweep {
    0% { left: -35%; }
    100% { left: 100%; }
}
@keyframes tr-twinkle {
    0%, 100% { opacity: 0; transform: scale(0.3); }
    50% { opacity: 1; transform: scale(1); }
}
</style>
"""

_LOADING_HTML = """
<div class="tr-loading">
    <p class="tr-loading-label">{label}<span class="tr-dots">
        <span>.</span><span>.</span><span>.</span>
    </span></p>
    <div class="tr-loading-track">
        <div class="tr-loading-fill"><span class="tr-loading-spark"></span></div>
    </div>
    <div class="tr-glitter">
        <span></span><span></span><span></span><span></span><span></span><span></span>
    </div>
</div>
"""


def _build_orchestrator() -> tuple[TrendoraOrchestrator, str | None]:
    """Returns (orchestrator, warning). Falls back to a mock LLM if the provider
    errors out; the page-fetch layer is independent and always runs for real
    unless TRENDORA_FETCH_MODE=mock."""
    fetcher = get_fetcher(FETCH_MODE)
    try:
        client = get_client(PROVIDER)
        orchestrator = TrendoraOrchestrator(
            client, TrendoraMemory(account_id="web_guest"), fetcher, SEC_EDGAR_CONTACT_EMAIL
        )
        return orchestrator, None
    except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
        client = get_client("mock")
        orchestrator = TrendoraOrchestrator(
            client, TrendoraMemory(account_id="web_guest"), fetcher, SEC_EDGAR_CONTACT_EMAIL
        )
        warning = (
            f"Could not start the '{PROVIDER}' provider ({exc}). "
            "Falling back to mock LLM responses — set GROQ_API_KEY in this app's secrets to use a real model."
        )
        return orchestrator, warning


def _panel(label: str, rows: list[tuple[str, str]], extra_class: str = "") -> str:
    body = "".join(
        f'<div class="tr-row"><span class="tr-key">{key}</span>{value}</div>' for key, value in rows if value
    )
    return f'<div class="tr-panel {extra_class}"><div class="tr-label">{label}</div>{body}</div>'


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
        f'<div class="tr-panel tr-recommendation"><div class="tr-label">One-Page Account Brief</div>'
        f'<div class="tr-verdict">"{report.get("recommended_strategy")}"</div>'
        + "".join(
            f'<div class="tr-row"><span class="tr-key">{key}</span>{value}</div>'
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


_PDF_GOLD = (198, 161, 91)
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
    pdf.set_text_color(*_PDF_GOLD)
    pdf.cell(0, 8, _pdf_text(title.upper()), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*_PDF_GOLD)
    pdf.set_line_width(0.2)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(3)

    if verdict:
        pdf.set_font("Times", "BI", 13)
        pdf.set_text_color(*_PDF_INK)
        pdf.multi_cell(0, 7, _pdf_text(f'"{verdict}"'))
        pdf.ln(2)

    pdf.set_font("Times", "", 11)
    for key, value in rows:
        if not value:
            continue
        pdf.set_font("Times", "B", 9.5)
        pdf.set_text_color(*_PDF_MUTED)
        pdf.cell(0, 6, _pdf_text(key.upper()), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Times", "", 11)
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
    pdf.cell(0, 12, "T R E N D O R A", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Times", "I", 10)
    pdf.set_text_color(*_PDF_MUTED)
    pdf.cell(0, 6, "Account Intelligence Brief", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(2)

    pdf.set_draw_color(*_PDF_GOLD)
    pdf.set_line_width(0.4)
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


st.set_page_config(page_title="Trendora — Account Intelligence", page_icon="💎", layout="centered")
st.markdown(THEME_CSS, unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="tr-hero">
        <p class="tr-mark">Trendora</p>
        <hr class="tr-rule" />
        <p class="tr-tagline">AI-Powered Account Intelligence for B2B Sales Reps</p>
        <p class="tr-provider">Advised by <b>{PROVIDER}</b> · Fetching pages via <b>{FETCH_MODE}</b></p>
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
        "What Are You Selling", placeholder="e.g. Trendora Curated Sourcing"
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

    st.markdown('<div class="tr-divider">• • •</div>', unsafe_allow_html=True)
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
            f'<div class="tr-panel tr-recommendation"><div class="tr-label">Revised Approach</div>'
            f'<div class="tr-verdict">"{f.get("recommended_approach")}"</div>'
            + "".join(
                f'<div class="tr-row"><span class="tr-key">{key}</span>{value}</div>'
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
            file_name=f"trendora-{company_slug}-brief.pdf",
            mime="application/pdf",
        )
