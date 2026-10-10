from types import SimpleNamespace

from app.api.endpoints.evaluation import demo_source_pages


def test_synthetic_demo_pages_preserve_quote_and_page_context():
    obligation = SimpleNamespace(source_page=12, source_section="Section 49", source_text_snippet="Synthetic requirement")
    pages = demo_source_pages("Section 49: Synthetic requirement", [obligation])
    assert len(pages) == 12
    assert "Synthetic requirement" in pages[11]


def test_synthetic_demo_pages_reject_unverified_quotes():
    obligation = SimpleNamespace(source_page=1, source_section="Section 49", source_text_snippet="Invented quote")
    assert demo_source_pages("Synthetic requirement", [obligation]) == []
