from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from opssentinel.config import settings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _require(value: str, env_name: str) -> None:
    if not value:
        raise ValueError(f"{env_name} is not set. Add it to your .env file.")


def get_llm(temperature: float = 0.0) -> BaseChatModel:
    """Return a chat model for the provider and model selected in .env."""
    provider = settings.llm_provider

    if provider == "openrouter":
        _require(settings.openrouter_api_key, "OPENROUTER_API_KEY")
        _require(settings.openrouter_model, "OPENROUTER_MODEL")
        return ChatOpenAI(
            model=settings.openrouter_model,
            api_key=settings.openrouter_api_key,
            base_url=OPENROUTER_BASE_URL,
            temperature=temperature,
            max_retries=1,  # failed calls can count against the free daily quota
        )

    if provider == "groq":
        _require(settings.groq_api_key, "GROQ_API_KEY")
        _require(settings.groq_model, "GROQ_MODEL")
        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=temperature,
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER '{provider}'. Use 'openrouter' or 'groq'."
    )