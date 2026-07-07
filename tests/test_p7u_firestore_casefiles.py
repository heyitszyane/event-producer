"""P7U — Firestore casefile store for hosted demos."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from event_producer.models.schemas import EventBasics
from event_producer.storage.casefile_context import reset_demo_user, set_demo_user
from event_producer.storage.casefile_store import build_casefile_store
from event_producer.storage.firestore_casefiles import FirestoreCasefileStore


class FakeSnapshot:
    def __init__(self, data: dict[str, Any] | None, reference: "FakeDocument") -> None:
        self._data = data
        self.reference = reference
        self.exists = data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return dict(self._data) if self._data is not None else None


class FakeDocument:
    def __init__(self, collection: "FakeCollection", doc_id: str) -> None:
        self._collection = collection
        self.id = doc_id

    def set(self, data: dict[str, Any]) -> None:
        self._collection._documents[self.id] = dict(data)

    def get(self) -> FakeSnapshot:
        data = self._collection._documents.get(self.id)
        return FakeSnapshot(dict(data) if data is not None else None, self)

    def delete(self) -> None:
        self._collection._documents.pop(self.id, None)
        prefix = self._collection._path + (self.id,)
        for key in list(self._collection._client._collections):
            if key[: len(prefix)] == prefix:
                self._collection._client._collections.pop(key, None)

    def collection(self, name: str) -> "FakeCollection":
        return self._collection._client.collection_for(self._collection._path + (self.id, name))


class FakeCollection:
    def __init__(self, client: "FakeFirestoreClient", path: tuple[str, ...]) -> None:
        self._client = client
        self._path = path
        self._documents: dict[str, dict[str, Any]] = {}
        self._auto_id = 0

    def document(self, doc_id: str | None = None) -> FakeDocument:
        if doc_id is None:
            self._auto_id += 1
            doc_id = f"auto-{self._auto_id}"
        return FakeDocument(self, doc_id)

    def stream(self) -> list[FakeSnapshot]:
        return [
            FakeSnapshot(dict(data), FakeDocument(self, doc_id))
            for doc_id, data in self._documents.items()
        ]


class FakeFirestoreClient:
    def __init__(self) -> None:
        self._collections: dict[tuple[str, ...], FakeCollection] = {}

    def collection(self, name: str) -> FakeCollection:
        return self.collection_for((name,))

    def collection_for(self, path: tuple[str, ...]) -> FakeCollection:
        if path not in self._collections:
            self._collections[path] = FakeCollection(self, path)
        return self._collections[path]


def _basics(title: str = "Hosted Demo") -> EventBasics:
    return EventBasics(
        working_title=title,
        country="Singapore",
        city="Singapore",
        currency="SGD",
        budget_cap=Decimal("10000"),
        contingency_pct=Decimal("10"),
        start_date="2026-08-14",
        end_date="2026-08-14",
        expected_turnout=100,
        event_type="networking",
    )


def test_firestore_store_persists_casefile_artifact_and_operator_state() -> None:
    store = FirestoreCasefileStore(client=FakeFirestoreClient())
    token = set_demo_user("browser-a")
    try:
        casefile = store.create_casefile(_basics(), "Brief says 50 people.")
        artifact = store.write_artifact(casefile.event_id, "run-snapshot", {"ok": True})
        assert artifact.path == "artifacts/run-snapshot"
        assert store.read_artifact(casefile.event_id, "run-snapshot") == {"ok": True}

        updated = store.update_run_sheet_task_status(
            casefile.event_id,
            "setup",
            status="Complete",
            notes="Done",
        )
        override = updated.planning_assumptions["run_sheet_task_overrides"]["setup"]
        assert override["status"] == "Complete"
        assert override["notes"] == "Done"
    finally:
        reset_demo_user(token)


def test_firestore_store_sanitizes_decimal_artifact_payload() -> None:
    # Regression: the Budget Engine emits Decimal values, which the Firestore
    # client cannot encode. write_artifact must coerce them to Firestore-safe
    # types (matching the local JSON store, which serialises money as strings)
    # instead of raising and turning /run into an unhandled 500.
    store = FirestoreCasefileStore(client=FakeFirestoreClient())
    token = set_demo_user("browser-decimal")
    try:
        casefile = store.create_casefile(_basics(), "Brief says 50 people.")
        payload = {
            "total": Decimal("10000"),
            "lines": [{"label": "venue", "amount": Decimal("2500.50")}],
        }
        store.write_artifact(casefile.event_id, "budget-summary", payload)
        stored = store.read_artifact(casefile.event_id, "budget-summary")
        assert stored == {
            "total": "10000",
            "lines": [{"label": "venue", "amount": "2500.50"}],
        }

        def _no_decimal(value: Any) -> None:
            assert not isinstance(value, Decimal)
            if isinstance(value, dict):
                for item in value.values():
                    _no_decimal(item)
            elif isinstance(value, list):
                for item in value:
                    _no_decimal(item)

        _no_decimal(stored)
    finally:
        reset_demo_user(token)


def test_firestore_store_scopes_casefiles_by_demo_user() -> None:
    store = FirestoreCasefileStore(client=FakeFirestoreClient())

    token_a = set_demo_user("browser-a")
    try:
        store.create_casefile(_basics("A"), "", event_id="shared-id")
        assert [item.working_title for item in store.list_casefiles()] == ["A"]
    finally:
        reset_demo_user(token_a)

    token_b = set_demo_user("browser-b")
    try:
        assert store.list_casefiles() == []
        store.create_casefile(_basics("B"), "", event_id="shared-id")
        assert [item.working_title for item in store.list_casefiles()] == ["B"]
    finally:
        reset_demo_user(token_b)

    token_a2 = set_demo_user("browser-a")
    try:
        assert [item.working_title for item in store.list_casefiles()] == ["A"]
    finally:
        reset_demo_user(token_a2)


def test_casefile_store_factory_selects_firestore(
    monkeypatch,
) -> None:
    fake_client = FakeFirestoreClient()
    monkeypatch.setenv("CASEFILE_STORE", "firestore")
    monkeypatch.setattr(
        "event_producer.storage.firestore_casefiles.FirestoreCasefileStore.__init__",
        lambda self: (
            setattr(self, "collection", "event_producer_demo_users"),
            setattr(self, "_client", fake_client),
            setattr(self, "storage_kind", "firestore"),
            None,
        )[-1],
    )

    store = build_casefile_store()
    assert isinstance(store, FirestoreCasefileStore)

