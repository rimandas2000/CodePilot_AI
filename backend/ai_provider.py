"""Unified AI provider layer for CodePilot AI.

Supports:
- OpenAI-compatible ChatGPT API
- Google Gemini API
- Groq (OpenAI-compatible)

CodePilot uses one selected cloud AI provider. RAG remains local and can be
used with any provider by adding retrieved context to the prompt before this
module is called.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from dotenv import load_dotenv
from json_storage import atomic_write_json

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)

DATA_DIR = Path(os.getenv("CODEPILOT_DATA_DIR", str(ROOT / "data")))
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "use_rag": True,
    "cloud_provider": os.getenv("CLOUD_PROVIDER", "OpenAI"),
    "remember_api_keys": True,
    "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
    "openai_model": os.getenv("OPENAI_MODEL", "gpt-5-mini"),
    "openai_base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
    "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    "groq_api_key": os.getenv("GROQ_API_KEY", ""),
    "groq_model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    "groq_base_url": os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
}


def load_settings() -> dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)
    try:
        if SETTINGS_FILE.exists():
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                settings.update(saved)
    except Exception:
        pass
    # Environment variables take precedence when explicitly supplied. This
    # lets users keep secrets out of settings.json if they prefer.
    env_map = {
        "OPENAI_API_KEY": "openai_api_key",
        "OPENAI_MODEL": "openai_model",
        "OPENAI_BASE_URL": "openai_base_url",
        "GEMINI_API_KEY": "gemini_api_key",
        "GEMINI_MODEL": "gemini_model",
        "GROQ_API_KEY": "groq_api_key",
        "GROQ_MODEL": "groq_model",
        "GROQ_BASE_URL": "groq_base_url",
    }
    for env_name, key in env_map.items():
        if os.getenv(env_name):
            settings[key] = os.getenv(env_name)
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    payload = dict(DEFAULT_SETTINGS)
    payload.update(settings)
    if not payload.get("remember_api_keys", True):
        for key in ("openai_api_key", "gemini_api_key", "groq_api_key"):
            payload[key] = ""
    atomic_write_json(SETTINGS_FILE, payload)


def enabled_providers(settings: dict[str, Any]) -> list[str]:
    name = str(settings.get("cloud_provider", "OpenAI")).strip()
    if name not in {"OpenAI", "Gemini", "Groq"}:
        raise ValueError("Select OpenAI, Gemini, or Groq as the cloud provider.")
    return [name]


def active_provider(settings: dict[str, Any]) -> str:
    return " + ".join(enabled_providers(settings)) or "Disabled"


def model_for(provider: str, settings: dict[str, Any]) -> str:
    key = {"OpenAI": "openai_model", "Gemini": "gemini_model", "Groq": "groq_model"}[provider]
    return str(settings.get(key) or DEFAULT_SETTINGS[key]).strip()


def active_model(settings: dict[str, Any]) -> str:
    return " / ".join(model_for(name, settings) for name in enabled_providers(settings)) or "No model"


def validate_settings(settings: dict[str, Any]) -> None:
    for name in enabled_providers(settings):
        key_name = {"OpenAI": "openai_api_key", "Gemini": "gemini_api_key", "Groq": "groq_api_key"}[name]
        if not str(settings.get(key_name, "")).strip():
            raise ValueError(f"{name} API key is missing. Add it before saving.")
        if name != "Gemini":
            _base_url(settings.get(f"{name.lower()}_base_url"), name)
        model_key = {"OpenAI": "openai_model", "Gemini": "gemini_model", "Groq": "groq_model"}[name]
        if not str(settings.get(model_key, "")).strip():
            raise ValueError(f"Enter a model name for {name}.")


def _base_url(value, provider):
    default_key = f"{provider.lower()}_base_url"
    url = str(value or DEFAULT_SETTINGS[default_key]).strip().rstrip("/")
    parsed = parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"Enter a valid HTTP(S) base URL for {provider}, without credentials or query parameters.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Use HTTPS for cloud API URLs to protect your API key.")
    if url.endswith("/chat/completions"):
        url = url[:-len("/chat/completions")]
    return url


class ProviderError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def _safe_error(exc, settings):
    message = str(exc)
    for name in ("openai_api_key", "gemini_api_key", "groq_api_key"):
        key = str(settings.get(name, ""))
        if key:
            message = message.replace(key, "[redacted]")
    return message[:1000]


def _read_json_response(req: request.Request, timeout: float) -> dict[str, Any]:
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ProviderError("The provider returned an unexpected response format.")
        return data
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(details)
            inner = parsed.get("error", {}) if isinstance(parsed, dict) else {}
            message = inner.get("message", details) if isinstance(inner, dict) else str(inner)
        except (ValueError, TypeError):
            message = details
        hint = {401: "Check your API key.", 403: "Check model access and API permissions.",
                404: "Check the model name and API URL.", 429: "Check quota/rate limits, then retry later."}.get(exc.code, "")
        raise ProviderError(f"HTTP {exc.code}: {message[:600]} {hint}".strip(), exc.code) from exc
    except error.URLError as exc:
        raise ProviderError(f"Could not reach the provider: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ProviderError("The AI request timed out. Check connectivity and try again.") from exc
    except (ValueError, UnicodeError) as exc:
        raise ProviderError("The provider returned invalid JSON instead of an AI response.") from exc


def connection_results(settings: dict[str, Any], live: bool = False) -> dict[str, tuple[bool, str]]:
    results = {}
    try:
        providers = enabled_providers(settings)
    except ValueError as exc:
        return {"Configuration": (False, str(exc))}
    if not providers:
        return {"Configuration": (False, "Enable at least one AI provider")}
    for provider in providers:
        try:
            key_name = {"OpenAI": "openai_api_key", "Gemini": "gemini_api_key", "Groq": "groq_api_key"}[provider]
            if not str(settings.get(key_name, "")).strip():
                results[provider] = (False, "API key missing")
                continue
            if not live:
                results[provider] = (True, "Configured — use Test Connections to verify")
                continue
            probe_tokens = 1024 if provider == "OpenAI" and model_for(provider, settings).startswith(("gpt-5", "o1", "o3", "o4")) else 128
            answer = _generate_one(provider, "Reply with OK.", settings, "Connection test.", 0, probe_tokens, 30)
            results[provider] = (bool(answer.strip()), "Connected; model responded")
        except Exception as exc:
            results[provider] = (False, _safe_error(exc, settings))
    return results


def provider_status(settings: dict[str, Any], live: bool = False) -> tuple[bool, str]:
    results = connection_results(settings, live)
    return any(ok for ok, _ in results.values()), " | ".join(f"{name}: {message}" for name, (_, message) in results.items())


def _openai_compatible_generate(prompt: str, settings: dict[str, Any], provider: str, system_prompt: str, temperature: float, max_tokens: int, timeout: float) -> str:
    if provider == "Groq":
        key = str(settings.get("groq_api_key", "")).strip()
        model = str(settings.get("groq_model") or DEFAULT_SETTINGS["groq_model"])
        base_url = _base_url(settings.get("groq_base_url"), "Groq")
    else:
        key = str(settings.get("openai_api_key", "")).strip()
        model = str(settings.get("openai_model") or DEFAULT_SETTINGS["openai_model"])
        base_url = _base_url(settings.get("openai_base_url"), "OpenAI")
    if not key:
        raise RuntimeError(f"{provider} API key is missing. Add it in Settings.")
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": prompt.strip()})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
    }

    if provider == "OpenAI" and model.startswith(("gpt-5", "o1", "o3", "o4")):
        payload.pop("temperature", None)
        payload["max_completion_tokens"] = payload.pop("max_tokens")

    def do_request(body: dict[str, Any]) -> dict[str, Any]:
        req = request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            method="POST",
        )
        return _read_json_response(req, timeout)

    try:
        data = do_request(payload)
    except RuntimeError as exc:
        # Some newer OpenAI-compatible reasoning models use
        # max_completion_tokens and/or reject a custom temperature. Retry in
        # a broadly compatible form instead of making users edit code.
        message = str(exc).lower()
        if provider == "OpenAI" and getattr(exc, "status_code", None) == 400 and ("max_tokens" in message or "temperature" in message):
            retry_payload = {
                "model": model,
                "messages": messages,
                "max_completion_tokens": int(max_tokens),
            }
            data = do_request(retry_payload)
        else:
            raise
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"{provider} returned no completion choices.")
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        # Some OpenAI-compatible APIs can return content parts.
        content = "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    answer = str(content or "").strip()
    if not answer:
        raise RuntimeError(f"{provider} returned no answer text. Check output-token limits and model compatibility.")
    return answer


def _gemini_generate(prompt: str, settings: dict[str, Any], system_prompt: str, temperature: float, max_tokens: int, timeout: float) -> str:
    key = str(settings.get("gemini_api_key", "")).strip()
    model = str(settings.get("gemini_model") or DEFAULT_SETTINGS["gemini_model"])
    if not key:
        raise RuntimeError("Gemini API key is missing. Add it in Settings.")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{parse.quote(model.removeprefix('models/'), safe='-._')}:generateContent"
    )
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt.strip()}]}],
        "generationConfig": {
            "temperature": float(temperature),
            "maxOutputTokens": int(max_tokens),
        },
    }
    if system_prompt.strip():
        payload["systemInstruction"] = {"parts": [{"text": system_prompt.strip()}]}
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    data = _read_json_response(req, timeout)
    candidates = data.get("candidates") or []
    if not candidates:
        feedback = data.get("promptFeedback")
        raise RuntimeError(f"Gemini returned no candidates. {feedback or ''}".strip())
    parts = candidates[0].get("content", {}).get("parts", [])
    answer = "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict)).strip()
    if not answer:
        raise RuntimeError("Gemini returned an empty response.")
    return answer


def _generate_one(provider, prompt, settings, system_prompt, temperature, max_tokens, timeout):
    if provider == "Gemini":
        return _gemini_generate(prompt, settings, system_prompt, temperature, max_tokens, timeout)
    return _openai_compatible_generate(prompt, settings, provider, system_prompt, temperature, max_tokens, timeout)


def generate_text(prompt: str, settings: dict[str, Any] | None = None, *,
                  system_prompt: str = "", temperature: float = 0.2,
                  max_tokens: int = 1800, timeout: float = 180) -> str:
    settings = load_settings() if settings is None else dict(settings)
    providers = enabled_providers(settings)
    if len(providers) == 1:
        try:
            return _generate_one(providers[0], prompt, settings, system_prompt, temperature, max_tokens, timeout)
        except Exception as exc:
            raise RuntimeError(f"{providers[0]}: {_safe_error(exc, settings)}") from exc
    try:
        return _generate_one(providers[0], prompt, settings, system_prompt, temperature, max_tokens, timeout)
    except Exception as exc:
        raise RuntimeError(f"{providers[0]}: {_safe_error(exc, settings)}") from exc
