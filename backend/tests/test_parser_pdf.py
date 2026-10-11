"""PDF parsing stays functional with the supported PyMuPDF import."""

import pymupdf
import pytest

from app.services.parser import DocumentParser


@pytest.mark.parametrize("source", ["bytes", "file"])
def test_pdf_text_metadata_and_page_provenance(source, tmp_path):
    with pymupdf.open() as document:
        document.set_metadata({"title": "Synthetic compliance source"})
        document.new_page().insert_text((72, 72), "Informational preamble.")
        document.new_page().insert_text((72, 72), "The bank shall review capital daily.")
        content = document.tobytes()

    parser = DocumentParser()
    if source == "bytes":
        parsed = parser.parse_pdf_bytes(content)
    else:
        path = tmp_path / "source.pdf"
        path.write_bytes(content)
        parsed = parser.parse_pdf(str(path))

    assert parsed.metadata["page_count"] == 2
    assert parsed.metadata["title"] == "Synthetic compliance source"
    assert "[PAGE 2]" in parsed.raw_text
    assert "shall review capital daily" in parsed.pages[1]
    chunks = parser.chunk_document(parsed)
    assert next(chunk for chunk in chunks if "shall review" in chunk.text).page_number == 2
