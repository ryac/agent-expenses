from functools import lru_cache
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel, set_tracing_disabled
import os

PROVIDERS = {
    "openai":     {"base_url": None,                                                        "key_env": "OPENAI_API_KEY"},
    "grok":       {"base_url": "https://api.x.ai/v1",                                       "key_env": "XAI_API_KEY"},
    "gemini":     {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",  "key_env": "GEMINI_API_KEY"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1",                              "key_env": "OPENROUTER_API_KEY"},
    "ollama":     {"base_url": "http://localhost:11434/v1",                                 "key_env": None},
}

@lru_cache
def _client(provider: str) -> AsyncOpenAI:
    cfg = PROVIDERS[provider]
    api_key = os.environ[cfg["key_env"]] if cfg["key_env"] else "ollama"
    return AsyncOpenAI(base_url=cfg["base_url"], api_key=api_key)

def build_model():
    provider = os.getenv("EXPENSES_PROVIDER", "openai").lower()
    model_name = os.getenv("EXPENSES_MODEL", "gpt-4.1")  # pick your default
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}; choose from {list(PROVIDERS)}")

    if provider == "openai":
        return model_name  # SDK default: Responses API + trace uploads
    set_tracing_disabled(True)  # traces upload to OpenAI and need an OpenAI key
    return OpenAIChatCompletionsModel(model=model_name, openai_client=_client(provider))