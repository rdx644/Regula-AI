from typing import List, Union, Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    PROJECT_NAME: str = "RegulaAI"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"

    # Security
    SECRET_KEY: str = "change_me_in_production_regula_ai_super_secret_key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours; reauthentication is required after expiry
    JWT_ISSUER: str = "regulaai-api"
    JWT_AUDIENCE: str = "regulaai-web"

    # CORS
    BACKEND_CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://localhost:3001"]
    ALLOWED_HOSTS: Union[List[str], str] = ["localhost", "127.0.0.1", "testserver"]

    # Database
    SQLALCHEMY_DATABASE_URI: str = "postgresql://postgres:postgres@localhost:5432/regula_ai"

    # AI & Services (optional)
    OPENAI_API_KEY: Optional[str] = None
    MODEL_EXECUTION_ENABLED: bool = False
    OPS_METRICS_TOKEN: Optional[str] = None
    REDIS_URL: Optional[str] = None
    ENABLE_RATE_LIMITING: bool = False
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 120
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    AGENT_RATE_LIMIT_PER_MINUTE: int = 20
    AI_REQUESTS_PER_TENANT_PER_DAY: int = 100
    AI_TOKENS_PER_TENANT_PER_DAY: int = 200000

    # Private document storage; local storage is for development/demo only.
    STORAGE_BACKEND: str = "local"
    UPLOAD_STORAGE_DIR: str = "var/private-uploads"
    MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024
    S3_BUCKET: Optional[str] = None
    S3_ENDPOINT_URL: Optional[str] = None
    AWS_REGION: str = "ap-south-1"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://localhost:3001"]

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def assemble_allowed_hosts(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                return json.loads(v)
            return [host.strip() for host in v.split(",") if host.strip()]
        return v

    @model_validator(mode="after")
    def require_production_secret(self):
        if self.ENVIRONMENT.lower() in {"staging", "production"}:
            secret = self.SECRET_KEY.strip()
            if len(secret) < 32 or "change_me" in secret.lower():
                raise ValueError(
                    "SECRET_KEY must be a unique value of at least 32 characters in staging and production."
                )
            if not self.JWT_ISSUER.strip() or not self.JWT_AUDIENCE.strip():
                raise ValueError("JWT_ISSUER and JWT_AUDIENCE must be explicitly configured.")
            unsafe_hosts = {"localhost", "127.0.0.1", "testserver", "*"}
            if not self.ALLOWED_HOSTS or any(host.lower() in unsafe_hosts for host in self.ALLOWED_HOSTS):
                raise ValueError("ALLOWED_HOSTS must be explicitly configured in staging and production.")
            if not self.BACKEND_CORS_ORIGINS or any(
                origin == "*" or not origin.startswith("https://")
                for origin in self.BACKEND_CORS_ORIGINS
            ):
                raise ValueError("Staging and production require explicit HTTPS CORS origins.")
            if not self.REDIS_URL or not self.ENABLE_RATE_LIMITING:
                raise ValueError("Staging and production require Redis-backed request rate limiting.")
            if self.AI_REQUESTS_PER_TENANT_PER_DAY < 1 or self.AI_TOKENS_PER_TENANT_PER_DAY < 1:
                raise ValueError("Production model quotas must be positive")
            if self.STORAGE_BACKEND.lower() != "s3" or not self.S3_BUCKET:
                raise ValueError("Staging and production require a configured private S3-compatible bucket.")
        return self


settings = Settings()
