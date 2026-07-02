"""Live Gemini provider (lazy, server-side only).

Responsibilities:
    - Import the ``google-genai`` SDK lazily and ONLY when live mode is enabled
      and a key is present. Importing at module top-level would break
      fallback/test installs that do not have the SDK.
    - Send system + user prompts without invoking code tools.
    - Parse the model text output into the requested Pydantic ``schema``.
    - On any failure to produce valid structured output, return
      ``parsed=None`` with ``error`` + ``fallback_reason`` set (instead of
      raising) so the caller can record a trace step and continue with the
      deterministic pipeline.

It does NOT: perform budget math, mutate event state, or claim success on
invalid output. Those stay in the deterministic engines and the action-gate.
"""

from __future__ import annotations

import json
import re
import time

from pydantic import BaseModel, ValidationError

from event_producer.providers.agent_model import AgentModelResult, LiveModelProviderError
from event_producer.providers.diagnostics import latency_ms, preview, pydantic_error_summary
from event_producer.providers.model_env import ModelEnv
from event_producer.providers.schema_repair import repair_schema_output


def _extract_json_object(text: str) -> dict | None:
    """Best-effort extraction of a JSON object out of free model text."""
    if not text:
        return None
    # Prefer fenced code blocks.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    # Then the first {...} span that parses.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


class GeminiModel:
    """Live, server-side Gemini provider bound to a resolved ``ModelEnv``."""

    def __init__(self, env: ModelEnv) -> None:
        self._env = env
        self._client = None  # constructed lazily

    # -- public API ---------------------------------------------------------

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
        if not self._env.api_key:
            return self._failure(
                self._env.fallback_reason or "no Gemini API key provided",
                agent_name=agent_name,
                prompt_version=prompt_version,
                started=started,
            )

        try:
            client = self._get_client()
        except Exception as exc:
            return self._failure(
                f"Gemini SDK unavailable: {preview(str(exc))}",
                agent_name=agent_name,
                prompt_version=prompt_version,
                started=started,
            )

        try:
            config, response_format_mode = self._build_config(system_prompt, schema)
            response = client.models.generate_content(
                model=self._env.model_name,
                contents=user_prompt,
                config=config,
            )
            raw_text = (response.text or "").strip()
        except Exception as exc:
            return self._failure(
                f"Gemini API call failed: {exc.__class__.__name__}: {preview(str(exc))}",
                agent_name=agent_name,
                prompt_version=prompt_version,
                started=started,
                response_format_mode="json_object",
            )

        if not raw_text:
            return self._failure(
                "Gemini returned an empty response; fallback interpretation applied",
                agent_name=agent_name,
                prompt_version=prompt_version,
                started=started,
                live_mode=True,
            )

        data = _extract_json_object(raw_text)
        if data is None:
            return self._failure(
                "Gemini output was not valid JSON; deterministic interpretation applied",
                agent_name=agent_name,
                prompt_version=prompt_version,
                started=started,
                raw_text=raw_text,
                response_preview=preview(raw_text),
                live_mode=True,
                response_format_mode=response_format_mode,
            )

        repair = repair_schema_output(
            schema=schema,
            agent_name=agent_name,
            original_user_prompt=user_prompt,
            decoded_json=data,
        )

        try:
            parsed = schema(**repair.data)
        except (ValidationError, TypeError, ValueError) as exc:
            return self._failure(
                f"Gemini output did not match schema: {pydantic_error_summary(exc)}",
                agent_name=agent_name,
                prompt_version=prompt_version,
                started=started,
                raw_text=raw_text,
                response_shape_keys=sorted(str(k) for k in repair.data.keys())[:20],
                response_preview=preview(raw_text),
                live_mode=True,
                response_format_mode=response_format_mode,
                repaired_schema=repair.repaired_schema,
                repaired_fields=repair.repaired_fields,
            )

        return AgentModelResult(
            parsed=parsed,
            raw_text=raw_text,
            model_mode="gemini_live",
            model_name=self._env.model_name,
            fallback_reason=None,
            error=None,
            provider=self._env.provider,
            effective_mode=self._env.effective_mode,
            agent_name=agent_name,
            prompt_version=prompt_version,
            ok=True,
            latency_ms=latency_ms(started),
            http_status=None,
            response_shape_keys=sorted(str(k) for k in repair.data.keys())[:20],
            response_preview=preview(raw_text),
            response_format_mode=response_format_mode,
            repaired_schema=repair.repaired_schema,
            repaired_fields=repair.repaired_fields,
        )

    # -- internals ----------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            # Lazy import: skip entirely on fallback/test installs.
            from google import genai

            self._client = genai.Client(api_key=self._env.require_key())
        return self._client

    def _build_config(
        self,
        system_prompt: str,
        schema: type[BaseModel] | None = None,
    ):
        # Imported lazily alongside the client to avoid a hard import at
        # module load. ``google-genai`` exposes generation config helpers.
        try:
            from google.genai import types

            if schema is not None:
                for response_schema in (schema, schema.model_json_schema()):
                    try:
                        return (
                            types.GenerateContentConfig(
                                system_instruction=system_prompt,
                                response_mime_type="application/json",
                                temperature=0,
                                max_output_tokens=self._env.max_output_tokens,
                                response_schema=response_schema,
                            ),
                            "json_schema",
                        )
                    except TypeError:
                        continue
            return (
                types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0,
                    max_output_tokens=self._env.max_output_tokens,
                ),
                "json_object",
            )
        except Exception:
            # Older SDK shape — fall back to a plain dict the client tolerates.
            return {
                "system_instruction": system_prompt,
                "temperature": 0,
                "max_output_tokens": self._env.max_output_tokens,
            }, "json_object"

    def _failure(
        self,
        reason: str,
        *,
        agent_name: str,
        prompt_version: str,
        started: float,
        raw_text: str | None = None,
        response_shape_keys: list[str] | None = None,
        response_preview: str | None = None,
        response_format_mode: str | None = None,
        repaired_schema: bool = False,
        repaired_fields: list[str] | None = None,
        live_mode: bool = False,
    ) -> AgentModelResult:
        duration_ms = latency_ms(started)
        if self._env.strict_live_model and self._env.live_enabled:
            raise LiveModelProviderError(
                reason,
                provider=self._env.provider,
                effective_mode=self._env.effective_mode,
                model_name=self._env.model_name,
                agent_name=agent_name,
                prompt_version=prompt_version,
                response_shape_keys=response_shape_keys,
                fallback_reason="provider_call_failed",
                response_format_mode=response_format_mode,
                repaired_schema=repaired_schema,
                repaired_fields=repaired_fields,
            )
        return AgentModelResult(
            parsed=None,
            raw_text=raw_text,
            model_mode="gemini_live" if live_mode else "rule_based_fallback",
            model_name=self._env.model_name,
            fallback_reason=reason,
            error=reason,
            provider=self._env.provider,
            effective_mode=self._env.effective_mode,
            agent_name=agent_name,
            prompt_version=prompt_version,
            ok=False,
            latency_ms=duration_ms,
            response_shape_keys=response_shape_keys or [],
            response_preview=response_preview or preview(raw_text),
            response_format_mode=response_format_mode,
            repaired_schema=repaired_schema,
            repaired_fields=repaired_fields or [],
        )
