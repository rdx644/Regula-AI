import pytest
from pydantic import ValidationError

from app.core.config import Settings


def valid_production_settings(**overrides):
    values = {
        "_env_file": None,
        "ENVIRONMENT": "production",
        "SECRET_KEY": "test-only-production-secret-not-for-deployment",
        "ALLOWED_HOSTS": ["api.example.test"],
        "BACKEND_CORS_ORIGINS": ["https://app.example.test"],
        "REDIS_URL": "redis://localhost:6379/0",
        "ENABLE_RATE_LIMITING": True,
        "STORAGE_BACKEND": "s3",
        "S3_BUCKET": "private-test-bucket",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_settings_require_explicit_https_hosts_and_private_storage():
    config = valid_production_settings()
    assert config.ALLOWED_HOSTS == ["api.example.test"]
    assert config.BACKEND_CORS_ORIGINS == ["https://app.example.test"]
    assert config.STORAGE_BACKEND == "s3"


@pytest.mark.parametrize(
    "overrides",
    [
        {"ALLOWED_HOSTS": ["localhost"]},
        {"ALLOWED_HOSTS": ["*"]},
        {"BACKEND_CORS_ORIGINS": ["*"]},
        {"BACKEND_CORS_ORIGINS": ["http://app.example.test"]},
        {"ENABLE_RATE_LIMITING": False},
        {"STORAGE_BACKEND": "local"},
        {"S3_BUCKET": None},
    ],
)
def test_production_configuration_rejects_unsafe_defaults(overrides):
    with pytest.raises(ValidationError):
        valid_production_settings(**overrides)


def test_browser_extraction_fixture_cannot_be_enabled_in_production():
    with pytest.raises(ValidationError, match="restricted to the test environment"):
        valid_production_settings(BROWSER_EXTRACTION_FIXTURE=True)
