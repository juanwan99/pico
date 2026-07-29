from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshot-v1-8k"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    pico_jwt_secret: str = "change-me-dev-only-not-for-prod-32b!"
    pico_jwt_iss: str = "pico-test-issuer"
    pico_jwt_aud: str = "pico-api"
    pico_jwt_ttl_seconds: int = 900

    pico_run_max_seconds: int = 120
    pico_run_max_tokens: int = 8000
    pico_run_max_retries: int = 2

    pico_api_host: str = "0.0.0.0"
    pico_api_port: int = 8000
    pico_database_url: str = "sqlite+aiosqlite:///./data/pico.db"
    pico_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    pico_agent_file: str = "services/orchestrator/agents/pico.yaml"
    pico_dangerous_tools_enabled: bool = False
    pico_env: str = "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.pico_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
