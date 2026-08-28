from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _normalize_model_name(model: str) -> str:
    value = (model or "").strip()
    return value.split("/")[-1] if value else ""


_INSECURE_JWT_SECRETS = {
    "",
    "pico-dev",
    "change-me",
    "change-me-dev-only-not-for-prod-32b!",
}
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "kimi-k2.6"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-v4-flash"
    # Product default model provider when both keys present: deepseek | kimi
    pico_model_provider: str = "deepseek"

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

    # --- Tiered run budgets (P-COMPLEX-DONE package A) ---
    # Delivery / pico-agent multi-step (HTML 课件等): default 900s, not 120s freeze.
    pico_run_max_seconds: int = 900
    pico_run_max_tokens: int = 32_000
    pico_run_max_steps: int = 24
    pico_run_max_retries: int = 2
    # Short / direct-model chat: keep snappy day-use turns.
    pico_run_short_max_seconds: int = 120
    pico_run_short_max_tokens: int = 8000
    # Durable long jobs (package B): wall cap for staged jobs / long agent when detach on.
    # Must pair with detach+checkpoint — never “only raise this to 8h.”
    pico_run_durable_max_seconds: int = 3600
    # Page close / SSE abort: default continue job (durable). 0 = legacy kill-on-disconnect.
    pico_run_detach_on_disconnect: bool = True

    # --- Pi Agent (product default multi-step kernel · HANDOFF-WB-PI) ---
    # True + empty canary (or *) → all principals use Pi (prod default).
    # True + non-empty joint keys → restricted canary only; miss = fail-closed unless allow_all.
    pico_pi_agent_runtime: bool = True
    pico_pi_agent_canary_membership_ids: str = ""
    pico_pi_agent_canary_batch: str = ""

    # Legacy Kimi Agent multi-step (rollback only; off by default).
    # Prefer PICO_LEGACY_KIMI_AGENT_RUNTIME; PICO_KIMI_AGENT_RUNTIME still accepted.
    pico_legacy_kimi_agent_runtime: bool = False
    pico_kimi_agent_runtime: bool = False  # alias env; OR'd with legacy flag in properties
    pico_kimi_agent_canary_membership_ids: str = ""
    pico_kimi_agent_canary_batch: str = ""
    # DEPRECATED no-op (KA-4 HARD): previously forced transitional loop.
    pico_legacy_agent_loop_emergency: bool = False
    pico_chat_rpm: int = 30
    pico_chat_max_concurrent: int = 2
    # Reject (do not silent-truncate) user prompts longer than this many chars.
    pico_chat_max_prompt_chars: int = 12000
    pico_allowed_models: str = ""

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
    # P2 MCP allowlist bridge (comma-separated known safe tool names).
    # Default pilot: mcp_time,mcp_workspace_stat. Empty string disables MCP tools.
    pico_mcp_allowlist: str = "mcp_time,mcp_workspace_stat"
    # Isolated sandbox sidecar (B2). Empty token allowed in dev; compose may set one.
    pico_sandbox_url: str = "http://127.0.0.1:18767"
    pico_sandbox_token: str = ""
    pico_env: str = "development"
    pico_allow_test_issuer_break_glass: bool = False

    # OpenAI-compat proxy key for LibreChat. Production requires a strong,
    # explicit internal credential; development also accepts known dev values.
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

    # T-KB-CATCH · Meilisearch projection (loopback only). Key stays in host .env.
    pico_meili_url: str = "http://127.0.0.1:7700"
    meili_master_key: str = ""
    siliconflow_api_key: str = ""
    zhipu_api_key: str = ""
    zhipu_images_url: str = ""
    zhipu_image_model: str = "glm-image"
    zhipu_image_size: str = ""
    zhipu_image_quality: str = ""
    gemini_api_key: str = ""
    google_api_key: str = ""
    gemini_images_url: str = ""
    gemini_image_model: str = "gemini-2.5-flash-image"
    pico_image_gateway_url: str = ""
    pico_image_gateway_key: str = ""
    pico_image_gateway_model: str = ""

    # edu → Pico service hooks
    pico_hook_service_token: str = ""  # shared secret for /v1/hooks/edu/*

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.pico_cors_origins.split(",") if o.strip()]

    @property
    def auth_issuer_mode(self) -> str:
        return "test_and_edu" if self.pico_accept_test_issuer else "edu_only"

    @property
    def is_production(self) -> bool:
        return self.pico_env.strip().lower() in {"production", "prod"}

    @property
    def allowed_model_list(self) -> list[str]:
        return [model.strip() for model in self.pico_allowed_models.split(",") if model.strip()]

    # --- Pi canary ---
    @property
    def pi_agent_canary_principal_set(self) -> frozenset[tuple[str, str]]:
        principals: set[tuple[str, str]] = set()
        for raw in self.pico_pi_agent_canary_membership_ids.split(","):
            entry = raw.strip()
            if not entry or entry in {"*", "*:*"} or ":" not in entry:
                continue
            school_id, membership_id = entry.split(":", 1)
            school_id = school_id.strip()
            membership_id = membership_id.strip()
            if school_id and membership_id and school_id != "*":
                principals.add((school_id, membership_id))
        return frozenset(principals)

    @property
    def pi_agent_canary_membership_count(self) -> int:
        return len(self.pi_agent_canary_principal_set)

    @property
    def pi_agent_allow_all_token(self) -> bool:
        for raw in self.pico_pi_agent_canary_membership_ids.split(","):
            if raw.strip() in {"*", "*:*"}:
                return True
        return False

    @property
    def pi_agent_default_all(self) -> bool:
        """True for intentional full cutover: Pi on + empty/* canary."""
        if not self.pico_pi_agent_runtime:
            return False
        if self.pi_agent_allow_all_token:
            return True
        return self.pico_pi_agent_canary_membership_ids.strip() == ""

    @property
    def pi_agent_scope(self) -> str:
        if not self.pico_pi_agent_runtime:
            return "off"
        if self.pi_agent_default_all:
            return "all"
        return "canary"

    # --- Legacy Kimi canary (rollback) ---
    @property
    def legacy_kimi_enabled(self) -> bool:
        return bool(self.pico_legacy_kimi_agent_runtime or self.pico_kimi_agent_runtime)

    @property
    def kimi_agent_canary_principal_set(self) -> frozenset[tuple[str, str]]:
        """Joint canary keys as (school_id, membership_id). Bare/* tokens ignored here."""
        principals: set[tuple[str, str]] = set()
        for raw in self.pico_kimi_agent_canary_membership_ids.split(","):
            entry = raw.strip()
            if not entry or entry in {"*", "*:*"} or ":" not in entry:
                continue
            school_id, membership_id = entry.split(":", 1)
            school_id = school_id.strip()
            membership_id = membership_id.strip()
            if school_id and membership_id and school_id != "*":
                principals.add((school_id, membership_id))
        return frozenset(principals)

    @property
    def kimi_agent_canary_membership_count(self) -> int:
        return len(self.kimi_agent_canary_principal_set)

    @property
    def kimi_agent_allow_all_token(self) -> bool:
        for raw in self.pico_kimi_agent_canary_membership_ids.split(","):
            if raw.strip() in {"*", "*:*"}:
                return True
        return False

    @property
    def kimi_agent_default_all(self) -> bool:
        if not self.legacy_kimi_enabled:
            return False
        if self.kimi_agent_allow_all_token:
            return True
        return self.pico_kimi_agent_canary_membership_ids.strip() == ""

    @property
    def kimi_agent_scope(self) -> str:
        if not self.legacy_kimi_enabled:
            return "off"
        if self.kimi_agent_default_all:
            return "all"
        return "canary"

    @property
    def kimi_agent_canary_membership_id_set(self) -> frozenset[str]:
        return frozenset(membership_id for _, membership_id in self.kimi_agent_canary_principal_set)

    def delivery_run_caps(
        self,
        *,
        allowed_tools: list[str] | None = None,
        skill_instruction: str = "",
    ):
        """RunCaps for pico-agent / multi-step delivery (courseware, tools)."""
        from pico_orchestrator.run_caps import caps_for_tier

        return caps_for_tier(
            "delivery",
            max_seconds=self.pico_run_max_seconds,
            max_tokens=self.pico_run_max_tokens,
            max_steps=self.pico_run_max_steps,
            max_retries=self.pico_run_max_retries,
            allowed_tools=allowed_tools,
            skill_instruction=skill_instruction,
        )

    def short_run_caps(self):
        """RunCaps for direct-model short chat (no multi-step agent)."""
        from pico_orchestrator.run_caps import caps_for_tier

        return caps_for_tier(
            "short",
            max_seconds=self.pico_run_short_max_seconds,
            max_tokens=self.pico_run_short_max_tokens,
            max_retries=self.pico_run_max_retries,
        )

    def durable_run_caps(
        self,
        *,
        allowed_tools: list[str] | None = None,
        skill_instruction: str = "",
    ):
        """RunCaps for durable long jobs (detach-from-browser)."""
        from pico_orchestrator.run_caps import caps_for_tier

        return caps_for_tier(
            "durable",
            max_seconds=self.pico_run_durable_max_seconds,
            max_tokens=max(self.pico_run_max_tokens, 64_000),
            max_steps=max(self.pico_run_max_steps, 48),
            max_retries=self.pico_run_max_retries,
            allowed_tools=allowed_tools,
            skill_instruction=skill_instruction,
        )

    def spend_caps_dict(self) -> dict:
        from pico_orchestrator.run_caps import spend_caps_public

        return spend_caps_public(
            delivery_seconds=self.pico_run_max_seconds,
            delivery_tokens=self.pico_run_max_tokens,
            delivery_steps=self.pico_run_max_steps,
            delivery_retries=self.pico_run_max_retries,
            short_seconds=self.pico_run_short_max_seconds,
            short_tokens=self.pico_run_short_max_tokens,
            durable_seconds=self.pico_run_durable_max_seconds,
            detach_on_disconnect=self.pico_run_detach_on_disconnect,
        )

    def validate_production(self) -> None:
        """Fail closed before a production process starts serving traffic."""
        if not self.is_production:
            return

        errors: list[str] = []
        jwt_secret = self.pico_jwt_secret.strip()
        if jwt_secret in _INSECURE_JWT_SECRETS or len(jwt_secret) < 32:
            errors.append("PICO_JWT_SECRET must be a non-default secret of at least 32 characters")

        proxy_key = self.pico_openai_proxy_key.strip()
        if proxy_key in {"pico-dev", "sk-pico-dev"}:
            errors.append("PICO_OPENAI_PROXY_KEY must not use a development default")
        elif proxy_key and len(proxy_key) < 32:
            errors.append("PICO_OPENAI_PROXY_KEY must be empty or at least 32 characters")

        if self.pico_accept_test_issuer:
            if not self.pico_allow_test_issuer_break_glass:
                errors.append(
                    "PICO_ACCEPT_TEST_ISSUER=true requires "
                    "PICO_ALLOW_TEST_ISSUER_BREAK_GLASS=true"
                )
            else:
                logger.critical(
                    "SECURITY BREAK-GLASS: production test JWT issuer is enabled"
                )

        if not (self.kimi_api_key.strip() or self.deepseek_api_key.strip()):
            errors.append("configure DEEPSEEK_API_KEY (preferred) or KIMI_API_KEY")
        if not self.allowed_model_list:
            errors.append("PICO_ALLOWED_MODELS must contain at least one production model")
        else:
            if self.deepseek_api_key.strip() and (
                self.pico_model_provider.strip().lower() != "kimi" or not self.kimi_api_key.strip()
            ):
                provider_model = self.deepseek_model.strip()
            else:
                provider_model = (
                    self.kimi_model if self.kimi_api_key.strip() else self.deepseek_model
                ).strip()
            normalized_allowed = {_normalize_model_name(item) for item in self.allowed_model_list}
            if provider_model not in self.allowed_model_list and not (
                _normalize_model_name(provider_model) in normalized_allowed
                or (
                    (
                        _normalize_model_name(provider_model)
                        in {"deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner"}
                        or _normalize_model_name(provider_model).startswith("gpt-")
                    )
                    and {"pico-fast", "pico-deep"}.intersection(normalized_allowed)
                )
            ):
                errors.append(
                    "the configured provider model must appear in PICO_ALLOWED_MODELS"
                )
        if self.pico_chat_rpm <= 0:
            errors.append("PICO_CHAT_RPM must be greater than zero")
        if self.pico_chat_max_concurrent <= 0:
            errors.append("PICO_CHAT_MAX_CONCURRENT must be greater than zero")
        if self.pico_chat_max_prompt_chars <= 0:
            errors.append("PICO_CHAT_MAX_PROMPT_CHARS must be greater than zero")
        if self.pico_run_max_tokens <= 0:
            errors.append("PICO_RUN_MAX_TOKENS must be greater than zero")
        if self.pico_run_max_seconds <= 0:
            errors.append("PICO_RUN_MAX_SECONDS must be greater than zero")
        if self.pico_run_max_steps <= 0:
            errors.append("PICO_RUN_MAX_STEPS must be greater than zero")
        if self.pico_run_short_max_seconds <= 0:
            errors.append("PICO_RUN_SHORT_MAX_SECONDS must be greater than zero")
        if self.pico_run_short_max_tokens <= 0:
            errors.append("PICO_RUN_SHORT_MAX_TOKENS must be greater than zero")
        if self.pico_run_durable_max_seconds <= 0:
            errors.append("PICO_RUN_DURABLE_MAX_SECONDS must be greater than zero")
        if self.pico_dangerous_tools_enabled:
            errors.append("PICO_DANGEROUS_TOOLS_ENABLED must remain false")
        if not self.pico_pi_agent_runtime and not self.legacy_kimi_enabled:
            errors.append("enable PICO_PI_AGENT_RUNTIME (default) or legacy Kimi for multi-step")

        if errors:
            raise ValueError("invalid production configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()
