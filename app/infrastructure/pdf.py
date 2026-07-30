"""Adapter of the `DocumentGenerator` port based on WeasyPrint.

This is the **only** module importing WeasyPrint. HTML is delegated to `JinjaTemplates`
(without WeasyPrint), and the PDF is produced from that HTML. Isolating the import lets
tests substituting a generator double avoid the Pango/Cairo libraries.
"""
from __future__ import annotations

from weasyprint import HTML

from ..domain.leave_type import REGISTRY, LeaveTypeRegistry
from .templates import JinjaTemplates


class WeasyPrintDocumentGenerator:
    """Implementation of the `DocumentGenerator` port (HTML → PDF)."""

    def __init__(self, registry: LeaveTypeRegistry = REGISTRY) -> None:
        self._templates = JinjaTemplates(registry)

    def html(self, data: dict) -> str:
        return self._templates.html(data)

    def pdf(self, data: dict) -> bytes:
        return HTML(string=self._templates.html(data)).write_pdf()
