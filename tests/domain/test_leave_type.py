"""Tests of the type registry and payload validation."""
from __future__ import annotations

import pytest

from app.domain.errors import UnknownLeaveType
from app.domain.leave_type import REGISTRY


def test_registry_types():
    assert {t.id for t in REGISTRY.all()} == {"wypoczynkowy", "ojcowski", "opieka", "wolne_za_swieta"}


def test_weekend_off_type_is_not_generatable():
    assert REGISTRY.required("wolne_za_swieta").generatable is False
    assert REGISTRY.required("wypoczynkowy").generatable is True


def test_get_unknown_returns_none():
    assert REGISTRY.get("nieistnieje") is None


def test_required_unknown_raises():
    with pytest.raises(UnknownLeaveType):
        REGISTRY.required("nieistnieje")


def test_validate_rejects_unknown_type():
    with pytest.raises(UnknownLeaveType):
        REGISTRY.validate({"typ": "nieistnieje"})


def test_validate_whitelists_fields():
    data = REGISTRY.validate({"typ": "wypoczynkowy", "data_od": "2026-08-04", "haker": "x"})
    assert "haker" not in data
    assert data["data_od"] == "2026-08-04"


def test_validate_fills_defaults():
    data = REGISTRY.validate({"typ": "wypoczynkowy"})
    # All common and specific fields present, empty as a string.
    assert data["miejscowosc"] == ""
    assert data["liczba_dni"] == ""


def test_validate_corrects_select_outside_options():
    data = REGISTRY.validate({"typ": "opieka", "forma": "kosmos"})
    assert data["forma"] == "dni"  # default value


def test_validate_trims_whitespace():
    data = REGISTRY.validate({"typ": "wypoczynkowy", "imie_nazwisko": "  Jan Kowalski  "})
    assert data["imie_nazwisko"] == "Jan Kowalski"


def test_validate_require_fields_raises_on_missing():
    with pytest.raises(ValueError) as exc:
        REGISTRY.validate({"typ": "wypoczynkowy", "data_od": "2026-08-04", "data_do": "2026-08-08"},
                          require_fields=True)
    msg = str(exc.value)
    assert "Miejscowość" in msg and "Pracodawca" in msg


def test_validate_require_fields_ok_when_complete():
    data = REGISTRY.validate(
        {"typ": "wypoczynkowy", "data_od": "2026-08-04", "data_do": "2026-08-08",
         "miejscowosc": "Warszawa", "pracodawca": "ACME"},
        require_fields=True)
    assert data["miejscowosc"] == "Warszawa"


def test_validate_without_require_fields_allows_empty():
    # Domyślnie (np. ręczne dodawanie) puste pola wymagane są dozwolone.
    data = REGISTRY.validate({"typ": "wypoczynkowy", "data_od": "2026-08-04", "data_do": "2026-08-08"})
    assert data["miejscowosc"] == ""
