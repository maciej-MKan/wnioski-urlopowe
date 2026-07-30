"""Serialization of domain objects to JSON for the frontend and API.

Presentation of the type registry and records — deliberately outside the domain, because
the JSON shape is an interface detail that may change independently of the domain model.
JSON keys stay Polish (the wire contract shared with the frontend); the Python attributes
they read from are English. This serializer is the bridge between the two.
"""
from __future__ import annotations

from ..domain.balance import BalanceItem
from ..domain.entitlement import Entitlement
from ..domain.leave_record import LeaveRecord
from ..domain.leave_type import FormField, LeaveTypeRegistry


def _field_to_json(f: FormField) -> dict:
    return {
        "name": f.name,
        "label": f.label,
        "typ_pola": f.field_type,
        "placeholder": f.placeholder,
        "hint": f.hint,
        "szerokosc": f.width,
        "domyslna": f.default,
        "auto_z_zakresu": f.auto_from_range,
        "opcje": [{"value": v, "label": e} for v, e in f.options],
        "widoczne_gdy": (
            {"pole": f.visible_when[0], "wartosc": f.visible_when[1]} if f.visible_when else None
        ),
    }


def registry_to_json(registry: LeaveTypeRegistry, active: set[str] | None = None) -> dict:
    """The type registry in the shape the frontend expects (tabs + fields).

    `active` — the set of type ids due in the given year (from Settings). When `None` (a call
    without a year), all types are marked active — backward-compatible. The frontend filters
    tabs/select by the `aktywny` flag.
    """
    return {
        "wspolne": [_field_to_json(f) for f in registry.common],
        "typy": [
            {
                "id": t.id,
                "nazwa": t.name,
                "zakladka_opis": t.tab_note,
                "podstawa_prawna": t.legal_basis,
                "uwaga": t.note,
                "kolor": t.color,
                "jednostka": t.unit.value,
                "ma_zalegly": t.has_overdue,
                "limit_domyslny": t.default_limit_text,
                "aktywny": active is None or t.id in active,
                "generowalny": t.generatable,
                "pola": [_field_to_json(f) for f in t.fields],
            }
            for t in registry.all()
        ],
    }


def entitlement_to_json(e: Entitlement) -> dict:
    return {
        "typ": e.leave_type,
        "aktywny": e.active,
        "limit_dni": e.limit_days,
        "limit_godzin": e.limit_hours,
        "bilans_z_przeniesienia": e.carried_over,
        "uwagi": e.notes,
    }


def balance_item_to_json(item: BalanceItem) -> dict:
    return {
        "typ": item.leave_type,
        "etykieta": item.label,
        "jednostka": item.unit,
        "limit": item.limit,
        "wykorzystano": item.used,
        "zaplanowano": item.planned,
        "pozostalo": item.remaining,
        "krotki_termin": item.short_term,
        "miesiac": item.month,
    }


def record_to_json(record: LeaveRecord) -> dict:
    """A leave record in list/API form."""
    return {
        "id": record.id,
        "typ": record.leave_type,
        "rok": record.year,
        "status": record.status.value,
        "zrodlo": record.source.value,
        "za_okres": record.pool.value,
        "data_od": record.period.start_iso,
        "data_do": record.period.end_iso,
        "dni_robocze": record.working_days,
        "godziny": record.hours,
        "ma_zalacznik": record.attachment_mime is not None,
        "zalacznik_mime": record.attachment_mime,
        "zalacznik_nazwa": record.attachment_name,
        "korekta_powod": record.correction_reason,
        "utworzono": record.created_at,
        "zmieniono": record.updated_at,
        "dane": record.data,
    }
