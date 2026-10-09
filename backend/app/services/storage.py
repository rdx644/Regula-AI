"""Private storage for regulatory source documents.

The local adapter is intended for development and deterministic demos. Production
deployments must put this interface behind a private object-storage adapter.
"""

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
CHUNK_SIZE = 1024 * 1024


def validate_document(content: bytes, filename: str | None) -> tuple[str, str]:
    """Validate the content against a narrow extension and content allowlist."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail="Only PDF, TXT, and Markdown documents are accepted.")
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="The uploaded document is empty.")
    if suffix == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                                detail="The uploaded file is not a valid PDF document.")
        return suffix, "application/pdf"
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail="Text documents must use UTF-8 encoding.") from exc
    if b"\x00" in content:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail="Binary content is not accepted as a text document.")
    return suffix, "text/markdown" if suffix == ".md" else "text/plain"


class PrivateLocalStorage:
    """Local non-public storage for development and explicitly temporary demos."""

    def __init__(self, root: str | Path | None = None):
        configured_root = root if root is not None else settings.UPLOAD_STORAGE_DIR
        self.root = Path(configured_root).expanduser().resolve()

    def _path_for(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Invalid object key")
        return path

    def save(
        self,
        organization_id: UUID,
        resource_id: UUID,
        suffix: str,
        content: bytes,
        category: str = "regulations",
    ) -> str:
        if category not in {"regulations", "policies", "evidence"}:
            raise ValueError("Unsupported storage category")
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValueError("Unsupported file extension")
        key = f"{category}/{organization_id}/{resource_id}/{uuid4().hex}{suffix}"
        target = self._path_for(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(content)
        return key

    def read(self, key: str) -> bytes:
        """Read a validated object without making a second plaintext disk copy."""
        source = self._path_for(key)
        if not source.is_file():
            raise FileNotFoundError("Stored document is unavailable")
        suffix = source.suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValueError("Stored document type is unsupported")
        return source.read_bytes()

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        if path.is_file():
            path.unlink()


class PrivateS3Storage:
    """S3-compatible private storage; credentials come from the SDK role chain."""

    def __init__(self):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install the declared boto3 dependency to use S3 storage") from exc
        self.bucket = settings.S3_BUCKET
        if not self.bucket:
            raise RuntimeError("S3_BUCKET must be configured for S3 storage")
        self.client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL,
        )

    def verify_configuration(self):
        self.client.head_bucket(Bucket=self.bucket)
        public = self.client.get_public_access_block(Bucket=self.bucket)['PublicAccessBlockConfiguration']
        if not all(public.get(key) for key in ['BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets']):
            raise RuntimeError("Bucket public access must be blocked")
        if self.client.get_bucket_versioning(Bucket=self.bucket).get('Status') != 'Enabled':
            raise RuntimeError("Bucket versioning must be enabled")
        rules = self.client.get_bucket_encryption(Bucket=self.bucket)['ServerSideEncryptionConfiguration']['Rules']
        if not rules:
            raise RuntimeError("Bucket encryption must be configured")
        return True

    def save(
        self,
        organization_id: UUID,
        resource_id: UUID,
        suffix: str,
        content: bytes,
        category: str = "regulations",
    ) -> str:
        if category not in {"regulations", "policies", "evidence"} or suffix not in ALLOWED_EXTENSIONS:
            raise ValueError("Unsupported object type")
        key = f"{category}/{organization_id}/{resource_id}/{uuid4().hex}{suffix}"
        content_type = "application/pdf" if suffix == ".pdf" else "text/markdown" if suffix == ".md" else "text/plain"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
        return key

    def read(self, key: str) -> bytes:
        suffix = Path(key).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValueError("Stored document type is unsupported")
        from io import BytesIO
        output = BytesIO()
        self.client.download_fileobj(self.bucket, key, output)
        return output.getvalue()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def get_private_storage() -> PrivateLocalStorage | PrivateS3Storage:
    backend = settings.STORAGE_BACKEND.lower()
    if backend == "local":
        if settings.ENVIRONMENT.lower() in {"staging", "production"}:
            raise RuntimeError("Local document storage is not allowed in staging or production")
        return PrivateLocalStorage()
    if backend == "s3":
        return PrivateS3Storage()
    raise RuntimeError("STORAGE_BACKEND must be either 'local' or 's3'")
