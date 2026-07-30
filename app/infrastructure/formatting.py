"""Formatting dates and text into the form used in Polish documents.

Presentation (not domain): inflected wording of dates and numbers for the templates. Date
parsing belongs to the domain (`domain.values.parse_date`) and is reused from there.
"""
from __future__ import annotations

from ..domain.values import parse_date

_MONTHS = [
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
]


def date_in_words(d: str) -> str:
    """'2026-07-24' → '24 lipca 2026 r.'; unrecognized input is returned unchanged."""
    parsed = parse_date(d)
    if not parsed:
        return d or ""
    return f"{parsed.day} {_MONTHS[parsed.month - 1]} {parsed.year} r."


def date_short(d: str) -> str:
    """'2026-07-24' → '24.07.2026'; unrecognized input is returned unchanged."""
    parsed = parse_date(d)
    if not parsed:
        return d or ""
    return parsed.strftime("%d.%m.%Y")


def days_word(n: str) -> str:
    """Inflection of the Polish word 'dzień' by number (1 → 'dnia', otherwise → 'dni')."""
    try:
        number = int(str(n).strip())
    except (ValueError, TypeError):
        return "dni"
    return "dnia" if number == 1 else "dni"
