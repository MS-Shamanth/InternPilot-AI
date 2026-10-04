"""Unit tests for app.core.config (design.md §13.1, R13.1)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import (
    DEFAULT_DATA_DIR,
    AppEnv,
    ConfigurationError,
    LogLevel,
    Settings,
    get_settings,
)

pytestmark = pytest.mark.unit

SETTINGS_ENV_VARS = (
    "APP_ENV",
    "DATABASE_URL",
    "TEST_DATABASE_URL",
    "CORS_ORIGINS",
    "DEMO_USER_EMAIL",
    "DEMO_USER_NAME",
    "DATA_DIR",
    "INGEST_ALLOWED_HOSTS",
    "INGEST_TIMEOUT_SECONDS",
    "INGEST_MAX_BYTES",
    "LLM_ENABLED",
    "LLM_PROVIDER",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_API_KEY",
    "LOG_LEVEL",
)
DB_URL = "postgresql+psycopg://internpilot:placeholder-pw@localhost:5432/internpilot"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Isolate every test from the developer's environment and any local .env file."""
    for name in SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def load(**overrides: str) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_settings_missing_database_url_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as excinfo:
        load()

    assert excinfo.value.errors()[0]["loc"] == ("database_url",)


def test_get_settings_missing_database_url_raises_clear_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="DATABASE_URL is required"):
        get_settings()


def test_settings_empty_database_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "   ")

    with pytest.raises(ValidationError):
        load()


def test_settings_only_database_url_set_uses_documented_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)

    settings = load()

    assert settings.database_url.get_secret_value() == DB_URL
    assert settings.app_env is AppEnv.DEVELOPMENT
    assert settings.test_database_url is None
    assert settings.cors_origins == ["http://localhost:5173"]
    assert settings.demo_user_email == "demo@internpilot.dev"
    assert settings.demo_user_name == "Demo Student"
    assert settings.data_dir == DEFAULT_DATA_DIR
    assert settings.ingest_allowed_hosts == ["remotive.com", "www.arbeitnow.com"]
    assert settings.ingest_timeout_seconds == 10
    assert settings.ingest_max_bytes == 5_000_000
    assert settings.llm_enabled is False
    assert settings.llm_provider == "openai_compatible"
    assert settings.llm_base_url == ""
    assert settings.llm_model == ""
    assert settings.llm_api_key.get_secret_value() == ""
    assert settings.log_level is LogLevel.INFO


def test_settings_default_data_dir_points_at_repo_data_folder() -> None:
    assert DEFAULT_DATA_DIR.name == "data"
    assert (DEFAULT_DATA_DIR.parent / "backend" / "app" / "core" / "config.py").is_file()


def test_settings_comma_lists_parse_and_strip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("CORS_ORIGINS", " http://localhost:5173/ , https://app.example.com ")
    monkeypatch.setenv("INGEST_ALLOWED_HOSTS", "Remotive.com, www.arbeitnow.com,")

    settings = load()

    assert settings.cors_origins == ["http://localhost:5173", "https://app.example.com"]
    assert settings.ingest_allowed_hosts == ["remotive.com", "www.arbeitnow.com"]


def test_settings_json_list_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("CORS_ORIGINS", '["http://a.example.com", "http://b.example.com"]')

    assert load().cors_origins == ["http://a.example.com", "http://b.example.com"]


@pytest.mark.parametrize("origins", ["*", "localhost:5173", "ftp://files.example.com"])
def test_settings_invalid_cors_origin_raises(monkeypatch: pytest.MonkeyPatch, origins: str) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("CORS_ORIGINS", origins)

    with pytest.raises(ValidationError):
        load()


@pytest.mark.parametrize("hosts", ["https://remotive.com", "remotive.com/api", "*.example.com"])
def test_settings_allowed_host_with_scheme_path_or_wildcard_raises(
    monkeypatch: pytest.MonkeyPatch, hosts: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("INGEST_ALLOWED_HOSTS", hosts)

    with pytest.raises(ValidationError):
        load()


@pytest.mark.parametrize("timeout", ["0", "61"])
def test_settings_ingest_timeout_out_of_range_raises(
    monkeypatch: pytest.MonkeyPatch, timeout: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("INGEST_TIMEOUT_SECONDS", timeout)

    with pytest.raises(ValidationError):
        load()


def test_settings_unsupported_llm_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("LLM_PROVIDER", "other")

    with pytest.raises(ValidationError):
        load()


def test_settings_non_http_llm_base_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("LLM_BASE_URL", "file:///etc/passwd")

    with pytest.raises(ValidationError):
        load()


def test_settings_env_values_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example.com/v1")
    monkeypatch.setenv("DATA_DIR", "/data")

    settings = load()

    assert settings.app_env is AppEnv.PRODUCTION
    assert settings.log_level is LogLevel.DEBUG
    assert settings.llm_enabled is True
    assert settings.llm_base_url == "https://llm.example.com/v1"
    assert settings.data_dir == Path("/data")


def test_settings_secrets_are_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("LLM_API_KEY", "placeholder-api-key")

    settings = load()

    assert settings.llm_api_key.get_secret_value() == "placeholder-api-key"
    assert "placeholder-api-key" not in repr(settings)
    assert "placeholder-pw" not in repr(settings)
    assert "placeholder-api-key" not in str(settings.model_dump())


def test_get_settings_invalid_value_error_does_not_echo_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("INGEST_MAX_BYTES", "not-a-number-secret")

    with pytest.raises(ConfigurationError) as excinfo:
        get_settings()

    assert "INGEST_MAX_BYTES" in str(excinfo.value)
    assert "not-a-number-secret" not in str(excinfo.value)
    assert excinfo.value.__cause__ is None


def test_get_settings_returns_cached_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)

    assert get_settings() is get_settings()


def test_get_settings_reads_dotenv_in_working_directory(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        f"DATABASE_URL={DB_URL}\nCORS_ORIGINS=http://a.example.com,http://b.example.com\n",
        encoding="utf-8",
    )

    settings = get_settings()

    assert settings.database_url.get_secret_value() == DB_URL
    assert settings.cors_origins == ["http://a.example.com", "http://b.example.com"]
