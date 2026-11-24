"""Thin wrapper around the OpenAI API with model fallback and safe JSON parsing."""

import json
import re
import threading

from . import config

_client = None
_working_model = None
_lock = threading.Lock()


class LLMError(RuntimeError):
    pass


def client():
    global _client
    if _client is None:
        if not config.has_openai():
            raise LLMError("OPENAI_API_KEY is not set. Add it to your .env file.")
        from openai import OpenAI

        kwargs = {"api_key": config.OPENAI_API_KEY, "timeout": 60, "max_retries": 2}
        if config.BASE_URL:
            kwargs["base_url"] = config.BASE_URL
        _client = OpenAI(**kwargs)
    return _client


def _candidate_models():
    seen, out = set(), []
    for m in [_working_model, config.OPENAI_MODEL, *config.FALLBACK_MODELS]:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _is_model_problem(err: Exception) -> bool:
    text = str(err).lower()
    return any(k in text for k in ("model", "does not exist", "not found", "unsupported", "access"))


def parse_json(text: str) -> dict:
    """Parse a JSON object even if the model wrapped it in ``` fences or extra text."""
    if not text:
        raise ValueError("empty response")
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def chat_json(system: str, user: str) -> dict:
    """Ask the model for a JSON object. Tries fallback models if one is unavailable."""
    global _working_model
    last_err = None
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for model in _candidate_models():
        try:
            try:
                resp = client().chat.completions.create(
                    model=model, messages=messages, response_format={"type": "json_object"}
                )
            except Exception as err:  # noqa: BLE001
                # Some providers/models don't support JSON mode: ask again without it.
                if "response_format" not in str(err).lower() and "json" not in str(err).lower():
                    raise
                resp = client().chat.completions.create(model=model, messages=messages)
            with _lock:
                _working_model = model
            return parse_json(resp.choices[0].message.content or "")
        except LLMError:
            raise
        except Exception as err:  # noqa: BLE001 - we want to try the next model
            last_err = err
            if not _is_model_problem(err):
                break
    raise LLMError(f"OpenAI request failed: {last_err}")


def embed(texts: list[str]) -> list[list[float]] | None:
    """Return embeddings, or None if embeddings are unavailable (search then uses keywords)."""
    if not texts or not config.has_openai() or not config.EMBEDDING_MODEL:
        return None
    try:
        resp = client().embeddings.create(model=config.EMBEDDING_MODEL, input=[t[:6000] for t in texts])
        return [d.embedding for d in resp.data]
    except Exception:  # noqa: BLE001 - keyword search still works without embeddings
        return None


def active_model() -> str:
    return _working_model or config.OPENAI_MODEL
