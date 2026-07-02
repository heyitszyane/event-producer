"""OpenAI-compatible live model provider.

Supports providers that expose ``/chat/completions`` with OpenAI-shaped
requests, including OpenRouter and local servers such as Ollama or LM Studio.
Like the Gemini provider, this class never mutates state and never raises for
normal model/transport degradation; callers receive an ``AgentModelResult`` and
can continue through the deterministic fallback path.
"""

from __future__ import annotations

import json
import logging
import re
import time
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from pydantic import BaseModel, ValidationError

from event_producer.providers.agent_model import AgentModelResult, LiveModelProviderError
from event_producer.providers.diagnostics import latency_ms, preview, pydantic_error_summary
from event_producer.providers.gemini_model import _extract_json_object
from event_producer.providers.model_env import ModelEnv
from event_producer.providers.schema_repair import repair_schema_output

_LOG = logging.getLogger(__name__)


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
        started = time.perf_counter()
        if not self._env.api_base_url:
            return self._failure(
                "no OpenAI-compatible API base URL configured",
                agent_name=agent_name,
                prompt_version=prompt_version,
                started=started,
            )

        base_payload = {
            "model": self._env.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "stream": False,
            "max_tokens": self._env.max_output_tokens,
        }
        attempts = self._payload_attempts(
            base_payload,
            schema=schema,
            agent_name=agent_name,
            prompt_version=prompt_version,
        )
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/heyitszyane/event-producer",
            "X-Title": "Event Producer",
        }
        if self._env.api_key:
            headers["Authorization"] = f"Bearer {self._env.api_key}"

        http_status: int | None = None
        response_shape_keys: list[str] = []
        raw_body = ""
        response_format_mode = "json_object"
        for index, (response_format_mode, payload) in enumerate(attempts):
            req = request.Request(
                self._env.api_base_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self._env.request_timeout_seconds) as resp:
                    http_status = getattr(resp, "status", None) or resp.getcode()
                    raw_body = resp.read().decode("utf-8")
                break
            except HTTPError as exc:
                http_status = exc.code
                body = _safe_decode(exc.read())
                detail = preview(body) or str(exc)
                can_retry = (
                    index == 0
                    and response_format_mode == "json_schema"
                    and len(attempts) > 1
                    and _is_json_schema_rejection(exc.code, body)
                )
                if can_retry:
                    _LOG.info(
                        "model_call retrying_json_object provider=%s model=%s agent=%s "
                        "prompt_version=%s http_status=%s reason=%s",
                        self._env.provider,
                        self._env.model_name,
                        agent_name,
                        prompt_version,
                        exc.code,
                        detail,
                    )
                    continue
                return self._failure(
                    f"{self._provider_title()} call failed: HTTP {exc.code}: {detail}",
                    agent_name=agent_name,
                    prompt_version=prompt_version,
                    started=started,
                    http_status=http_status,
                    raw_text=body,
                    response_preview=detail,
                    response_format_mode=response_format_mode,
                )
            except (URLError, TimeoutError, OSError) as exc:
                reason = (
                    f"{self._provider_title()} call failed: "
                    f"{exc.__class__.__name__}: {preview(str(exc))}"
                )
                return self._failure(
                    reason,
                    agent_name=agent_name,
                    prompt_version=prompt_version,
                    started=started,
                    response_format_mode=response_format_mode,
                )

        try:
            data = json.loads(raw_body)
            if isinstance(data, dict):
                response_shape_keys = sorted(str(k) for k in data.keys())[:20]
            raw_text = str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            return self._failure(
                f"{self._provider_title()} response was not chat-completions shaped: "
                f"{exc.__class__.__name__}: {preview(str(exc))}",
                agent_name=agent_name,
                prompt_version=prompt_version,
                started=started,
                http_status=http_status,
                raw_text=raw_body,
                response_shape_keys=response_shape_keys,
                response_preview=preview(raw_body),
                response_format_mode=response_format_mode,
            )

        self._log_call(
            agent_name=agent_name,
            prompt_version=prompt_version,
            latency_ms=latency_ms(started),
            http_status=http_status,
            response_shape_keys=response_shape_keys,
        )

        json_obj = _extract_json_object(raw_text)
        if json_obj is None:
            return self._failure(
                f"{self._provider_title()} output was not valid JSON; "
                "deterministic interpretation applied",
                agent_name=agent_name,
                prompt_version=prompt_version,
                started=started,
                http_status=http_status,
                raw_text=raw_body,
                response_shape_keys=response_shape_keys,
                response_preview=preview(raw_text),
                live_mode=True,
                response_format_mode=response_format_mode,
            )

        repair = repair_schema_output(
            schema=schema,
            agent_name=agent_name,
            original_user_prompt=user_prompt,
            decoded_json=json_obj,
        )
        parsed_shape_keys = sorted(str(k) for k in repair.data.keys())[:20]

        try:
            parsed = schema(**repair.data)
        except (ValidationError, TypeError, ValueError) as exc:
            return self._failure(
                f"{self._provider_title()} output did not match schema: "
                f"{pydantic_error_summary(exc)}",
                agent_name=agent_name,
                prompt_version=prompt_version,
                started=started,
                http_status=http_status,
                raw_text=raw_text,
                response_shape_keys=parsed_shape_keys,
                response_preview=preview(raw_text),
                live_mode=True,
                response_format_mode=response_format_mode,
                repaired_schema=repair.repaired_schema,
                repaired_fields=repair.repaired_fields,
            )

        return AgentModelResult(
            parsed=parsed,
            raw_text=raw_text,
            model_mode="openai_compatible_live",
            model_name=self._env.model_name,
            fallback_reason=None,
            error=None,
            provider=self._env.provider,
            effective_mode=self._env.effective_mode,
            agent_name=agent_name,
            prompt_version=prompt_version,
            ok=True,
            latency_ms=latency_ms(started),
            http_status=http_status,
            response_shape_keys=parsed_shape_keys,
            response_preview=preview(raw_text),
            response_format_mode=response_format_mode,
            repaired_schema=repair.repaired_schema,
            repaired_fields=repair.repaired_fields,
        )

    def _payload_attempts(
        self,
        base_payload: dict,
        *,
        schema: type[BaseModel],
        agent_name: str,
        prompt_version: str,
    ) -> list[tuple[str, dict]]:
        if self._env.provider in {"openrouter", "openai_compatible"}:
            schema_payload = dict(base_payload)
            schema_payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": safe_schema_name(agent_name, prompt_version),
                    "strict": True,
                    "schema": schema.model_json_schema(),
                },
            }
            if self._env.provider == "openrouter":
                schema_payload["provider"] = {"require_parameters": True}
            object_payload = dict(base_payload)
            object_payload["response_format"] = {"type": "json_object"}
            return [("json_schema", schema_payload), ("json_object", object_payload)]

        payload = dict(base_payload)
        payload["response_format"] = {"type": "json_object"}
        return [("json_object", payload)]

    def _failure(
        self,
        reason: str,
        *,
        agent_name: str,
        prompt_version: str,
        started: float,
        raw_text: str | None = None,
        live_mode: bool = False,
        http_status: int | None = None,
        response_shape_keys: list[str] | None = None,
        response_preview: str | None = None,
        response_format_mode: str | None = None,
        repaired_schema: bool = False,
        repaired_fields: list[str] | None = None,
    ) -> AgentModelResult:
        duration_ms = latency_ms(started)
        self._log_call(
            agent_name=agent_name,
            prompt_version=prompt_version,
            latency_ms=duration_ms,
            http_status=http_status,
            response_shape_keys=response_shape_keys or [],
            error=reason,
        )
        if self._env.strict_live_model and self._env.live_enabled:
            raise LiveModelProviderError(
                reason,
                provider=self._env.provider,
                effective_mode=self._env.effective_mode,
                model_name=self._env.model_name,
                agent_name=agent_name,
                prompt_version=prompt_version,
                http_status=http_status,
                response_shape_keys=response_shape_keys,
                fallback_reason="provider_call_failed",
                response_format_mode=response_format_mode,
                repaired_schema=repaired_schema,
                repaired_fields=repaired_fields,
            )
        return AgentModelResult(
            parsed=None,
            raw_text=raw_text,
            model_mode="openai_compatible_live" if live_mode else "rule_based_fallback",
            model_name=self._env.model_name,
            fallback_reason=reason,
            error=reason,
            provider=self._env.provider,
            effective_mode=self._env.effective_mode,
            agent_name=agent_name,
            prompt_version=prompt_version,
            ok=False,
            latency_ms=duration_ms,
            http_status=http_status,
            response_shape_keys=response_shape_keys or [],
            response_preview=response_preview or preview(raw_text),
            response_format_mode=response_format_mode,
            repaired_schema=repaired_schema,
            repaired_fields=repaired_fields or [],
        )

    def _provider_title(self) -> str:
        if self._env.provider == "openrouter":
            return "OpenRouter"
        return "OpenAI-compatible provider"

    def _log_call(
        self,
        *,
        agent_name: str,
        prompt_version: str,
        latency_ms: int,
        http_status: int | None,
        response_shape_keys: list[str],
        error: str | None = None,
    ) -> None:
        host = urlparse(self._env.api_base_url).netloc
        _LOG.info(
            "model_call provider=%s mode=%s model=%s host=%s agent=%s "
            "prompt_version=%s latency_ms=%s http_status=%s response_shape_keys=%s ok=%s",
            self._env.provider,
            self._env.effective_mode,
            self._env.model_name,
            host,
            agent_name,
            prompt_version,
            latency_ms,
            http_status,
            response_shape_keys,
            error is None,
        )


def _safe_decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def safe_schema_name(agent_name: str, prompt_version: str) -> str:
    raw = f"{agent_name}_{prompt_version}".strip("_")
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw)[:64].strip("_")
    return safe or "event_producer_schema"


def _is_json_schema_rejection(http_status: int, body: str) -> bool:
    if http_status not in {400, 422}:
        return False
    low = body.lower()
    return any(
        needle in low
        for needle in (
            "json_schema",
            "response_format",
            "require_parameters",
            "unsupported parameter",
            "unsupported_param",
            "invalid parameter",
        )
    )
