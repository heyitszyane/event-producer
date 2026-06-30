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

from pydantic import BaseModel, ValidationError

from event_producer.providers.agent_model import AgentModelResult
from event_producer.providers.model_env import ModelEnv


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
        if not self._env.api_key:
            return AgentModelResult(
                parsed=None,
                raw_text=None,
                model_mode="rule_based_fallback",
                model_name=None,
                fallback_reason=self._env.fallback_reason
                or "no Gemini API key provided",
                error="live Gemini has no API key",
            )

        try:
            client = self._get_client()
        except Exception as exc:
            return AgentModelResult(
                parsed=None,
                raw_text=None,
                model_mode="rule_based_fallback",
                model_name=self._env.model_name,
                fallback_reason=f"failed to import/construct Gemini SDK: {exc}",
                error=f"Gemini SDK unavailable: {exc}",
            )

        try:
            response = client.models.generate_content(
                model=self._env.model_name,
                contents=user_prompt,
                config=self._build_config(system_prompt),
            )
            raw_text = (response.text or "").strip()
        except Exception as exc:
            return AgentModelResult(
                parsed=None,
                raw_text=None,
                model_mode="rule_based_fallback",
                model_name=self._env.model_name,
                fallback_reason=f"Gemini API call failed: {exc}",
                error=f"Gemini API error: {exc}",
            )

        if not raw_text:
            return AgentModelResult(
                parsed=None,
                raw_text=None,
                model_mode="gemini_live",
                model_name=self._env.model_name,
                fallback_reason="Gemini returned an empty response; fallback interpretation applied",
                error="empty Gemini response",
            )

        data = _extract_json_object(raw_text)
        if data is None:
            return AgentModelResult(
                parsed=None,
                raw_text=raw_text,
                model_mode="gemini_live",
                model_name=self._env.model_name,
                fallback_reason="Gemini output was not valid JSON; deterministic interpretation applied",
                error="could not parse JSON from Gemini output",
            )

        try:
            parsed = schema(**data)
        except (ValidationError, TypeError, ValueError) as exc:
            return AgentModelResult(
                parsed=None,
                raw_text=raw_text,
                model_mode="gemini_live",
                model_name=self._env.model_name,
                fallback_reason=f"Gemini output did not match schema: {exc}",
                error=f"schema mismatch: {exc}",
            )

        return AgentModelResult(
            parsed=parsed,
            raw_text=raw_text,
            model_mode="gemini_live",
            model_name=self._env.model_name,
            fallback_reason=None,
            error=None,
        )

    # -- internals ----------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            # Lazy import: skip entirely on fallback/test installs.
            from google import genai

            self._client = genai.Client(api_key=self._env.require_key())
        return self._client

    def _build_config(self, system_prompt: str):
        # Imported lazily alongside the client to avoid a hard import at
        # module load. ``google-genai`` exposes generation config helpers.
        try:
            from google.genai import types

            return types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
            )
        except Exception:
            # Older SDK shape — fall back to a plain dict the client tolerates.
            return {"system_instruction": system_prompt}
