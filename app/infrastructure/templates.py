"""Rendering application content to HTML (Jinja2). Deliberately without WeasyPrint.

Split from `pdf.py` so the HTML can be tested on its own (and so the preview does not pull
in Pango/Cairo). Date formatting is done by Jinja filters, and the day count from a range —
by a global based on the domain `DateRange`. The title and template name come from the type
registry.

The Jinja-facing names (filter names, context keys) stay unchanged — they are the template
contract with the Polish UI templates in `app/templates/`.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..domain.leave_type import REGISTRY, LeaveTypeRegistry
from ..domain.values import DateRange
from .formatting import date_in_words, date_short, days_word

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def _calendar_days(start: str, end: str) -> int | None:
    return DateRange.from_strings(start, end).calendar_days()


class JinjaTemplates:
    """Builds application HTML from Jinja2 templates based on normalized data."""

    def __init__(self, registry: LeaveTypeRegistry = REGISTRY) -> None:
        self._registry = registry
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES)),
            autoescape=select_autoescape(["html"]),
        )
        self._env.filters["krotko"] = date_short
        self._env.filters["slownie"] = date_in_words
        self._env.filters["dni_slowo"] = days_word
        self._env.globals["dni_kalendarzowe"] = _calendar_days

    def html(self, data: dict) -> str:
        leave_type = self._registry.required(data.get("typ"))
        employer = (data.get("pracodawca") or "").strip()
        context = {
            "d": data,
            "lt": leave_type,
            "tytul": leave_type.document_title,
            "data_dok": date_in_words(data.get("data", "")),
            "pracodawca_linie": [line for line in employer.splitlines() if line.strip()],
        }
        return self._env.get_template(leave_type.template).render(**context)
