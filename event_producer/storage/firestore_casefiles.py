"""Firestore-backed casefile persistence for hosted demos.

The local JSON store remains the default for clone-and-run workflows. This
store is opt-in via ``CASEFILE_STORE=firestore`` and keeps each browser demo
session scoped under its own owner document, using the ``X-Demo-User`` header
captured in ``casefile_context``.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from event_producer.models.schemas import (
    CasefileArtifact,
    CasefileState,
    CasefileSummary,
    EventBasics,
)
from event_producer.storage.casefile_context import get_demo_user
from event_producer.storage.local_casefiles import (
    build_next_best_step,
    build_requirements_payload,
    resolve_event_state,
    utc_now,
)

DEFAULT_COLLECTION = "event_producer_demo_users"


def _firestore_safe(payload: Any) -> Any:
    """Coerce an arbitrary artifact/timeline payload into Firestore-safe types.

    The Firestore client cannot encode values such as ``Decimal`` (used by the
    Budget Engine for exact money math). Round-tripping through JSON with
    ``default=str`` mirrors exactly what the local JSON store persists, so both
    stores hand the frontend the same shape (e.g. money values as strings).
    """
    return json.loads(json.dumps(payload, default=str))


class FirestoreCasefileStore:
    """Casefile store using Firestore documents and artifact subcollections."""

    storage_kind = "firestore"

    def __init__(
        self,
        client: Any | None = None,
        *,
        collection: str | None = None,
        project: str | None = None,
    ) -> None:
        self.collection = collection or os.environ.get(
            "EVENT_PRODUCER_FIRESTORE_COLLECTION",
            DEFAULT_COLLECTION,
        )
        if client is None:
            try:
                from google.cloud import firestore  # type: ignore[import-untyped]
            except ImportError as exc:  # pragma: no cover - dependency is deployment-only
                raise RuntimeError(
                    "CASEFILE_STORE=firestore requires google-cloud-firestore. "
                    "Install dependencies from requirements.txt."
                ) from exc
            client = firestore.Client(project=project or os.environ.get("GOOGLE_CLOUD_PROJECT"))
        self._client = client

    def create_casefile(
        self, basics: EventBasics, brief: str = "", event_id: str | None = None
    ) -> CasefileState:
        event_id = event_id or str(uuid.uuid4())
        now = utc_now()
        state = CasefileState(
            event_id=event_id,
            created_at=now,
            updated_at=now,
            basics=basics,
            brief=brief,
            resolved=resolve_event_state(
                basics,
                brief,
                user_fields={
                    field
                    for field, value in basics.model_dump().items()
                    if value not in ("", None)
                },
            ),
        )
        self._casefile_ref(event_id).set(self._persistable_state(state))
        self.append_timeline(event_id, "casefile_created", {"status": state.status})
        return self.get_casefile(event_id)

    def delete_casefile(self, event_id: str) -> None:
        self.get_casefile(event_id)
        casefile_ref = self._casefile_ref(event_id)
        for collection_name in ("artifacts", "timeline"):
            for doc in casefile_ref.collection(collection_name).stream():
                doc.reference.delete()
        casefile_ref.delete()

    def list_casefiles(self) -> list[CasefileSummary]:
        summaries: list[CasefileSummary] = []
        for snapshot in self._casefiles_ref().stream():
            if not snapshot.exists:
                continue
            try:
                summaries.append(self.summary_for(self._state_from_snapshot(snapshot.to_dict() or {})))
            except Exception:
                continue
        return sorted(summaries, key=lambda item: item.updated_at, reverse=True)

    def get_casefile(self, event_id: str) -> CasefileState:
        snapshot = self._casefile_ref(event_id).get()
        if not snapshot.exists:
            raise FileNotFoundError(event_id)
        return self._enrich_state(self._state_from_snapshot(snapshot.to_dict() or {}))

    def update_basics(self, event_id: str, basics: EventBasics) -> CasefileState:
        state = self.get_casefile(event_id)
        state.basics = basics
        state.resolved = resolve_event_state(
            basics,
            state.brief,
            user_fields={
                field
                for field, value in basics.model_dump().items()
                if value not in ("", None)
            },
        )
        if state.status == "requirements_confirmed":
            state.status = "generated" if state.artifacts else "draft"
        state.requirements_confirmed_at = None
        state.requirements_confirmed_by = None
        state.updated_at = utc_now()
        self._casefile_ref(event_id).set(self._persistable_state(state))
        self.append_timeline(event_id, "event_basics_updated", {"fields": list(basics.model_dump().keys())})
        return self.get_casefile(event_id)

    def update_brief(self, event_id: str, brief: str) -> CasefileState:
        state = self.get_casefile(event_id)
        state.brief = brief
        state.resolved = resolve_event_state(state.basics, brief)
        if state.status == "requirements_confirmed":
            state.status = "generated" if state.artifacts else "draft"
        state.requirements_confirmed_at = None
        state.requirements_confirmed_by = None
        state.updated_at = utc_now()
        self._casefile_ref(event_id).set(self._persistable_state(state))
        self.append_timeline(event_id, "brief_saved", {"length": len(brief)})
        return self.get_casefile(event_id)

    def mark_generated(self, event_id: str, planning_assumptions: dict[str, Any]) -> CasefileState:
        state = self.get_casefile(event_id)
        if state.status != "requirements_confirmed":
            state.status = "generated"
        state.planning_assumptions = {
            **(state.planning_assumptions or {}),
            **planning_assumptions,
        }
        state.updated_at = utc_now()
        self._casefile_ref(event_id).set(self._persistable_state(state))
        return self.get_casefile(event_id)

    def confirm_requirements(self, event_id: str, actor: str = "demo-user") -> CasefileState:
        state = self.get_casefile(event_id)
        now = utc_now()
        state.status = "requirements_confirmed"
        state.requirements_confirmed_at = now
        state.requirements_confirmed_by = actor
        state.updated_at = now
        self._casefile_ref(event_id).set(self._persistable_state(state))
        self.append_timeline(event_id, "requirements_confirmed", {"actor": actor})
        return self.get_casefile(event_id)

    def dismiss_market_realism_warning(self, event_id: str, warning: str) -> CasefileState:
        state = self.get_casefile(event_id)
        planning = dict(state.planning_assumptions or {})
        dismissed = [
            str(item)
            for item in planning.get("dismissed_market_realism_warnings", [])
            if str(item).strip()
        ]
        if warning not in dismissed:
            dismissed.append(warning)
        planning["dismissed_market_realism_warnings"] = dismissed
        state.planning_assumptions = planning
        state.updated_at = utc_now()
        self._casefile_ref(event_id).set(self._persistable_state(state))
        self.append_timeline(event_id, "market_realism_warning_dismissed", {"warning": warning})
        return self.get_casefile(event_id)

    def update_run_sheet_task_status(
        self,
        event_id: str,
        task_id: str,
        *,
        status: str,
        notes: str | None = None,
    ) -> CasefileState:
        state = self.get_casefile(event_id)
        planning = dict(state.planning_assumptions or {})
        overrides = {
            str(key): dict(value)
            for key, value in (planning.get("run_sheet_task_overrides") or {}).items()
            if isinstance(value, dict)
        }
        current = dict(overrides.get(task_id, {}))
        current["status"] = status
        if notes is not None:
            current["notes"] = notes
        current["updated_at"] = utc_now()
        overrides[task_id] = current
        planning["run_sheet_task_overrides"] = overrides
        state.planning_assumptions = planning
        state.updated_at = utc_now()
        self._casefile_ref(event_id).set(self._persistable_state(state))
        self.append_timeline(
            event_id,
            "run_sheet_task_status_updated",
            {"task_id": task_id, "status": status},
        )
        return self.get_casefile(event_id)

    def write_artifact(self, event_id: str, name: str, payload: Any) -> CasefileArtifact:
        self.get_casefile(event_id)
        now = utc_now()
        artifact = CasefileArtifact(
            name=name,
            path=f"artifacts/{name}",
            updated_at=now,
        )
        self._artifact_ref(event_id, name).set(
            {"payload": _firestore_safe(payload), "updated_at": now}
        )
        state = self.get_casefile(event_id)
        state.artifacts[name] = artifact
        state.updated_at = utc_now()
        self._casefile_ref(event_id).set(self._persistable_state(state))
        self.append_timeline(event_id, "artifact_saved", {"name": name, "path": artifact.path})
        return artifact

    def read_artifact(self, event_id: str, name: str) -> Any:
        snapshot = self._artifact_ref(event_id, name).get()
        if not snapshot.exists:
            raise FileNotFoundError(f"{event_id}/{name}")
        data = snapshot.to_dict() or {}
        return data.get("payload")

    def append_timeline(self, event_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        entry = {
            "timestamp": utc_now(),
            "type": event_type,
            "payload": _firestore_safe(payload or {}),
        }
        self._casefile_ref(event_id).collection("timeline").document().set(entry)

    def summary_for(self, state: CasefileState) -> CasefileSummary:
        basics = state.resolved.basics
        return CasefileSummary(
            event_id=state.event_id,
            working_title=basics.working_title,
            country=basics.country,
            city=basics.city,
            start_date=basics.start_date,
            end_date=basics.end_date,
            expected_turnout=basics.expected_turnout,
            updated_at=state.updated_at,
            status=state.status,
        )

    def storage_info(self) -> dict[str, Any]:
        return {
            "root": f"firestore://{self.collection}/{get_demo_user()}/casefiles",
            "storage_kind": self.storage_kind,
            "casefile_count": len(self.list_casefiles()),
        }

    def _persistable_state(self, state: CasefileState) -> dict[str, Any]:
        return self._enrich_state(state).model_dump(
            mode="json",
            exclude={"requirements", "next_step"},
        )

    def _state_from_snapshot(self, data: dict[str, Any]) -> CasefileState:
        return CasefileState(**data)

    def _enrich_state(self, state: CasefileState) -> CasefileState:
        state.resolved = resolve_event_state(
            state.basics,
            state.brief,
            user_fields={
                field
                for field, value in state.basics.model_dump().items()
                if value not in ("", None)
            },
        )
        state.requirements = build_requirements_payload(state)
        state.next_step = build_next_best_step(state)
        return state

    def _owner_ref(self):
        return self._client.collection(self.collection).document(get_demo_user())

    def _casefiles_ref(self):
        return self._owner_ref().collection("casefiles")

    def _casefile_ref(self, event_id: str):
        return self._casefiles_ref().document(event_id)

    def _artifact_ref(self, event_id: str, name: str):
        return self._casefile_ref(event_id).collection("artifacts").document(name)
