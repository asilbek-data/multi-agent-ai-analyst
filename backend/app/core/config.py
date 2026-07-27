"""
F1 — Config.

Loads every key from a local .env (never committed). Using OpenAI as the
LLM + embeddings provider instead of the guide's default Gemini path —
everything downstream (agents, supervisor, critic) just calls `get_llm()`
and `get_embeddings()` from here, so swapping providers later only means
editing this one file.
"""
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- required ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    # --- vector store ---
    QDRANT_URL: str = os.getenv("QDRANT_URL", "")          # empty -> use embedded/local Qdrant
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "maai_documents")
    QDRANT_MEMORY_COLLECTION: str = os.getenv("QDRANT_MEMORY_COLLECTION", "maai_memory")

    # --- database (F5, text-to-SQL) ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/company.db")

    # --- optional extras ---
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")          # F4, web agent
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")  # F12, observability
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # --- graph safety ---
    MAX_REVISIONS: int = int(os.getenv("MAX_REVISIONS", "2"))
    RECURSION_LIMIT: int = int(os.getenv("RECURSION_LIMIT", "40"))

    def validate(self) -> None:
        missing = []
        if not self.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        if missing:
            raise RuntimeError(
                f"Missing required env vars: {', '.join(missing)}. "
                f"Copy .env.example to .env and fill them in."
            )


settings = Settings()


def get_llm(temperature: float = 0.0):
    """Single place that builds the chat model every agent uses."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY,
    )


def get_embeddings():
    """Single place that builds the embeddings model used for ingestion + memory."""
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
