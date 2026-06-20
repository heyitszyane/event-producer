"""Abstract interface for vendor discovery and qualification."""

from abc import ABC, abstractmethod

from event_producer.models.schemas import Vendor


class VendorSourcer(ABC):
    """Abstract interface for vendor discovery and qualification.

    Implementations must be deterministic. No live network calls.
    """

    @abstractmethod
    def search(self, category: str, location: str = "") -> list[Vendor]:
        """Search for vendors by category and optional location."""
        ...

    @abstractmethod
    def get_by_id(self, vendor_id: str) -> Vendor | None:
        """Retrieve a vendor by ID."""
        ...

    @abstractmethod
    def qualify(self, vendor: Vendor, requirements: dict) -> bool:
        """Check if a vendor meets the given requirements."""
        ...
