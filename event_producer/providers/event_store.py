"""Abstract interface for event data persistence (CRUD contract)."""

from abc import ABC, abstractmethod
from typing import Optional

from event_producer.models.schemas import (
    BudgetSummary,
    EventSpec,
    RunOfShow,
    ScheduleResult,
    ScopeItem,
    Vendor,
    VendorMessage,
)


class EventStore(ABC):
    """Abstract interface for event data persistence.

    Implementations must be deterministic: same inputs always produce
    the same output. No live network calls in the interface contract.
    """

    @abstractmethod
    def save_event(self, event_id: str, event_spec: EventSpec) -> None:
        """Persist an event specification."""
        ...

    @abstractmethod
    def get_event(self, event_id: str) -> Optional[EventSpec]:
        """Retrieve an event specification by ID."""
        ...

    @abstractmethod
    def save_scope(self, event_id: str, items: list[ScopeItem]) -> None:
        """Persist scope items for an event."""
        ...

    @abstractmethod
    def get_scope(self, event_id: str) -> list[ScopeItem]:
        """Retrieve scope items for an event."""
        ...

    @abstractmethod
    def save_budget(self, event_id: str, budget: BudgetSummary) -> None:
        """Persist a budget summary."""
        ...

    @abstractmethod
    def get_budget(self, event_id: str) -> Optional[BudgetSummary]:
        """Retrieve a budget summary."""
        ...

    @abstractmethod
    def save_schedule(self, event_id: str, schedule: ScheduleResult) -> None:
        """Persist a schedule result."""
        ...

    @abstractmethod
    def get_schedule(self, event_id: str) -> Optional[ScheduleResult]:
        """Retrieve a schedule result."""
        ...

    @abstractmethod
    def save_vendor(self, event_id: str, vendor: Vendor) -> None:
        """Persist a vendor record."""
        ...

    @abstractmethod
    def get_vendors(self, event_id: str) -> list[Vendor]:
        """Retrieve all vendors for an event."""
        ...

    @abstractmethod
    def save_message(self, event_id: str, message: VendorMessage) -> None:
        """Persist a vendor message."""
        ...

    @abstractmethod
    def get_messages(self, event_id: str) -> list[VendorMessage]:
        """Retrieve all vendor messages for an event."""
        ...

    @abstractmethod
    def save_run_of_show(self, event_id: str, ros: RunOfShow) -> None:
        """Persist the full run-of-show."""
        ...

    @abstractmethod
    def get_run_of_show(self, event_id: str) -> Optional[RunOfShow]:
        """Retrieve the full run-of-show."""
        ...
