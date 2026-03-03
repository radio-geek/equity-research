"""Load configuration from environment."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def get_env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def get_openai_api_key() -> str:
    key = get_env("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY is not set. Copy .env.example to .env and set it.")
    return key


def get_openai_model() -> str:
    return get_env("OPENAI_MODEL", "gpt-4o").strip() or "gpt-4o"


def get_tavily_api_key() -> str | None:
    """Tavily API key for web search. If not set, research runs without web search."""
    return get_env("TAVILY_API_KEY")


def get_reports_dir() -> Path:
    raw = get_env("REPORTS_DIR", "reports")
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_nse_download_folder() -> Path:
    raw = get_env("NSE_DOWNLOAD_FOLDER", ".nse_cache")
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_llm(tools: list | None = None):
    """Return LangChain ChatOpenAI instance. If tools are provided, binds them for tool use."""
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model=get_openai_model(), api_key=get_openai_api_key())
    if tools:
        return llm.bind_tools(tools)
    return llm
