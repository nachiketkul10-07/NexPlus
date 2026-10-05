"""
PulseOps Backend Core Configuration
Handles environment-based application settings with Pydantic Settings.
"""
import os
from typing import List
from urllib.parse import urlparse
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application & Environment
    PROJECT_NAME: str = "NexPulse Backend"
    VERSION: str = "0.2.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"

    # Server Binding
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # Security Credentials & Tokens (Prepared for Phase 3+)
    SECRET_KEY: str = "dev-secret-key-change-in-production-use-a-secure-random-key-32bytes"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    SESSION_COOKIE_NAME: str = "nexpulse_session"
    SESSION_COOKIE_SECURE: bool = False

    # CORS Configuration
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    TRUSTED_HOSTS: str = "localhost,127.0.0.1,testserver"
    # Public account creation is off in production until the invite flow is enabled.
    REGISTRATION_ENABLED: bool = False
    REGISTRATION_REQUIRE_INVITE: bool = True
    REGISTRATION_INVITE_TTL_SECONDS: int = 7 * 24 * 60 * 60

    # Database & Redis Configuration (Prepared for Phase 4 & Phase 9)
    DATABASE_URL: str = "postgresql+asyncpg://pulseops:pulseops_dev_pass@localhost:5432/pulseops_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_CONNECT_TIMEOUT: float = 0.5
    REDIS_SOCKET_TIMEOUT: float = 0.5

    # Rate Limiting Defaults
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    RATE_LIMIT_API_PER_MINUTE: int = 60
    RATE_LIMIT_TELEMETRY_PER_MINUTE: int = 600

    # AI Assistant Configuration (Phase 12 / Groq Provider)
    AI_ENABLED: bool = True
    AI_PROVIDER: str = "groq"
    AI_API_KEY: str = ""
    AI_MODEL: str = "llama-3.3-70b-versatile"
    AI_BASE_URL: str = "https://api.groq.com/openai/v1"
    AI_TIMEOUT_SECONDS: int = 20
    AI_MAX_CONTEXT_CHARS: int = 12000
    AI_MAX_LOG_ENTRIES: int = 20
    AI_MAX_METRIC_POINTS: int = 30

    # Max Payload Size Limit in Bytes (10MB default)
    MAX_PAYLOAD_SIZE_BYTES: int = 10 * 1024 * 1024

    # Observability Configuration (Phase 10)
    OTEL_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "pulseops-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_EXPORTER_OTLP_TIMEOUT: int = 10
    OTEL_TRACE_SAMPLING_RATE: float = 1.0
    PROMETHEUS_ENABLED: bool = True


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Returns parsed list of allowed CORS origins."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def trusted_hosts_list(self) -> List[str]:
        return [host.strip() for host in self.TRUSTED_HOSTS.split(",") if host.strip()]

    @property
    def is_production(self) -> bool:
        # Vercel is always treated as production for security decisions, even
        # if someone accidentally adds ENVIRONMENT=development to its settings.
        return bool(os.getenv("VERCEL")) or self.ENVIRONMENT.strip().lower() in {"prod", "production"}

    def validate_production_settings(self) -> None:
        """Fail closed when a production process still has development-only settings."""
        if not self.is_production:
            return

        problems = []
        secret_placeholder = any(marker in self.SECRET_KEY.upper() for marker in ("CHANGE_ME", "REPLACE", "EXAMPLE", "SECRET_KEY"))
        if len(self.SECRET_KEY) < 40 or len(set(self.SECRET_KEY)) < 12 or secret_placeholder or self.SECRET_KEY == "dev-secret-key-change-in-production-use-a-secure-random-key-32bytes":
            problems.append("SECRET_KEY must be a unique random value of at least 40 characters")
        if not self.SESSION_COOKIE_SECURE:
            problems.append("SESSION_COOKIE_SECURE must be true behind HTTPS")
        if not self.SESSION_COOKIE_NAME.startswith("__Host-"):
            problems.append("SESSION_COOKIE_NAME must use the __Host- prefix in production")
        if self.ACCESS_TOKEN_EXPIRE_MINUTES < 1 or self.ACCESS_TOKEN_EXPIRE_MINUTES > 30:
            problems.append("ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 30 in production")
        if not self.cors_origins_list or any(not origin.startswith("https://") for origin in self.cors_origins_list):
            problems.append("ALLOWED_ORIGINS must contain only the production HTTPS origin(s)")
        if not self.trusted_hosts_list or any("*" in host for host in self.trusted_hosts_list):
            problems.append("TRUSTED_HOSTS must list the exact public hostnames")
        elif any(urlparse(origin).hostname not in self.trusted_hosts_list for origin in self.cors_origins_list):
            problems.append("Every ALLOWED_ORIGINS hostname must also appear in TRUSTED_HOSTS")
        database_url = urlparse(self.DATABASE_URL)
        if database_url.scheme != "postgresql+asyncpg" or not database_url.hostname or database_url.hostname in {"localhost", "127.0.0.1"} or not database_url.password or len(database_url.password) < 24 or "URL_ENCODED_PASSWORD" in database_url.password:
            problems.append("DATABASE_URL must use asyncpg with private PostgreSQL and a strong password")
        redis_url = urlparse(self.REDIS_URL)
        if redis_url.scheme not in {"redis", "rediss"} or not redis_url.hostname or redis_url.hostname in {"localhost", "127.0.0.1"} or not redis_url.password or len(redis_url.password) < 24 or "URL_ENCODED" in redis_url.password:
            problems.append("REDIS_URL must use a password-protected Redis service")
        if not self.REGISTRATION_REQUIRE_INVITE:
            problems.append("REGISTRATION_REQUIRE_INVITE must be true in production")
        if self.REGISTRATION_INVITE_TTL_SECONDS < 300 or self.REGISTRATION_INVITE_TTL_SECONDS > 30 * 24 * 60 * 60:
            problems.append("REGISTRATION_INVITE_TTL_SECONDS must be between 300 seconds and 30 days")
        if self.AI_ENABLED and not self.AI_BASE_URL.startswith("https://"):
            problems.append("AI_BASE_URL must use HTTPS when AI requests are enabled")
        if self.AI_ENABLED and not self.AI_API_KEY.strip():
            problems.append("AI_API_KEY must be configured when AI is enabled in production")
        if problems:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))


settings = Settings()

