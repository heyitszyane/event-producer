"""Tests for P7H.5 live structured-output hardening."""

from __future__ import annotations

import io
import json
import sys
import types
from urllib.error import HTTPError

from fastapi.testclient import TestClient

from event_producer.api import create_app
from event_producer.models.schemas import BriefIntakeResult
from event_producer.providers.agent_model import LiveModelProviderError
from event_producer.providers.gemini_model import GeminiModel
from event_producer.providers.model_env import ModelEnv
from event_producer.providers.openai_compatible_model import OpenAICompatibleModel
from event_producer.providers.schema_repair import repair_schema_output


class _FakeHTTPResponse:
    def __init__(self, body: dict) -> None:
        self.status = 200
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self) -> bytes:
        return self._body


def _openrouter_env(*, strict: bool = True) -> ModelEnv:
    return ModelEnv(
        provider="openrouter",
        live_enabled=True,
        api_key="test-key",
        model_name="google/gemini-2.5-flash",
        api_base_url="https://openrouter.ai/api/v1/chat/completions",
        fallback_reason="",
        strict_live_model=strict,
    )


def _chat_body(content: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(content)}}]}


def test_openrouter_sends_json_schema_response_format_first(monkeypatch) -> None:
    seen_payloads: list[dict] = []

    def fake_urlopen(req, timeout):
        seen_payloads.append(json.loads(req.data.decode("utf-8")))
        return _FakeHTTPResponse(
            _chat_body(
                {
                    "normalized_brief": "Need a networking event.",
                    "event_type": "networking",
                    "tone": None,
                    "assumptions": [],
                    "missing_questions": [],
                }
            )
        )

    monkeypatch.setattr(
        "event_producer.providers.openai_compatible_model.request.urlopen",
        fake_urlopen,
    )

    result = OpenAICompatibleModel(_openrouter_env()).generate_structured(
        agent_name="brief_intake",
        prompt_version="brief_intake.v1",
        system_prompt="Return JSON.",
        user_prompt="Need a networking event.",
        schema=BriefIntakeResult,
    )

    assert result.ok is True
    assert result.response_format_mode == "json_schema"
    assert seen_payloads[0]["response_format"]["type"] == "json_schema"
    assert seen_payloads[0]["response_format"]["json_schema"]["strict"] is True
    assert seen_payloads[0]["provider"]["require_parameters"] is True


def test_openrouter_retries_json_object_when_json_schema_is_rejected(monkeypatch) -> None:
    seen_payloads: list[dict] = []

    def fake_urlopen(req, timeout):
        payload = json.loads(req.data.decode("utf-8"))
        seen_payloads.append(payload)
        if payload["response_format"]["type"] == "json_schema":
            raise HTTPError(
                req.full_url,
                400,
                "bad request",
                hdrs=None,
                fp=io.BytesIO(b'{"error":"unsupported parameter response_format json_schema"}'),
            )
        return _FakeHTTPResponse(
            _chat_body(
                {
                    "normalized_brief": "Need a networking event.",
                    "event_type": "networking",
                    "tone": None,
                    "assumptions": [],
                    "missing_questions": [],
                }
            )
        )

    monkeypatch.setattr(
        "event_producer.providers.openai_compatible_model.request.urlopen",
        fake_urlopen,
    )

    result = OpenAICompatibleModel(_openrouter_env()).generate_structured(
        agent_name="brief_intake",
        prompt_version="brief_intake.v1",
        system_prompt="Return JSON.",
        user_prompt="Need a networking event.",
        schema=BriefIntakeResult,
    )

    assert result.ok is True
    assert result.response_format_mode == "json_object"
    assert [p["response_format"]["type"] for p in seen_payloads] == [
        "json_schema",
        "json_object",
    ]


def test_brief_intake_repair_handles_harmless_schema_mismatches() -> None:
    original = "Need a premium networking event in Singapore. Budget is 10000."
    repair = repair_schema_output(
        schema=BriefIntakeResult,
        agent_name="brief_intake",
        original_user_prompt=original,
        decoded_json={
            "event_type": "networking",
            "budget_cap": 10000,
            "tone": None,
            "assumptions": [{"basis": "brief says networking"}],
        },
    )

    parsed = BriefIntakeResult(**repair.data)

    assert parsed.normalized_brief == original
    assert parsed.budget_cap == "10000"
    assert parsed.tone is None
    assert parsed.assumptions == ['{"basis":"brief says networking"}']
    assert parsed.attendees is None
    assert "attendees" not in repair.repaired_fields


def test_strict_live_still_502s_when_output_is_unrecoverably_invalid(monkeypatch) -> None:
    class _UnrecoverableProvider:
        def generate_structured(self, **kwargs):
            raise LiveModelProviderError(
                "OpenRouter output did not match schema: event_type: Input should be a valid string",
                provider="openrouter",
                effective_mode="openai_compatible_live",
                model_name="google/gemini-2.5-flash",
                agent_name=kwargs["agent_name"],
                prompt_version=kwargs["prompt_version"],
                response_format_mode="json_schema",
                repaired_schema=True,
                repaired_fields=["normalized_brief"],
                fallback_reason="provider_call_failed",
            )

    monkeypatch.setenv("ENABLE_LIVE_MODEL", "true")
    monkeypatch.setenv("STRICT_LIVE_MODEL", "true")
    monkeypatch.setenv("MODEL_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-openrouter")
    app = create_app()
    app.state.event_producer._agent_model = _UnrecoverableProvider()
    app.state.event_producer._brief_intake_reason._provider = app.state.event_producer._agent_model
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    response = client.post("/run", json={"brief": "Need a networking event."})

    assert response.status_code == 502
    data = response.json()
    assert data["error"]["code"] == "LIVE_MODEL_PROVIDER_FAILED"
    assert data["error"]["response_format_mode"] == "json_schema"
    assert data["error"]["repaired_schema"] is True
    assert "secret-openrouter" not in str(data)


def test_gemini_config_uses_response_schema_when_sdk_supports_it(monkeypatch) -> None:
    captured: dict = {}

    class _Config:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    fake_types = types.SimpleNamespace(GenerateContentConfig=_Config)
    fake_genai = types.ModuleType("google.genai")
    fake_genai.types = fake_types
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    config, mode = GeminiModel(_openrouter_env())._build_config("system", BriefIntakeResult)

    assert isinstance(config, _Config)
    assert mode == "json_schema"
    assert captured["response_schema"] is BriefIntakeResult
    assert captured["response_mime_type"] == "application/json"


def test_gemini_config_falls_back_when_response_schema_is_not_supported(monkeypatch) -> None:
    captured: dict = {}

    class _Config:
        def __init__(self, **kwargs) -> None:
            if "response_schema" in kwargs:
                raise TypeError("unexpected response_schema")
            captured.update(kwargs)

    fake_types = types.SimpleNamespace(GenerateContentConfig=_Config)
    fake_genai = types.ModuleType("google.genai")
    fake_genai.types = fake_types
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    config, mode = GeminiModel(_openrouter_env())._build_config("system", BriefIntakeResult)

    assert isinstance(config, _Config)
    assert mode == "json_object"
    assert "response_schema" not in captured
    assert captured["response_mime_type"] == "application/json"
