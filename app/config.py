import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_host: str
    app_port: int
    agent_name: str
    agent_mode: str
    internal_agent_api_key: str
    maestro_base_url: str
    openai_api_key: str
    openai_model: str
    openai_temperature: float
    openai_max_output_tokens: int
    brain_enabled: bool
    audit_log_path: str
    reports_dir: str
    data_dir: str


def _get_env_int(name: str, default: str) -> int:
    return int(os.getenv(name, default).strip())


def _get_env_float(name: str, default: str) -> float:
    return float(os.getenv(name, default).strip())


def _get_env_bool(name: str, default: str) -> bool:
    value = os.getenv(name, default).strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def get_settings() -> Settings:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(base_dir, "data")
    reports_dir = os.path.join(base_dir, "reports")

    return Settings(
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=_get_env_int("APP_PORT", "8021"),
        agent_name=os.getenv("AGENT_NAME", "automation_integrations_ai"),
        agent_mode=os.getenv("AGENT_MODE", "PROPOSE"),
        internal_agent_api_key=os.getenv("INTERNAL_AGENT_API_KEY", ""),
        maestro_base_url=os.getenv("MAESTRO_BASE_URL", "http://localhost:8000"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.2"),
        openai_temperature=_get_env_float("OPENAI_TEMPERATURE", "0.2"),
        openai_max_output_tokens=_get_env_int("OPENAI_MAX_OUTPUT_TOKENS", "900"),
        brain_enabled=_get_env_bool("BRAIN_ENABLED", "false"),
        audit_log_path=os.path.join(data_dir, "audit.jsonl"),
        reports_dir=reports_dir,
        data_dir=data_dir,
    )
