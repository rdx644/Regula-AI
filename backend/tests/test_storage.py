from uuid import uuid4
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.services.storage import PrivateLocalStorage, validate_document
from app.schemas.regulation import RegulationProcessRequest
from app.services.parser import parse_document_bytes


def test_local_storage_generates_tenant_scoped_opaque_key(tmp_path):
    organization_id = uuid4()
    version_id = uuid4()
    storage = PrivateLocalStorage(tmp_path)

    key = storage.save(organization_id, version_id, ".txt", b"Section 1: banks shall report.")
    assert key.startswith(f"regulations/{organization_id}/{version_id}/")
    assert storage.read(key) == b"Section 1: banks shall report."


def test_storage_rejects_traversal_key(tmp_path):
    storage = PrivateLocalStorage(tmp_path)
    with pytest.raises(ValueError, match="Invalid object key"):
        storage.read("../../outside.txt")


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (b"not really a pdf", "regulation.pdf"),
        (b"\xff\xfe", "regulation.txt"),
        (b"binary\x00payload", "regulation.md"),
        (b"text", "regulation.exe"),
    ],
)
def test_document_validation_rejects_invalid_content(content, filename):
    with pytest.raises(HTTPException):
        validate_document(content, filename)


def test_document_validation_recognizes_valid_pdf_and_utf8_text():
    assert validate_document(b"%PDF-1.7\nbody", "rule.pdf") == (".pdf", "application/pdf")
    assert validate_document("Section 1: Banks shall act.".encode(), "rule.txt") == (".txt", "text/plain")


def test_document_processing_request_does_not_accept_server_file_paths():
    with pytest.raises(ValidationError):
        RegulationProcessRequest(version_id=uuid4(), file_path="C:/Windows/win.ini", file_type="txt")


def test_document_processing_request_accepts_only_version_id():
    version_id = uuid4()
    assert RegulationProcessRequest(version_id=version_id).version_id == version_id


def test_s3_storage_uses_private_server_side_encryption(monkeypatch):
    calls = []

    class FakeClient:
        def put_object(self, **kwargs):
            calls.append(kwargs)

    fake_boto3 = SimpleNamespace(client=lambda *_args, **_kwargs: FakeClient())
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    from app.services import storage as storage_module

    monkeypatch.setattr(storage_module.settings, "S3_BUCKET", "private-test-bucket")
    monkeypatch.setattr(storage_module.settings, "STORAGE_BACKEND", "s3")
    monkeypatch.setattr(storage_module.settings, "ENVIRONMENT", "test")
    storage = storage_module.PrivateS3Storage()
    key = storage.save(uuid4(), uuid4(), ".txt", b"confidential regulation")

    assert calls[0]["Bucket"] == "private-test-bucket"
    assert calls[0]["ServerSideEncryption"] == "AES256"
    assert "regulations/" in key
    assert "ACL" not in calls[0]


def test_parser_accepts_source_bytes_without_filesystem_copy():
    parsed = parse_document_bytes(b"Section 5. Banks shall maintain capital.", "txt")
    assert parsed.metadata["page_count"] == 1
    assert "capital" in parsed.sanitized_text
