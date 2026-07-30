"""Smoke test of the real WeasyPrint generator.

Skipped when WeasyPrint (really its system libraries) is unavailable — the full run happens
in the Docker image. The rest of the tests work without this dependency.
"""
from __future__ import annotations

import pytest

pytest.importorskip("weasyprint")

from app.domain.leave_type import REGISTRY  # noqa: E402
from app.infrastructure.pdf import WeasyPrintDocumentGenerator  # noqa: E402


def test_generates_valid_pdf():
    generator = WeasyPrintDocumentGenerator()
    data = REGISTRY.validate({"typ": "wypoczynkowy", "data_od": "2026-08-04", "data_do": "2026-08-08"})
    pdf = generator.pdf(data)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_html_contains_title():
    generator = WeasyPrintDocumentGenerator()
    html = generator.html(REGISTRY.validate({"typ": "ojcowski"}))
    assert "URLOPU OJCOWSKIEGO".lower() in html.lower()
