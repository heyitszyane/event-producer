"""Unit tests for the FX rate provider."""

from decimal import Decimal

import pytest

from event_producer.providers.rate_card import StaticFxRateProvider


@pytest.fixture
def provider() -> StaticFxRateProvider:
    return StaticFxRateProvider()


# --- Identity ---

def test_identity_rate(provider: StaticFxRateProvider) -> None:
    assert provider.get_rate("USD", "USD") == Decimal("1.00")


# --- Direct (USD -> X) ---

def test_direct_rate(provider: StaticFxRateProvider) -> None:
    assert provider.get_rate("USD", "SGD") == Decimal("1.34")


# --- Inverse (X -> USD) ---

def test_inverse_rate(provider: StaticFxRateProvider) -> None:
    expected = Decimal("1.00") / Decimal("1.34")
    assert provider.get_rate("SGD", "USD") == expected


# --- Cross-rate (X -> Y via USD pivot) ---

def test_cross_rate(provider: StaticFxRateProvider) -> None:
    # SGD -> THB = (1 / 1.34) * 35.50
    expected = (Decimal("1.00") / Decimal("1.34")) * Decimal("35.50")
    assert provider.get_rate("SGD", "THB") == expected


# --- Type checks ---

def test_rate_type_is_decimal(provider: StaticFxRateProvider) -> None:
    rate = provider.get_rate("USD", "EUR")
    assert type(rate) is Decimal


def test_all_rates_are_decimal(provider: StaticFxRateProvider) -> None:
    currencies = ["USD", "SGD", "THB", "EUR", "GBP", "MYR",
                  "IDR", "PHP", "VND", "JPY", "KRW", "AUD", "CNY"]
    for cur in currencies:
        rate = provider.get_rate("USD", cur)
        assert type(rate) is Decimal, f"Rate for USD->{cur} is {type(rate)}, not Decimal"


# --- Error handling ---

def test_unknown_currency_raises(provider: StaticFxRateProvider) -> None:
    with pytest.raises(ValueError):
        provider.get_rate("USD", "XYZ")

    with pytest.raises(ValueError):
        provider.get_rate("XYZ", "USD")
