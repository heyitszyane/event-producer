"""Minimal MCP wrapper over the EventStore.

Provides a thin ``McpServer`` class that delegates to an ``EventStore``
instance, plus a ``create_app`` factory function. An optional
``McpHttpHandler`` exposes the same operations over HTTP using Python's
built-in ``http.server`` module (no external dependencies).
"""

from __future__ import annotations

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from event_producer.providers.event_store import EventStore


# ---------------------------------------------------------------------------
# Core MCP server
# ---------------------------------------------------------------------------


class McpServer:
    """Thin wrapper that exposes EventStore operations through a uniform
    MCP-style interface plus a simple HTTP handler.

    Args:
        event_store: Any ``EventStore`` implementation (abstract
            interface — concrete provider is injected).
    """

    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    # -- MCP-style CRUD methods -------------------------------------------

    def get_event(self, event_id: str) -> Optional[dict]:
        """Retrieve an event specification as a plain dict, or ``None``."""
        spec = self._event_store.get_event(event_id)
        return spec.model_dump() if spec is not None else None

    def save_event(self, event_id: str, data: dict) -> bool:
        """Persist an event specification. Returns ``True`` on success."""
        from event_producer.models.schemas import EventSpec

        self._event_store.save_event(event_id, EventSpec(**data))
        return True

    def list_events(self) -> list[str]:
        """Return all event IDs currently in the store."""
        return self._event_store.list_events()

    def delete_event(self, event_id: str) -> bool:
        """Remove an event from the store. Returns ``True`` if it existed."""
        return self._event_store.delete_event(event_id)

    def health(self) -> dict:
        """Health-check payload."""
        return {"status": "ok"}

    # -- HTTP handler factory ---------------------------------------------

    def make_handler(self):
        """Return a ``BaseHTTPRequestHandler`` subclass bound to this
        server instance, suitable for passing to ``HTTPServer``.

        Usage::

            server = create_app(event_store)
            handler = server.make_handler()
            HTTPServer(("127.0.0.1", 8000), handler).serve_forever()
        """
        _event_store = self._event_store

        class _JsonMixin:
            """Small mixin so every handler method can serialize with one call."""

            @staticmethod
            def _json(handler_self, payload: object, status: int = 200) -> None:
                body = json.dumps(payload).encode()
                handler_self.send_response(status)
                handler_self.send_header("Content-Type", "application/json")
                handler_self.send_header("Content-Length", str(len(body)))
                handler_self.end_headers()
                handler_self.wfile.write(body)

            @staticmethod
            def _read_body(handler_self: BaseHTTPRequestHandler) -> dict:  # type: ignore[override]
                raw = handler_self.rfile.read(
                    int(handler_self.headers.get("Content-Length", 0))
                )
                return json.loads(raw) if raw else {}

        class McpHttpHandler(_JsonMixin, BaseHTTPRequestHandler):  # type: ignore[misc]
            """Simple JSON HTTP interface over the EventStore."""

            # Suppress default stderr logging noise.
            def log_message(self, fmt: str, *args: object) -> None:
                ...

            # -- helpers --------------------------------------------------------

            @staticmethod
            def _path_parts(path: str) -> list[str]:
                return [p for p in path.strip("/").split("/") if p]

            # -- GET /health ----------------------------------------------------

            def do_GET(self) -> None:  # noqa: N802
                parts = self._path_parts(self.path)

                if not parts or parts == ["health"]:
                    self._json(self, self.health_response())
                    return

                if parts[0] == "events" and len(parts) == 1:
                    # Return scope index keys as best-effort IDs
                    spec = list_response(_event_store)
                    self._json(self, spec)
                    return

                if parts[0] == "events" and len(parts) == 2:
                    event_id = parts[1]
                    spec = _event_store.get_event(event_id)
                    if spec is None:
                        self._json(self, {"error": "not found"}, 404)
                    else:
                        self._json(self, spec.model_dump())
                    return

                self._json(self, {"error": "not found"}, 404)

            # -- POST /events/<id> ----------------------------------------------

            def do_POST(self) -> None:  # noqa: N802
                parts = self._path_parts(self.path)

                if len(parts) == 2 and parts[0] == "events":
                    event_id = parts[1]
                    from event_producer.models.schemas import EventSpec

                    data = self._read_body()  # type: ignore[call-arg]
                    _event_store.save_event(event_id, EventSpec(**data))
                    self._json(self, {"saved": True})
                    return

                self._json(self, {"error": "bad request"}, 400)

            # -- DELETE /events/<id> --------------------------------------------

            def do_DELETE(self) -> None:  # noqa: N802
                parts = self._path_parts(self.path)

                if len(parts) == 2 and parts[0] == "events":
                    event_id = parts[1]
                    deleted = _event_store.delete_event(event_id)
                    if deleted:
                        self._json(self, {"deleted": True})
                    else:
                        self._json(self, {"error": "not found"}, 404)
                    return

                self._json(self, {"error": "not found"}, 404)

            # -- Static responses -----------------------------------------------

            @staticmethod
            def health_response() -> dict:
                return {"status": "ok"}

        return McpHttpHandler


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_app(event_store: EventStore) -> McpServer:
    """Factory that builds an ``McpServer`` wired to *event_store*.

    This is the single recommended entry point for tests and for
    production composition roots alike.
    """
    return McpServer(event_store=event_store)


# ---------------------------------------------------------------------------
# Convenience: dict-based helper
# ---------------------------------------------------------------------------


def list_response(store: EventStore) -> list[str]:
    """Return all event IDs via the provider seam."""
    return store.list_events()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from event_producer.main import InMemoryEventStore

    store = InMemoryEventStore()
    app = create_app(store)
    handler = app.make_handler()

    port = 8200
    print(f"MCP server listening on http://127.0.0.1:{port}")
    print("Routes: GET /health, GET /events, GET /events/<id>, "
          "POST /events/<id>, DELETE /events/<id>")
    HTTPServer(("127.0.0.1", port), handler).serve_forever()
