"""
F12 — Observability (Langfuse).
"""
from app.core.config import settings

_client_configured = False


def get_langfuse_handler():
    """Returns a Langfuse CallbackHandler if keys are configured, else None."""
    global _client_configured

    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        return None

    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    if not _client_configured:
        Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        _client_configured = True

    return CallbackHandler()


def flush():
    """Force-send any queued trace events. Call after each graph run."""
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        return
    from langfuse import get_client

    get_client().flush()