import re
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

import fitz


INJECTION_PATTERNS = [
    r"ignore\s+(?:previous|above|all)\s+instructions",
    r"forget\s+(?:everything|above|previous)",
    r"system\s*:\s*you\s+are",
    r"assistant\s*:\s*you\s+are",
    r"<\s*system\s*>",
    r"<\s*assistant\s*>",
    r"role\s*:\s*system",
    r"role\s*:\s*assistant",
    r"###\s*instruction",
    r"###\s*system",
    r"```\s*system",
    r"```\s*assistant",
    r"disregard\s+(?:the\s+)?(?:above|previous)",
    r"override\s+(?:the\s+)?(?:above|previous)",
    r"new\s+instructions?",
    r"updated\s+instructions?",
    r"secret\s+(?:key|token|password)",
    r"api\s+key",
    r"authorization\s*:\s*bearer",
    r"execute\s+(?:code|command|script)",
    r"run\s+(?:code|command|script)",
    r"eval\s*\(",
    r"exec\s*\(",
    r"import\s+os",
    r"subprocess",
    r"__import__",
    r"getattr\s*\(",
    r"setattr\s*\(",
]


@dataclass
class ParsedDocument:
    raw_text: str
    pages: List[str]
    metadata: dict
    injection_warnings: List[str]
    sanitized_text: str


@dataclass
class DocumentChunk:
    text: str
    page_number: int
    section: Optional[str] = None
    char_start: int = 0
    char_end: int = 0


class DocumentParser:
    def __init__(self, max_chunk_size: int = 2000, chunk_overlap: int = 200):
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

    def parse_pdf(self, file_path: str) -> ParsedDocument:
        doc = fitz.open(file_path)
        return self._parse_pdf_document(doc)

    def parse_pdf_bytes(self, content: bytes) -> ParsedDocument:
        doc = fitz.open(stream=content, filetype="pdf")
        return self._parse_pdf_document(doc)

    def _parse_pdf_document(self, doc) -> ParsedDocument:
        pages = []
        full_text = []
        metadata = {
            "page_count": len(doc),
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "creator": doc.metadata.get("creator", ""),
            "producer": doc.metadata.get("producer", ""),
            "creation_date": doc.metadata.get("creationDate", ""),
            "modification_date": doc.metadata.get("modDate", ""),
        }

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            pages.append(text)
            full_text.append(f"[PAGE {page_num + 1}]\n{text}")

        raw_text = "\n\n".join(full_text)
        injection_warnings = self._detect_injection(raw_text)
        sanitized_text = self._sanitize(raw_text)

        return ParsedDocument(
            raw_text=raw_text,
            pages=pages,
            metadata=metadata,
            injection_warnings=injection_warnings,
            sanitized_text=sanitized_text,
        )

    def parse_text(self, file_path: str) -> ParsedDocument:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        return self.parse_text_content(raw_text)

    def parse_text_content(self, raw_text: str) -> ParsedDocument:

        injection_warnings = self._detect_injection(raw_text)
        sanitized_text = self._sanitize(raw_text)

        pages = [raw_text]
        metadata = {"page_count": 1}

        return ParsedDocument(
            raw_text=raw_text,
            pages=pages,
            metadata=metadata,
            injection_warnings=injection_warnings,
            sanitized_text=sanitized_text,
        )

    def _detect_injection(self, text: str) -> List[str]:
        warnings = []
        text_lower = text.lower()

        for pattern in INJECTION_PATTERNS:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].replace("\n", " ")
                warnings.append(f"Potential prompt injection at position {match.start()}")

        return warnings

    def _sanitize(self, text: str) -> str:
        sanitized = text

        for pattern in INJECTION_PATTERNS:
            sanitized = re.sub(
                pattern,
                "[REDACTED: POTENTIAL INJECTION]",
                sanitized,
                flags=re.IGNORECASE,
            )

        return sanitized

    def chunk_document(self, parsed: ParsedDocument) -> List[DocumentChunk]:
        chunks = []
        char_offset = 0

        for page_num, page_text in enumerate(parsed.pages):
            sections = self._extract_sections(page_text)

            if not sections:
                sections = [("full_page", page_text)]

            for section_name, section_text in sections:
                text_chunks = self._split_text(section_text)

                for chunk_text in text_chunks:
                    chunk = DocumentChunk(
                        text=chunk_text,
                        page_number=page_num + 1,
                        section=section_name if section_name != "full_page" else None,
                        char_start=char_offset,
                        char_end=char_offset + len(chunk_text),
                    )
                    chunks.append(chunk)
                    char_offset += len(chunk_text)

        return chunks

    def _extract_sections(self, text: str) -> List[tuple]:
        section_pattern = r"^(?:Section|Article|Chapter|Part|Clause|Rule|Regulation)\s+\d+[\.\d]*"
        lines = text.split("\n")
        sections = []
        current_section = None
        current_text = []

        for line in lines:
            if re.match(section_pattern, line.strip(), re.IGNORECASE):
                if current_text and any(part.strip() for part in current_text):
                    sections.append((current_section or "preamble", "\n".join(current_text)))
                current_section = line.strip()
                current_text = [line]
            else:
                current_text.append(line)

        if current_text and any(part.strip() for part in current_text):
            sections.append((current_section or "full_page", "\n".join(current_text)))

        return sections

    def _split_text(self, text: str) -> List[str]:
        if len(text) <= self.max_chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = min(start + self.max_chunk_size, len(text))

            if end < len(text):
                last_period = text.rfind(".", start, end)
                last_newline = text.rfind("\n", start, end)
                break_point = max(last_period, last_newline)

                if break_point > start:
                    end = break_point + 1

            chunks.append(text[start:end].strip())
            
            # If we've reached the end of the text, break
            if end >= len(text):
                break
                
            start = max(start + 1, end - self.chunk_overlap)

        return [c for c in chunks if c]


def parse_document(file_path: str, file_type: str) -> ParsedDocument:
    parser = DocumentParser()

    if file_type.lower() in ("pdf", "application/pdf"):
        return parser.parse_pdf(file_path)
    elif file_type.lower() in ("txt", "text/plain", "md", "markdown"):
        return parser.parse_text(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def parse_document_bytes(content: bytes, file_type: str) -> ParsedDocument:
    """Parse bounded, validated bytes without writing source data to disk."""
    parser = DocumentParser()
    if file_type.lower() in ("pdf", "application/pdf"):
        return parser.parse_pdf_bytes(content)
    if file_type.lower() in ("txt", "text/plain", "md", "markdown"):
        return parser.parse_text_content(content.decode("utf-8"))
    raise ValueError(f"Unsupported file type: {file_type}")
