"""The only place environment variables are read."""

import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SUPPORTED_COUNTIES = ("brevard", "orange", "volusia")


class ConfigError(SystemExit):
    """Raised at startup when configuration is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    admin_password: str
    session_secret: str

    operator_email: str = "operator@example.com"
    operator_postal_address: str = ""
    app_base_url: str = "http://127.0.0.1:8000"

    source_mode: Literal["fixture", "live"] = "fixture"
    fixtures_dir: Path = Path("fixtures")
    dbpr_newfood_url: str = (
        "https://www2.myfloridalicense.com/sto/file_download/extracts/newfood.csv"
    )
    dbpr_chgownr_url: str = (
        "https://www2.myfloridalicense.com/sto/file_download/extracts/chgownr_food.csv"
    )
    dbpr_plan_review_url: str = (
        "https://www2.myfloridalicense.com/sto/file_download/extracts/HR_plan_review.csv"
    )
    counties: str = "brevard"
    fetch_user_agent: str = "OpeningSoonFL/0.1 (+mailto:operator@example.com)"
    fetch_min_interval_s: float = 2.0

    email_mode: Literal["outbox", "resend"] = "outbox"
    resend_api_key: str = ""
    email_from: str = ""

    max_vendors_per_category: int = 3

    scheduler_enabled: bool = True
    scheduler_timezone: str = "America/New_York"

    test_routes: bool = False
    fake_now: datetime | None = None
    run_smoke: bool = False

    host: str = "127.0.0.1"
    port: int = 8000

    @field_validator("fake_now", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("admin_password", "session_secret", "database_url")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value

    @model_validator(mode="after")
    def _resend_needs_key(self) -> "Settings":
        if self.email_mode == "resend":
            missing = [n.upper() for n in ("resend_api_key", "email_from") if not getattr(self, n)]
            if missing:
                raise ValueError(f"EMAIL_MODE=resend requires {', '.join(missing)}")
        return self

    @property
    def county_list(self) -> list[str]:
        return [c.strip().lower() for c in self.counties.split(",") if c.strip()]


def load_settings(env_file: str | None = None) -> Settings:
    """Read settings once; turn validation errors into a message naming the variable.

    OSFL_ENV_FILE picks the dotenv file (default `.env`); set it to an empty string to read
    the process environment only, as the tests do.
    """
    if env_file is None:
        env_file = os.environ.get("OSFL_ENV_FILE", ".env")
    try:
        return Settings(_env_file=env_file or None)
    except ValidationError as exc:
        problems = []
        for err in exc.errors():
            loc = "_".join(str(part) for part in err["loc"]).upper() or "SETTINGS"
            problems.append(f"{loc}: {err['msg']}")
        raise ConfigError("Invalid configuration: " + "; ".join(problems)) from None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
