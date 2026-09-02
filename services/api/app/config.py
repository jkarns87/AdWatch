from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://adwatch:adwatch@localhost:5432/adwatch"

    serpapi_api_key: str = ""
    serpapi_cache_dir: str = ".cache/serpapi"
    serpapi_timeout_s: float = 60.0

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"

    demo_endpoints: bool = True
    webhook_url: str = ""

    auth_provider: str = "none"  # none | xano
    xano_base_url: str = ""  # e.g. https://x8ki-....xano.io/api:adwatch-control
    dataplane_shared_secret: str = ""  # shared with Xano ($env.DATAPLANE_SHARED_SECRET); allows X-Workspace-Id from machines
    alert_dispatcher: str = "webhook"  # webhook | xano | none
    dashboard_url: str = "http://localhost:3000"

    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def demo_enabled(self) -> bool:
        return self.demo_endpoints or self.env != "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
