from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "kimi-k2.6"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # Phase 1 test issuer (HS256)
    pico_jwt_secret: str = "change-me-dev-only-not-for-prod-32b!"
    pico_jwt_iss: str = "pico-test-issuer"
    pico_jwt_aud: str = "pico-api"
    pico_jwt_ttl_seconds: int = 900

    # Phase 3 edu issuer (who signs — same claim shape)
    # When set, Pico also accepts tokens with iss == pico_edu_iss
    pico_edu_iss: str = ""  # e.g. https://edu.example/iss/pico
    pico_edu_jwt_secret: str = ""  # HS256 shared with edu (bootstrap); empty = disabled
    pico_edu_jwt_public_key_pem: str = ""  # optional RS256 public key PEM
    pico_accept_test_issuer: bool = True  # set false in production after edu issuer live

    pico_run_max_seconds: int = 120
    pico_run_max_tokens: int = 8000
    pico_run_max_retries: int = 2

    pico_api_host: str = "0.0.0.0"
    pico_api_port: int = 8000
    pico_database_url: str = "sqlite+aiosqlite:///./data/pico.db"
    # Include LibreChat product origins (8080 public + 3080 direct)
    pico_cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8080,http://127.0.0.1:8080,"
        "http://localhost:3080,http://127.0.0.1:3080,"
        "https://pico.aivia.asia"
    )

    pico_agent_file: str = "services/orchestrator/agents/pico.yaml"
    pico_dangerous_tools_enabled: bool = False
    pico_env: str = "development"

    # OpenAI-compat proxy key for LibreChat etc. (dev only unless set).
    # Never fall back to KIMI_API_KEY or JWT secret as Bearer.
    pico_openai_proxy_key: str = ""

    # Phase 3 edu adapter
    # fake = synthetic FakeEdu; live = HTTP to edu
    pico_edu_mode: Literal["fake", "live"] = "fake"
    pico_edu_base_url: str = ""  # e.g. http://127.0.0.1:8001
    pico_edu_service_token: str = ""  # Pico → edu service credential
    pico_edu_timeout_seconds: float = 10.0

    # Change handoff push Pico → edu (optional until edu ready)
    pico_edu_handoff_enabled: bool = False

    # edu → Pico service hooks
    pico_hook_service_token: str = ""  # shared secret for /v1/hooks/edu/*

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.pico_cors_origins.split(",") if o.strip()]

    @property
    def auth_issuer_mode(self) -> str:
        return "test_and_edu" if self.pico_accept_test_issuer else "edu_only"


@lru_cache
def get_settings() -> Settings:
    return Settings()
