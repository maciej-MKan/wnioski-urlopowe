"""Public holidays in Poland — fixed and movable feasts.

Pure domain (no dependencies). Movable feasts are computed from Easter, determined by the
paschal algorithm (anonymous Gregorian method / Meeus–Jones–Butcher).

Legal note: since 2025, **December 24 (Christmas Eve)** is also a statutory day off —
we account for it for years >= 2025. Holiday names stay Polish (user-facing content).
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache


def easter(year: int) -> date:
    """Easter Sunday of the given year (Gregorian calendar)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    month = (h + ll - 7 * m + 114) // 31
    day = ((h + ll - 7 * m + 114) % 31) + 1
    return date(year, month, day)


# Fixed holidays: (month, day, name).
_FIXED: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Nowy Rok"),
    (1, 6, "Święto Trzech Króli"),
    (5, 1, "Święto Pracy"),
    (5, 3, "Święto Konstytucji 3 Maja"),
    (8, 15, "Wniebowzięcie NMP / Święto Wojska Polskiego"),
    (11, 1, "Wszystkich Świętych"),
    (11, 11, "Narodowe Święto Niepodległości"),
    (12, 25, "Boże Narodzenie (1. dzień)"),
    (12, 26, "Boże Narodzenie (2. dzień)"),
)


def polish_holidays_named(year: int) -> dict[date, str]:
    """Map day → name of statutory days off (excluding ordinary Sundays)."""
    e = easter(year)
    holidays: dict[date, str] = {date(year, m, d): name for m, d, name in _FIXED}
    holidays[e] = "Wielkanoc"
    holidays[e + timedelta(days=1)] = "Poniedziałek Wielkanocny"
    holidays[e + timedelta(days=49)] = "Zielone Świątki"
    holidays[e + timedelta(days=60)] = "Boże Ciało"
    if year >= 2025:
        holidays[date(year, 12, 24)] = "Wigilia Bożego Narodzenia"  # day off since 2025
    return holidays


@lru_cache(maxsize=256)
def polish_holidays(year: int) -> frozenset[date]:
    """Set of statutory days off in the given year (excluding ordinary Sundays)."""
    return frozenset(polish_holidays_named(year))


def saturday_holidays(year: int) -> list[date]:
    """Statutory holidays falling on a Saturday, ascending (§14).

    For a single-shift Mon–Fri worker a holiday on Saturday coincides with the day already
    free from the average 5-day week, so the employer owes an extra day off (art. 130 § 2
    K.p.). A holiday on Sunday grants nothing (the article excludes Sundays).
    """
    return sorted(d for d in polish_holidays(year) if d.weekday() == 5)
