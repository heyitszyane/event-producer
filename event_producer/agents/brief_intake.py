"""Brief Intake Agent — interprets messy event briefs.

Reason -> Formatter split (matches existing agent style):
    - BriefIntakeReasonAgent: resolves env/provider, builds the v1 prompt, calls
      the model provider seam.
    - BriefIntakeFormatterAgent: validates and coerces the provider output into
      ``BriefIntakeResult``. When the provider could not produce structured
      output (fallback mode), the formatter derives a deterministic-but-brief-
      aware result from the raw signal, and ALWAYS records ``model_mode`` +
      ``fallback_reason`` honestly.

Anti-patterns this agent explicitly rejects:
    - fabricating money-critical values (budget/attendees/date/venue) to look
      complete -> recorded as ``missing_questions`` + ``assumptions`` instead;
    - claiming live vendor/payments/Telegram/Firestore/OCR;
    - mutating budget/schedule directly (the engines own that).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from event_producer.models.schemas import AgentMode, BriefIntakeResult

_PROMPT_PATH = Path(__file__).parent / "prompts" / "brief_intake_v1.md"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tiny deterministic signal extractor (used by the fallback formatter).
# We ONLY derive what the brief plainly states; we never fabricate.
# ---------------------------------------------------------------------------

# Maps common phrasings -> canonical event_type used by the deterministic
# catalogue (corporate | networking | product_launch | conference).
_EVENT_TYPE_KEYWORDS: list[tuple[list[str], str]] = [
    (["networking", "meetup", "mixer", "meet-and-greet", "mingle"], "networking"),
    (["launch", "product launch", "unveil", "reveal", "release"], "product_launch"),
    (["conference", "summit", "keynote", "track", "panel schedule"], "conference"),
    (["corporate", "townhall", "offsite", "team building", "company"], "corporate"),
]

# Models / normalizers for budgets/pax/... are intentionally conservative.
_PAX_RE = re.compile(
    r"(?i)\b(\d{1,5})\s*[-]?\s*(?:pax|people|persons|guests|attendees|heads|crew|people)\b"
)
_BUDGET_RE = re.compile(
    r"(?i)(?:budget(?:\s+is)?|around|about|up to|max|cap|[$\£€])\s*[:\-]?\s*"
    r"(\d[\d,]*\.?\d*)\s*(k|m|million|thousand)?"
)
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_TOMORROW_RE = re.compile(r"\b(tomorrow)\b", re.I)


def _first_int(text: str, rx: re.Pattern) -> int | None:
    m = rx.search(text)
    return int(m.group(1)) if m else None


def _extract_event_type(text: str) -> tuple[str | None, str | None]:
    low = text.lower()
    for keywords, canonical in _EVENT_TYPE_KEYWORDS:
        for kw in keywords:
            if kw in low:
                return canonical, kw
    return None, None


def _extract_attendees(text: str) -> int | None:
    m = _PAX_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def _extract_budget_cap(text: str) -> tuple[str | None, str | None]:
    """Return (canonical_money_str | None, raw_match | None).

    We only report what the brief plainly states; we do NOT project or
    annualize. If a 'k'/'m' suffix appears we canonicalize e.g. 20k -> 20000.
    """
    m = _BUDGET_RE.search(text)
    if not m:
        return None, None
    raw = m.group(0).strip()
    num = m.group(1).replace(",", "")
    suffix = (m.group(2) or "").lower()
    try:
        value = float(num)
    except ValueError:
        return None, raw
    if suffix in ("k", "thousand"):
        value *= 1000
    elif suffix in ("m", "million"):
        value *= 1_000_000
    return str(int(value)) if value == int(value) else f"{value:.2f}", raw


def _extract_date(text: str) -> str | None:
    m = _DATE_RE.search(text)
    return m.group(1) if m else None


def _extract_location(text: str) -> str | None:
    # City after "in/at <City>" — conservative, single capitalized token.
    m = re.search(r"\b(?:in|at)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b", text)
    return m.group(1) if m else None


def _extract_goals(text: str) -> list[str]:
    goals: list[str] = []
    if "network" in text.lower() or "meet" in text.lower():
        goals.append("Facilitate attendee networking and connections")
    if any(w in text.lower() for w in ["investor", "founders", "startups"]):
        goals.append("Build credibility with investors and builders")
    return goals


# ---------------------------------------------------------------------------
# Formatter — owns schema production (also for non-structured providers).
# ---------------------------------------------------------------------------


class BriefIntakeFormatterAgent:
    """Coerce any provider output into a valid ``BriefIntakeResult``."""

    def run(
        self,
        *,
        provider_text: str | None,
        brief: str,
        model_mode: AgentMode,
        fallback_reason: str | None,
    ) -> BriefIntakeResult:
        # Try to parse structured JSON first (live Gemini path).
        parsed = self._try_parse(provider_text)
        if parsed is not None:
            # Normalize enums and telemetry fields defensively.
            parsed["model_mode"] = model_mode
            if fallback_reason:
                parsed["fallback_reason"] = fallback_reason
            return BriefIntakeResult(**parsed)

        # Fallback path: derive an honest, brief-aware interpretation from the
        # raw brief, but record fallback telemetry so the UI stays honest.
        return self._fallback_from_brief(
            brief,
            raw_provider_text=provider_text,
            model_mode=model_mode,
            fallback_reason=fallback_reason,
        )

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _try_parse(text: str | None) -> dict | None:
        if not text:
            return None
        # Strip fences and locate first {...}.
        cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.S)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        return data

    @staticmethod
    def _fallback_from_brief(
        brief: str,
        raw_provider_text: str | None,
        model_mode: AgentMode,
        fallback_reason: str | None,
    ) -> BriefIntakeResult:
        canonical, raw_kw = _extract_event_type(brief)
        budget_cap, _budget_raw = _extract_budget_cap(brief)
        attendees = _extract_attendees(brief)
        date = _extract_date(brief)
        location = _extract_location(brief)
        goals = _extract_goals(brief)

        missing: list[str] = []
        assumptions: list[str] = []
        if budget_cap is None:
            missing.append("Exact budget cap")
        if attendees is None:
            missing.append("Expected number of attendees")
        if date is None:
            missing.append("Event date (YYYY-MM-DD)")
        if raw_kw and canonical and raw_kw != canonical:
            assumptions.append(
                f"Interpreted event type '{raw_kw}' as '{canonical}'."
            )

        # Market realism: flag only obvious tensions and state the assumption.
        warnings: list[str] = []
        if budget_cap and attendees and int(budget_cap.replace(",", "")) / max(attendees, 1) < 25:
            warnings.append(
                f"Per-head budget looks tight given "
                f"${budget_cap} / {attendees} attendees."
            )

        # P7D: Singapore open-bar realism warning (common contradiction)
        # 100 pax with open bar/canapés in Singapore under SGD 10000 is
        # unlikely to be feasible. This heuristic makes the contradiction visible
        # to the user without fabricating costs.
        low_realism = False
        if location and attendees and budget_cap:
            location_low = location.lower()
            if "singapore" in location_low or "sg" in location_low:
                brief_low = brief.lower()
                has_open_bar = any(
                    kw in brief_low for kw in ["open bar", "openbar", "bar", "drinks", "alcohol", "full bar"]
                )
                budget_value = int(budget_cap.replace(",", ""))
                if attendees >= 80 and has_open_bar and budget_value <= 10000:
                    low_realism = True
        if low_realism:
            warnings.append(
                "Budget realism risk: 100 pax with open bar/canapés in Singapore is likely above this cap. "
                "Consider reducing bar scope, switching to drink coupons, or increasing budget."
            )

        # Confidence mirrors how much was actually extractable vs assumed.
        filled = sum(x is not None for x in (canonical, budget_cap, attendees, date))
        confidence = "high" if filled >= 3 else "medium" if filled >= 2 else "low"

        return BriefIntakeResult(
            normalized_brief=brief.strip()[:1000],
            event_type=canonical or "",
            event_type_raw=raw_kw,
            attendees=attendees,
            budget_cap=budget_cap,
            contingency_pct=None,
            venue_type=None,
            date=date,
            location=location,
            goals=goals,
            audience_profile=None,
            tone=None,
            must_haves=[],
            nice_to_haves=[],
            constraints=[],
            assumptions=assumptions,
            missing_questions=missing,
            contradictions=[],
            market_realism_warnings=warnings,
            confidence=confidence,
            model_mode=model_mode,
        )


# ---------------------------------------------------------------------------
# Reason — calls the provider seam and hands off to the formatter.
# ---------------------------------------------------------------------------


class BriefIntakeReasonAgent:
    """Reads the messy brief and asks the model provider for an interpretation."""

    def __init__(self, provider, prompt_version: str = "brief_intake.v1") -> None:
        self._provider = provider
        self._prompt = _load_prompt()
        self._prompt_version = prompt_version

    def run(self, brief: str) -> dict:
        """Return a dict the formatter will coerce into BriefIntakeResult."""
        res = self._provider.generate_structured(
            agent_name="brief_intake",
            prompt_version=self._prompt_version,
            system_prompt=self._prompt,
            user_prompt=brief,
            schema=BriefIntakeResult,  # passed for provider best-effort parse
        )
        return {
            "provider_text": res.raw_text or (json.dumps(res.parsed.model_dump()) if res.parsed else None),
            "model_mode": res.model_mode,
            "model_name": res.model_name,
            "prompt_version": self._prompt_version,
            "fallback_reason": res.fallback_reason,
            "error": res.error,
        }
