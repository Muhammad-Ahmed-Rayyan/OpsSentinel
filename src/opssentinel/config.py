import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "openrouter").strip().lower()

    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "")

    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "")

    @property
    def active_model(self) -> str:
        """Model name for the currently selected provider."""
        if self.llm_provider == "openrouter":
            return self.openrouter_model
        if self.llm_provider == "groq":
            return self.groq_model
        return ""


settings = Settings()