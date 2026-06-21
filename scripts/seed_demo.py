"""Seed demo data: creates a 1-night networking event via the REST API.

Usage:
    python scripts/seed_demo.py

Requires the API server to be running on http://localhost:8080.
"""

from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error

API_BASE = "http://localhost:8080"

RUN_ENDPOINT = f"{API_BASE}/run"

PAYLOAD = {
    "brief": "1-night networking event for tech professionals",
    "budget_cap": "50000",
    "contingency_pct": "15",
    "attendees": 200,
    "event_type": "networking",
    "venue_type": "indoor",
    "date": "2026-08-15",
}

HEADERS = {
    "Content-Type": "application/json",
    "X-Demo-User": "demo",
}


def seed_demo_event() -> dict:
    """POST to /run and return the parsed JSON response."""
    data = json.dumps(PAYLOAD).encode("utf-8")
    req = urllib.request.Request(
        RUN_ENDPOINT,
        data=data,
        headers=HEADERS,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP error {exc.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError:
        print(f"Cannot connect to the API server at {API_BASE}.", file=sys.stderr)
        print("Please start the server first:", file=sys.stderr)
        print("    python -m event_producer.main", file=sys.stderr)
        print("Or: uvicorn event_producer.api:create_app --factory --port 8080", file=sys.stderr)
        sys.exit(1)


def print_summary(result: dict) -> None:
    """Print a human-readable summary of the pipeline result."""
    event_id = result.get("event_id", "N/A")
    print(f"event_id: {event_id}")

    # Top-level summary fields
    for key in ("status", "brief", "date", "attendees", "event_type", "venue_type"):
        if key in result:
            print(f"  {key}: {result[key]}")

    # Budget reconciliation
    budget = result.get("budget", result.get("budget_summary", {}))
    if budget:
        print("budget reconciliation:")
        for field in ("total", "contingency", "headroom", "contingency_pct", "budget_cap"):
            if field in budget:
                print(f"  {field}: {budget[field]}")
    else:
        # Fallback: look for budget fields at the top level
        budget_keys = ("total", "contingency", "headroom", "contingency_pct", "budget_cap")
        found = {k: result[k] for k in budget_keys if k in result}
        if found:
            print("budget reconciliation:")
            for k, v in found.items():
                print(f"  {k}: {v}")

    # Run-of-Show / schedule summary
    schedule = result.get("schedule", result.get("run_of_show", []))
    if schedule:
        print(f"schedule: {len(schedule)} task(s)")
        for task in schedule[:5]:
            name = task.get("name", task.get("task", "?"))
            status = task.get("status", "")
            print(f"  - {name} [{status}]")
        if len(schedule) > 5:
            print(f"  ... and {len(schedule) - 5} more")

    # Vendor / approval summary
    approvals = result.get("approvals", result.get("pending_approvals", []))
    if approvals:
        print(f"pending approvals: {len(approvals)}")


def main() -> None:
    print("Seeding demo event via POST /run ...")
    result = seed_demo_event()
    print()
    print_summary(result)


if __name__ == "__main__":
    main()
