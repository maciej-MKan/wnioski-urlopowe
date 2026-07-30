"""Tests of rendering HTML from Jinja templates (without WeasyPrint)."""
from __future__ import annotations

import pytest

from app.domain.errors import UnknownLeaveType
from app.domain.leave_type import REGISTRY
from app.infrastructure.templates import JinjaTemplates


@pytest.fixture
def templates() -> JinjaTemplates:
    return JinjaTemplates()


def _html(templates, payload) -> str:
    return templates.html(REGISTRY.validate(payload))


def test_annual_auto_day_count(templates):
    html = _html(templates, {"typ": "wypoczynkowy", "data_od": "2026-08-04", "data_do": "2026-08-08"})
    assert "<strong>5</strong>" in html
    assert "dni" in html
    assert "04.08.2026" in html and "08.08.2026" in html


def test_annual_single_day_inflection(templates):
    html = _html(templates, {"typ": "wypoczynkowy", "data_od": "2026-08-04", "data_do": "2026-08-04"})
    assert "<strong>1</strong>" in html
    assert "dnia" in html


def test_annual_empty_range_has_dots(templates):
    html = _html(templates, {"typ": "wypoczynkowy"})
    assert "od dnia" in html and "....." in html


def test_paternity_amount_and_child_date(templates):
    html = _html(templates, {
        "typ": "ojcowski", "wymiar": "2 tygodnie",
        "dziecko_data_urodzenia": "2026-05-10",
    })
    assert "2 tygodnie" in html
    assert "10.05.2026" in html


def test_child_care_hourly_form(templates):
    html = _html(templates, {
        "typ": "opieka", "forma": "godziny", "wymiar": "8",
        "data_od": "2026-09-10", "godzina_od": "08:00", "godzina_do": "16:00",
    })
    assert "8 godzin" in html
    assert "08:00–16:00" in html
    assert "w dniu" in html


def test_annual_settlement_year_wording(templates):
    # §16.3: the closing sentence names the settlement year.
    html = _html(templates, {"typ": "wypoczynkowy", "rok_rozliczenia": "2025",
                             "data_od": "2026-08-04", "data_do": "2026-08-08"})
    assert "za rok <strong>2025</strong>" in html


def test_annual_settlement_year_defaults_to_start_year(templates):
    html = _html(templates, {"typ": "wypoczynkowy", "data_od": "2026-08-04", "data_do": "2026-08-08"})
    assert "za rok <strong>2026</strong>" in html


def test_unknown_type_raises(templates):
    with pytest.raises(UnknownLeaveType):
        templates.html({"typ": "nieistnieje"})
