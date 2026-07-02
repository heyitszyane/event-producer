"""OpenAI-compatible live model provider.

Supports providers that expose ``/chat/completions`` with OpenAI-shaped
requests, including OpenRouter and local servers such as Ollama or LM Studio.
Like the Gemini provider, this class never mutates state and never raises for
normal model/transport degradation; callers receive an ``AgentModelResult`` and
can continue through the deterministic fallback path.
"""

from __future__ import annotations

import json
from urllib import request
from urllib.error import HTTPError, URLError

from pydantic import BaseModel, ValidationError

from event_producer.providers.agent_model import AgentModelResult
from event_producer.providers.gemini_model import _extract_json_object
from event_producer.providers.model_env import ModelEnv


class OpenAICompatibleModel:
    """Live provider for OpenAI-compatible chat-completions endpoints."""

    def __init__(self, env: ModelEnv) -> None:
        self._env = env

    def generate_structured(
        self,
        *,
        agent_name: str,
        prompt_version: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
    ) -> AgentModelResult:
        if not self._env.api_base_url:
            return self._fallback("no OpenAI-compatible API base URL configured")

        payload = {
            "model": self._env.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/heyitszyane/event-producer",
            "X-Title": "Event Producer",
        }
        if self._env.api_key:
            headers["Authorization"] = f"Bearer {self._env.api_key}"
        req = request.Request(
            self._env.api_base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=30) as resp:
                raw_body = resp.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            detail = body.strip()[:500] if body else str(exc)
            return self._fallback(
                f"OpenAI-compatible API call failed ({exc.code}): {detail}"
            )
        except (URLError, TimeoutError, OSError) as exc:
            return self._fallback(f"OpenAI-compatible API call failed: {exc}")

        try:
            data = json.loads(raw_body)
            raw_text = str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            return self._fallback(
                f"OpenAI-compatible response was not chat-completions shaped: {exc}",
                raw_text=raw_body,
            )

        json_obj = _extract_json_object(raw_text)
        if json_obj is None:
            return self._fallback(
                "OpenAI-compatible output was not valid JSON; deterministic interpretation applied",
                raw_text=raw_text,
                live_mode=True,
            )

        try:
            parsed = schema(**json_obj)
        except (ValidationError, TypeError, ValueError) as exc:
            return self._fallback(
                f"OpenAI-compatible output did not match schema: {exc}",
                raw_text=raw_text,
                live_mode=True,
            )

        return AgentModelResult(
            parsed=parsed,
            raw_text=raw_text,
            model_mode="openai_compatible_live",
            model_name=self._env.model_name,
            fallback_reason=None,
            error=None,
        )

    def _fallback(
        self,
        reason: str,
        *,
        raw_text: str | None = None,
        live_mode: bool = False,
    ) -> AgentModelResult:
        return AgentModelResult(
            parsed=None,
            raw_text=raw_text,
            model_mode="openai_compatible_live" if live_mode else "rule_based_fallback",
            model_name=self._env.model_name,
            fallback_reason=reason,
            error=reason,
        )
