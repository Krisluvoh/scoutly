"""
Tests for web_research.py's pure parsing functions and the mock fetcher.

_parse_html and _parse_edgar_atom are tested directly against fixture
strings so these run entirely offline — no live HTTP or SEC EDGAR calls.
"""

from web_research import (
    MockFetcher,
    _extract_section,
    _find_primary_document_url,
    _is_safe_url,
    _parse_edgar_search_json,
    _parse_html,
    get_fetcher,
)

SAMPLE_HTML = """
<html>
<head><title>Acme Corp — Home</title></head>
<body>
<script>var x = 1;</script>
<p>Acme Corp builds widgets for enterprises.</p>
<a href="/about">About Us</a>
<a href="/leadership">Our Leadership</a>
<a href="/press">Press Releases</a>
<a href="https://external-site.com/leadership">External leadership link</a>
<a href="/random-page">Random Page</a>
</body>
</html>
"""

SAMPLE_EDGAR_SEARCH_JSON = {
    "hits": {
        "hits": [
            {
                "_source": {
                    "ciks": ["0001327567"],
                    "adsh": "0001327567-24-000123",
                    "form": "10-K",
                    "file_date": "2024-09-05",
                    "display_names": ["Acme Corp (ACME) (CIK 0001327567)"],
                }
            },
            {
                # Same accession number as above (a second document within the
                # same filing) — must be deduplicated, not counted twice.
                "_source": {
                    "ciks": ["0001327567"],
                    "adsh": "0001327567-24-000123",
                    "form": "10-K",
                    "file_date": "2024-09-05",
                    "display_names": ["Acme Corp (ACME) (CIK 0001327567)"],
                }
            },
        ]
    }
}


def test_parse_html_extracts_title_and_text():
    page = _parse_html(SAMPLE_HTML, "https://acme.com")
    assert page.title == "Acme Corp — Home"
    assert "Acme Corp builds widgets" in page.text
    assert "var x = 1" not in page.text


def test_parse_html_filters_links_to_keyword_allowlist_and_same_domain():
    page = _parse_html(SAMPLE_HTML, "https://acme.com")
    assert "https://acme.com/about" in page.links
    assert "https://acme.com/leadership" in page.links
    assert "https://acme.com/press" in page.links
    assert not any("external-site.com" in link for link in page.links)
    assert not any("random-page" in link for link in page.links)


def test_parse_edgar_search_json_extracts_and_dedupes_filings():
    filings = _parse_edgar_search_json(SAMPLE_EDGAR_SEARCH_JSON)
    assert len(filings) == 1
    assert filings[0].company_name == "Acme Corp (ACME) (CIK 0001327567)"
    assert filings[0].filing_date == "2024-09-05"
    assert filings[0].filing_url == (
        "https://www.sec.gov/Archives/edgar/data/1327567/000132756724000123/"
        "0001327567-24-000123-index.htm"
    )


def test_parse_edgar_search_json_returns_empty_list_when_no_hits():
    assert _parse_edgar_search_json({"hits": {"hits": []}}) == []
    assert _parse_edgar_search_json({}) == []


def test_mock_fetcher_returns_placeholder_content_without_network():
    page = MockFetcher().fetch_page("https://example-prospect.com")
    assert page.url == "https://example-prospect.com"
    assert page.text
    assert page.error is None
    assert page.links


def test_get_fetcher_factory():
    assert isinstance(get_fetcher("mock"), MockFetcher)


def test_is_safe_url_rejects_non_http_schemes():
    assert _is_safe_url("ftp://example.com") is False
    assert _is_safe_url("file:///etc/passwd") is False


def test_is_safe_url_rejects_loopback_and_private_hosts():
    assert _is_safe_url("http://localhost/") is False
    assert _is_safe_url("http://127.0.0.1/") is False
    assert _is_safe_url("http://192.168.1.1/") is False


SAMPLE_FILING_INDEX_HTML = """
<html><body>
<a href="/index.htm">SEC Home</a>
<a href="/ix?doc=/Archives/edgar/data/123/000012300024000001/acme-20240731.htm">acme-20240731.htm</a>
<a href="/Archives/edgar/data/123/000012300024000001/acmeex211subsidiaries.htm">acmeex211subsidiaries.htm</a>
</body></html>
"""

SAMPLE_FILING_INDEX_HTML_NO_IX = """
<html><body>
<a href="/index.htm">SEC Home</a>
<a href="/Archives/edgar/data/123/000012300024000001/acme-20240731.htm">acme-20240731.htm</a>
<a href="/Archives/edgar/data/123/000012300024000001/acmeex211subsidiaries.htm">acmeex211subsidiaries.htm</a>
</body></html>
"""

_SAMPLE_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/data/123/000012300024000001/0000123-24-000001-index.htm"
)


def test_find_primary_document_url_uses_ix_doc_wrapper_when_present():
    url = _find_primary_document_url(SAMPLE_FILING_INDEX_HTML, _SAMPLE_INDEX_URL)
    assert url == "https://www.sec.gov/Archives/edgar/data/123/000012300024000001/acme-20240731.htm"


def test_find_primary_document_url_falls_back_to_first_same_folder_htm():
    url = _find_primary_document_url(SAMPLE_FILING_INDEX_HTML_NO_IX, _SAMPLE_INDEX_URL)
    assert url == "https://www.sec.gov/Archives/edgar/data/123/000012300024000001/acme-20240731.htm"


def test_find_primary_document_url_returns_none_when_nothing_matches():
    assert _find_primary_document_url("<html><body>no links here</body></html>", _SAMPLE_INDEX_URL) is None


def test_extract_section_returns_text_after_last_header_match():
    text = (
        "Table of Contents Item 1A Risk Factors ... (page 12) "
        "Item 7 Management's Discussion ... (page 40) "
        "Item 1A Risk Factors Our business faces significant competition. "
        "Item 1B Unresolved Staff Comments None."
    )
    section = _extract_section(text, r"Item\s+1A\.?\s*Risk\s*Factors")
    assert "significant competition" in section
    assert "Unresolved Staff Comments" not in section


def test_extract_section_returns_empty_string_when_pattern_not_found():
    assert _extract_section("no relevant headers here", r"Item\s+1C\.?\s*Cybersecurity") == ""
