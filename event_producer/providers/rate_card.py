"""FX rate provider interface and static seeded implementation.

Rates are loaded at session start from a seeded table — never fetched live.
All rate literals are ``Decimal("...")`` strings to avoid float imprecision.
"""

from abc import ABC, abstractmethod
from decimal import Decimal


class FxRateProvider(ABC):
    """Abstract base class for FX rate providers.

    Implementations must be deterministic: same inputs always produce
    the same ``Decimal`` output. No live network calls.
    """

    @abstractmethod
    def get_rate(self, base: str, quote: str) -> Decimal:
        """Return the exchange rate converting *base* to *quote*.

        Args:
            base: ISO 4217 currency code to convert from (e.g. ``"SGD"``).
            quote: ISO 4217 currency code to convert to (e.g. ``"USD"``).

        Returns:
            ``Decimal`` multiplier: 1 unit of *base* = ``rate`` units of *quote*.

        Raises:
            ValueError: If either currency is not in the seeded table.
        """
        ...


class StaticFxRateProvider(FxRateProvider):
    """Seeded FX rate provider with a static rate table.

    Rates are stored as ``Decimal`` values representing ``1 USD = N CUR``.
    Cross-rates are computed via USD pivot::

        rate(A -> B) = rate(A -> USD) * rate(USD -> B)

    Identity ``USD -> USD`` returns ``Decimal("1.00")``.
    """

    # Seeded rate table: 1 USD = N units of target currency.
    # ALL literals are Decimal("...") strings — never bare floats.
    _RATES_TO_USD: dict[str, Decimal] = {
        "USD": Decimal("1.00"),
        "SGD": Decimal("1.34"),
        "THB": Decimal("35.50"),
        "EUR": Decimal("0.92"),
        "GBP": Decimal("0.79"),
        "MYR": Decimal("4.70"),
        "IDR": Decimal("15600.00"),
        "PHP": Decimal("56.00"),
        "VND": Decimal("24500.00"),
        "JPY": Decimal("149.50"),
        "KRW": Decimal("1380.00"),
        "AUD": Decimal("1.53"),
        "CNY": Decimal("7.24"),
    }

    def get_rate(self, base: str, quote: str) -> Decimal:
        """Return the FX rate from *base* to *quote* via USD pivot."""
        base_upper = base.upper()
        quote_upper = quote.upper()

        if base_upper not in self._RATES_TO_USD:
            raise ValueError(f"Unknown base currency: {base}")
        if quote_upper not in self._RATES_TO_USD:
            raise ValueError(f"Unknown quote currency: {quote}")

        # Identity
        if base_upper == quote_upper:
            return Decimal("1.00")

        # Convert base -> USD -> quote
        # rate(base -> USD) = 1 / rate(USD -> base)
        # rate(USD -> quote) = rate_table[quote]
        base_to_usd = Decimal("1.00") / self._RATES_TO_USD[base_upper]
        usd_to_quote = self._RATES_TO_USD[quote_upper]

        return base_to_usd * usd_to_quote
