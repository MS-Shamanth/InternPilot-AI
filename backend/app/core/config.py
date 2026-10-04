"""Environment-based application settings (design.md §13.1, R13.1).

Every value comes from an environment variable (or a local `.env` file). `DATABASE_URL` has no
default so a misconfigured deployment fails at startup instead of on the first query.
"""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import EmailStr, Field, SecretStr, ValidationError, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = REPO_ROOT / "data"
DEFAULT_CORS_ORIGINS = ("http://localhost:5173",)
DEFAULT_INGEST_ALLOWED_HOSTS = ("remotive.com", "www.arbeitnow.com")
ALLOWED_URL_SCHEMES = frozenset({"http", "https"})

NonEmptyStr = Annotated[str, Field(min_length=1)]


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ConfigurationError(RuntimeError):
    """Raised at startup when the environment does not describe a valid configuration."""


class _CommaListMixin(PydanticBaseSettingsSource):
    """Accept `a,b,c` as well as JSON (`["a","b"]`) for list-valued variables."""

    def decode_complex_value(self, field_name: str, field: FieldInfo, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return super().decode_complex_value(field_name, field, value)


class _CommaListEnvSource(_CommaListMixin, EnvSettingsSource):
    pass


class _CommaListDotEnvSource(_CommaListMixin, DotEnvSettingsSource):
    pass


def _is_http_url(value: str) -> bool:
    parts = urlsplit(value)
    return parts.scheme in ALLOWED_URL_SCHEMES and bool(parts.netloc)


class Settings(BaseSettings):
    """Typed view of the process environment. Field `x_y` is read from env var `X_Y`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    app_env: AppEnv = AppEnv.DEVELOPMENT
    database_url: SecretStr
    test_database_url: SecretStr | None = None
    cors_origins: list[NonEmptyStr] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS), min_length=1
    )
    demo_user_email: EmailStr = Field(default="demo@internpilot.dev", max_length=254)
    demo_user_name: str = Field(default="Demo Student", min_length=1, max_length=100)
    data_dir: Path = DEFAULT_DATA_DIR
    ingest_allowed_hosts: list[NonEmptyStr] = Field(
        default_factory=lambda: list(DEFAULT_INGEST_ALLOWED_HOSTS)
    )
    ingest_timeout_seconds: float = Field(default=10, ge=1, le=60)
    ingest_max_bytes: int = Field(default=5_000_000, ge=1)
    llm_enabled: bool = False
    llm_provider: Literal["openai_compatible"] = "openai_compatible"
    llm_base_url: str = Field(default="", max_length=2048)
    llm_model: str = Field(default="", max_length=200)
    llm_api_key: SecretStr = SecretStr("")
    log_level: LogLevel = LogLevel.INFO

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            _CommaListEnvSource(settings_cls),
            _CommaListDotEnvSource(settings_cls),
            file_secret_settings,
        )

    @field_validator("database_url")
    @classmethod
    def _require_non_empty_database_url(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("cors_origins")
    @classmethod
    def _validate_cors_origins(cls, origins: list[str]) -> list[str]:
        cleaned = [origin.strip().rstrip("/") for origin in origins]
        for origin in cleaned:
            if not _is_http_url(origin):
                raise ValueError("each origin must be an explicit http(s) origin (no wildcard)")
        return cleaned

    @field_validator("ingest_allowed_hosts")
    @classmethod
    def _validate_allowed_hosts(cls, hosts: list[str]) -> list[str]:
        cleaned = [host.strip().lower() for host in hosts]
        for host in cleaned:
            if not host or any(char in host for char in "/:*@ "):
                raise ValueError("each entry must be a bare host name such as remotive.com")
        return cleaned

    @field_validator("llm_base_url")
    @classmethod
    def _validate_llm_base_url(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned and not _is_http_url(cleaned):
            raise ValueError("must be an http(s) URL or empty")
        return cleaned

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


def _describe_errors(error: ValidationError) -> str:
    """Summarize validation errors by env var name without echoing any (possibly secret) input."""
    problems: list[str] = []
    for item in error.errors(include_input=False, include_url=False):
        variable = str(item["loc"][0]).upper() if item["loc"] else "SETTINGS"
        if item["type"] == "missing" and variable == "DATABASE_URL":
            problems.append(
                "DATABASE_URL is required; set it in the environment or .env (see .env.example)"
            )
        else:
            problems.append(f"{variable}: {item['msg']}")
    return "Invalid configuration: " + "; ".join(problems)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per process; usable as a FastAPI dependency (override in tests)."""
    try:
        return Settings()  # type: ignore[call-arg]  # values come from the environment
    except ValidationError as error:
        raise ConfigurationError(_describe_errors(error)) from None
