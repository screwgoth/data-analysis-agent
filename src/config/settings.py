from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(default="sqlite:///./data/agent.db")
    log_level: str = Field(default="INFO")

    # Analysis / agent bounds
    data_dir: str = Field(default="./data")
    max_steps: int = Field(default=6)
    execution_timeout_s: int = Field(default=30)
    max_upload_bytes: int = Field(default=100 * 1024 * 1024)  # ~100MB

    # Phase 2 — conversation + token budget
    history_max_turns: int = Field(default=8)          # most-recent turns kept verbatim
    token_warn_threshold: int = Field(default=20000)   # total tokens above → warn badge
    suggest_model: str = Field(default="gemini-2.5-flash")  # light follow-up model

    # Optional LangSmith tracing (enabled only when a key is present)
    langchain_api_key: str = Field(default="")
    langchain_tracing_v2: str = Field(default="")

    # LLM provider — auto-detected from whichever key is set if left blank
    llm_provider: str = Field(default="")   # "anthropic" | "gemini"
    llm_model: str = Field(default="")      # uses provider default when blank

    # Provider keys — set exactly one
    anthropic_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
