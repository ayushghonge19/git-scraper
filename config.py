"""Configuration module for GitHub Memory Assistant.

Handles environment variable loading and LLM instantiation.
Supports Google Gemini (free API tier) and OpenAI. Secrets are never hardcoded.
"""

import logging
import os
import warnings
from functools import lru_cache
from dotenv import load_dotenv

# Suppress benign Google GenAI SDK schema and AFC warnings
warnings.filterwarnings("ignore", message=".*Direct use of automatic function calling.*")
warnings.filterwarnings("ignore", message=".*additionalProperties.*")
warnings.filterwarnings("ignore", message=".*\\$schema.*")
logging.getLogger("google").setLevel(logging.ERROR)
logging.getLogger("google_genai").setLevel(logging.ERROR)
logging.getLogger("langchain_google_genai").setLevel(logging.ERROR)


# Load variables from .env file if present
load_dotenv()


@lru_cache(maxsize=1)
def get_llm():
    """Initializes and returns the configured Chat LLM.

    Checks priority:
    1. MOCK_LLM: If true, returns a simulated mock model for offline testing.
    2. GEMINI_API_KEY / GOOGLE_API_KEY: Uses ChatGoogleGenerativeAI (free tier).
    3. OPENAI_API_KEY: Uses ChatOpenAI.

    Returns:
        BaseChatModel: An initialized chat model.

    Raises:
        ValueError: If no valid API key is found.
    """
    mock_mode = os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes")

    if mock_mode:
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        return FakeListChatModel(
            responses=[
                "Hello! I am your GitHub Memory Assistant (Phase 1). How can I help you today?",
                "LangGraph is a library for building stateful, cyclical, multi-actor workflows with LLMs using graph representations.",
                "In LangGraph, State flows through Nodes along Edges, starting at START and terminating at END.",
                "You can exit the assistant anytime by typing 'exit' or 'quit'.",
            ]
        )

    # 1. Google Gemini (free API)
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        from langchain_google_genai import ChatGoogleGenerativeAI

        model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-flash-lite-latest")
        return ChatGoogleGenerativeAI(
            model=model_name,
            api_key=gemini_key,
            temperature=0.7,
        )

    # 2. OpenAI fallback
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        from langchain_openai import ChatOpenAI

        model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
        base_url = os.getenv("OPENAI_BASE_URL")
        kwargs = {
            "model": model_name,
            "api_key": openai_key,
            "temperature": 0.7,
        }
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)

    raise ValueError(
        "No API key found in your environment.\n\n"
        "To use Google Gemini for free:\n"
        "1. Get a free API key at https://aistudio.google.com/app/apikey\n"
        "2. Create a .env file (copy .env.example) and add:\n"
        "       GEMINI_API_KEY=your_gemini_key_here\n\n"
        "Alternatively, set MOCK_LLM=true in .env to test without an API key."
    )
