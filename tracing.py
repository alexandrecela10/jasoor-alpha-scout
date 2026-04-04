"""
Langfuse Tracing Setup — centralized observability for Alpha Scout.

Mirrors the BDC Footnotes pattern: a singleton Langfuse client with helpers
for creating traces (logical groupings) and generations (individual LLM calls).

Every LLM call in the app flows through here, giving us:
- Full prompt/response visibility in the Langfuse dashboard
- Latency, token usage, and cost tracking
- "Faithfulness" scoring to catch hallucinations

Required environment variables:
    LANGFUSE_SECRET_KEY  — your Langfuse secret key
    LANGFUSE_PUBLIC_KEY  — your Langfuse public key
    LANGFUSE_HOST        — Langfuse server URL (defaults to https://cloud.langfuse.com)
"""

import os
import logging
from langfuse import Langfuse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton — one Langfuse client for the entire app lifetime.
# Why a singleton? Creating multiple clients wastes connections and can
# cause duplicate events. One client batches everything efficiently.
# ---------------------------------------------------------------------------
_langfuse_client: Langfuse = None


def get_langfuse() -> Langfuse:
    """
    Get or create the Langfuse client singleton.

    Reads credentials from environment variables (loaded by python-dotenv).
    If keys aren't set, returns None — tracing is optional, the app still works.

    Think of this like a "lazy" login: we only connect to Langfuse the first
    time someone asks for the client, then reuse that same connection forever.
    """
    global _langfuse_client

    # Already created? Return it immediately (this is the "singleton" part)
    if _langfuse_client is not None:
        return _langfuse_client

    # Read keys from environment
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    host = os.environ.get("LANGFUSE_BASE_URL", os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"))

    # No keys? That's fine — tracing is optional
    if not secret_key or not public_key:
        logger.warning(
            "Langfuse keys not set (LANGFUSE_SECRET_KEY / LANGFUSE_PUBLIC_KEY). "
            "Tracing disabled — LLM calls will still work, just not logged."
        )
        return None

    # Create the client and store it for reuse
    _langfuse_client = Langfuse(
        secret_key=secret_key,
        public_key=public_key,
        host=host,
    )
    logger.info(f"Langfuse tracing enabled (host={host})")
    return _langfuse_client


def create_trace(name: str, input_data: dict = None, metadata: dict = None):
    """
    Create a new trace (top-level grouping) in Langfuse.

    A "trace" groups related LLM calls together. For example:
    - "search_similar_companies" trace contains the Tavily search + extraction calls
    - "score_company" trace contains the 4 scoring dimension calls

    Returns the observation object, or None if tracing is disabled.
    We use as_type="span" because a trace is a container, not an LLM call.
    """
    lf = get_langfuse()
    if lf is None:
        return None

    try:
        return lf.start_observation(
            name=name,
            as_type="span",          # "span" = logical grouping (not an LLM call)
            input=input_data,
            metadata=metadata,
        )
    except Exception as e:
        # Tracing should never crash the app — log and continue
        logger.debug(f"Failed to create trace: {e}")
        return None


def create_generation(name: str, model: str, input_data: str, metadata: dict = None):
    """
    Create a new generation (single LLM call) in Langfuse.

    A "generation" represents one prompt → response cycle with Gemini.
    Langfuse will show:
    - The exact prompt sent (input_data)
    - The model's response (added later via generation.update())
    - Token count, latency, cost

    We use as_type="generation" because this IS an LLM call.
    """
    lf = get_langfuse()
    if lf is None:
        return None

    try:
        return lf.start_observation(
            name=name,
            as_type="generation",    # "generation" = one LLM call
            model=model,
            input=input_data,
            metadata=metadata,
        )
    except Exception as e:
        logger.debug(f"Failed to create generation: {e}")
        return None


def flush_langfuse():
    """
    Flush any pending Langfuse events before the process exits.

    Langfuse batches events for efficiency (sends them in bulk every few seconds).
    This ensures nothing is lost when the app shuts down or a Streamlit rerun happens.
    """
    if _langfuse_client is not None:
        _langfuse_client.flush()
        logger.info("Langfuse events flushed.")
