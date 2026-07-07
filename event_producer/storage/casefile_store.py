"""Casefile store factory."""

from __future__ import annotations

import os
from typing import Any

from event_producer.storage.firestore_casefiles import FirestoreCasefileStore
from event_producer.storage.local_casefiles import LocalCasefileStore

CasefileStore = LocalCasefileStore | FirestoreCasefileStore


def build_casefile_store() -> CasefileStore:
    """Build the configured casefile store.

    ``local`` is the default because it keeps clone-and-run demos simple.
    ``firestore`` is intended for hosted demos where Cloud Run filesystem state
    is ephemeral.
    """
    mode = (os.environ.get("CASEFILE_STORE") or "local").strip().lower()
    if mode in {"", "local", "local_json"}:
        return LocalCasefileStore()
    if mode == "firestore":
        return FirestoreCasefileStore()
    raise ValueError(f"Unsupported CASEFILE_STORE={mode!r}")


def storage_info(store: CasefileStore) -> dict[str, Any]:
    """Return public, non-secret storage diagnostics for Settings."""
    if hasattr(store, "storage_info"):
        return store.storage_info()
    return {
        "root": str(store.root.resolve()),
        "casefile_count": len(store.list_casefiles()),
        "storage_kind": "local_json",
    }

