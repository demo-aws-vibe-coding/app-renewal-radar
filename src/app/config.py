"""Runtime configuration. Everything comes from environment variables set by the platform.

There are deliberately no secrets here. The app authenticates to the data API by
forwarding the signed-in user's identity, which the platform load balancer supplies.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore")

    name: str = "renewal-radar"
    title: str = "Renewal Radar"
    # When set, data comes from the platform data API. When empty, from fixtures/.
    data_api_url: str = ""
    fixtures_dir: Path = Path(__file__).resolve().parents[2] / "fixtures"
    # Used only when no identity header is present (local development).
    default_user: str = "local.user@demo.local"
    # Comma-separated groups from app.yaml (users.groups); set by the platform at deploy time.
    # Empty = no group restriction beyond sign-in. "*" in a user's groups matches everything.
    allowed_groups_raw: str = ""
    # Sign-out URL supplied by the platform. Empty = no sign-out link shown (e.g. local dev).
    logout_url: str = ""

    @property
    def allowed_groups(self) -> list[str]:
        return [g.strip() for g in self.allowed_groups_raw.split(",") if g.strip()]


settings = Settings()
