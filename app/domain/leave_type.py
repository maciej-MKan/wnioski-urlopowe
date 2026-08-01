"""Registry of leave types — descriptors driving validation, the document and the frontend.

This is the single source of truth about leave types (the extensibility foundation from
plan §4). Adding a new type = adding a `LeaveType` descriptor (+ optionally an HTML
template). The registry belongs to the domain because it encodes the ubiquitous language;
its serialization for the frontend is already a concern of the interface layer
(`interface/serializers.py`).

Note the deliberate language split: identifiers are English, but user-facing strings
(labels, hints, legal notes) and wire values (type ids, field names/`name`) stay Polish.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .errors import UnknownLeaveType
from .values import Unit


@dataclass(frozen=True)
class FormField:
    """Descriptor of a single form field (feeds the frontend and validation)."""

    name: str  # payload/JSON key (wire) — stays Polish, e.g. "miejscowosc"
    label: str
    field_type: str = "text"  # text | date | time | select | textarea | number
    placeholder: str = ""
    hint: str = ""
    width: str = "half"  # half | full
    options: tuple[tuple[str, str], ...] = ()  # for select: ((value, label), ...)
    default: str = ""
    visible_when: Optional[tuple[str, str]] = None  # (field_name, value)
    auto_from_range: bool = False  # hint the day count from the data_od–data_do range
    required: bool = False  # obowiązkowe przy generowaniu wniosku (validate(require_fields=True))


@dataclass(frozen=True)
class LeaveType:
    """Descriptor of a leave type."""

    id: str
    name: str  # tab label
    tab_note: str  # small note under the name
    document_title: str  # title printed on the document
    legal_basis: str
    template: str  # Jinja2 template file name
    fields: tuple[FormField, ...]
    unit: Unit
    color: str  # calendar color (Phase 3)
    counts_toward_limit: bool = True
    has_overdue: bool = False  # whether the pool splits into current and overdue ("za okres")
    default_limit_text: Optional[str] = None  # wording (on PDF / hint)
    default_limit_days: Optional[float] = None  # numeric day amount for the balance
    default_limit_hours: Optional[float] = None  # numeric hour amount for the balance
    note: str = ""  # legal note under the form
    generatable: bool = True  # shown as a generator tab / manual-add option (§15)


# --- Fields common to every application -----------------------------------------------

COMMON_FIELDS: tuple[FormField, ...] = (
    FormField("miejscowosc", "Miejscowość", placeholder="np. Warszawa", required=True),
    FormField("data", "Data sporządzenia", field_type="date"),
    FormField("imie_nazwisko", "Imię i nazwisko pracownika", placeholder="Jan Kowalski", width="full"),
    FormField("stanowisko", "Stanowisko / dział (opcjonalnie)", placeholder="Specjalista, Dział IT", width="full"),
    FormField(
        "pracodawca",
        "Pracodawca / adresat (każda linia osobno)",
        field_type="textarea",
        placeholder="Nazwa firmy Sp. z o.o.\nul. Przykładowa 1\n00-001 Warszawa",
        width="full",
        required=True,
    ),
    FormField(
        "dzial_kadr",
        "Kierowane do (opcjonalnie)",
        placeholder="np. Dział Kadr / Bezpośredni przełożony",
        width="full",
    ),
)


def _default_types() -> tuple[LeaveType, ...]:
    return (
        LeaveType(
            id="wypoczynkowy",
            name="Urlop wypoczynkowy",
            tab_note="art. 152 i 163 K.p.",
            document_title="Wniosek o udzielenie urlopu wypoczynkowego",
            legal_basis="art. 152 i 163 K.p.",
            template="wypoczynkowy.html",
            unit=Unit.WORKING_DAYS,
            color="#2f8f5b",
            has_overdue=True,
            default_limit_text="20 lub 26 dni",
            default_limit_days=26,
            fields=(
                FormField("data_od", "Data od", field_type="date", required=True),
                FormField("data_do", "Data do", field_type="date", required=True),
                FormField("liczba_dni", "Liczba dni", placeholder="auto z zakresu dat", auto_from_range=True),
                FormField(
                    "rok_rozliczenia",
                    "Rok rozliczenia",
                    field_type="number",
                    placeholder="np. 2026",
                    hint="Rok, z którego puli rozliczyć urlop (pusto = rok rozpoczęcia). "
                         "Rok wcześniejszy = urlop zaległy. Trafia na PDF i do bilansu.",
                ),
            ),
        ),
        LeaveType(
            id="ojcowski",
            name="Urlop ojcowski",
            tab_note="art. 182³ K.p.",
            document_title="Wniosek o udzielenie urlopu ojcowskiego",
            legal_basis="art. 182³ K.p.",
            template="ojcowski.html",
            unit=Unit.CALENDAR_DAYS,
            color="#3a6ea5",
            default_limit_text="2 tygodnie",
            default_limit_days=14,
            note=(
                "Prawo do urlopu ojcowskiego przysługuje do ukończenia przez dziecko "
                "12 miesiąca życia. Wniosek składa się co najmniej 7 dni przed rozpoczęciem "
                "urlopu. Do wniosku dołącza się skrócony odpis aktu urodzenia dziecka."
            ),
            fields=(
                FormField("dziecko_imie_nazwisko", "Imię i nazwisko dziecka", placeholder="Anna Kowalska", width="full"),
                FormField("dziecko_data_urodzenia", "Data urodzenia dziecka", field_type="date"),
                FormField(
                    "wymiar",
                    "Wymiar",
                    placeholder="np. 2 tygodnie",
                    hint="Do 2 tygodni, można w 2 częściach (min. 1 tydzień każda).",
                ),
                FormField("data_od", "Data od", field_type="date", required=True),
                FormField("data_do", "Data do", field_type="date", required=True),
            ),
        ),
        LeaveType(
            id="opieka",
            name="Opieka nad dzieckiem",
            tab_note="art. 188 K.p. · do 14 lat",
            document_title="Wniosek o udzielenie zwolnienia od pracy na opiekę nad dzieckiem",
            legal_basis="art. 188 K.p.",
            template="opieka.html",
            unit=Unit.HOURS,
            color="#b06a2c",
            default_limit_text="2 dni albo 16 godzin",
            default_limit_days=2,
            default_limit_hours=16,
            fields=(
                FormField("dziecko_imie_nazwisko", "Imię i nazwisko dziecka", placeholder="Anna Kowalska", width="full"),
                FormField("dziecko_data_urodzenia", "Data urodzenia dziecka", field_type="date"),
                FormField(
                    "forma",
                    "Forma wykorzystania",
                    field_type="select",
                    options=(("dni", "Dni"), ("godziny", "Godziny")),
                    default="dni",
                ),
                FormField("wymiar", "Wymiar (liczba dni lub godzin)", placeholder="np. 2", hint="Rocznie: 2 dni albo 16 godzin."),
                FormField("data_od", "Data od", field_type="date", required=True),
                FormField("data_do", "Data do", field_type="date", required=True),
                FormField("godzina_od", "Godzina od", field_type="time", visible_when=("forma", "godziny")),
                FormField("godzina_do", "Godzina do", field_type="time", visible_when=("forma", "godziny")),
            ),
        ),
        # §15: day off owed for a Saturday holiday (art. 130 § 2 K.p.). Not a generator tab —
        # created via the split flow when submitting annual leave. Shown on the calendar/balance.
        LeaveType(
            id="wolne_za_swieta",
            name="Dzień wolny za święto",
            tab_note="art. 130 § 2 K.p. · święto w sobotę",
            document_title="Wniosek o udzielenie dnia wolnego za święto przypadające w sobotę",
            legal_basis="art. 130 § 2 K.p.",
            template="wolne_za_swieta.html",
            unit=Unit.WORKING_DAYS,
            color="#7a4fbf",
            generatable=False,
            fields=(
                FormField("data_od", "Data od", field_type="date", required=True),
                FormField("data_do", "Data do", field_type="date", required=True),
            ),
        ),
    )


@dataclass(frozen=True)
class LeaveTypeRegistry:
    """Collection of descriptors with read operations and payload validation."""

    types: tuple[LeaveType, ...] = field(default_factory=_default_types)
    common: tuple[FormField, ...] = COMMON_FIELDS

    @property
    def _index(self) -> dict[str, LeaveType]:
        return {t.id: t for t in self.types}

    def all(self) -> tuple[LeaveType, ...]:
        return self.types

    def get(self, type_id: str) -> Optional[LeaveType]:
        return self._index.get(type_id)

    def required(self, type_id: object) -> LeaveType:
        """The type descriptor or `UnknownLeaveType`."""
        leave_type = self.get(type_id) if isinstance(type_id, str) else None
        if leave_type is None:
            raise UnknownLeaveType(type_id)
        return leave_type

    def validate(self, payload: dict, require_fields: bool = False) -> dict:
        """Normalized application data driven by the descriptor.

        - rejects an unknown `typ` (`UnknownLeaveType`),
        - copies only fields from the descriptor (whitelist),
        - missing fields → default value (usually an empty string),
        - a `select` value outside the options → the default value.
        - `require_fields=True` (generowanie wniosku) → puste pole oznaczone `required`
          kończy się `ValueError` z listą brakujących etykiet (parytet z walidacją w web).
        """
        leave_type = self.required(payload.get("typ"))
        data: dict = {"typ": leave_type.id}
        missing: list[str] = []
        for f in self.common + leave_type.fields:
            value = payload.get(f.name, f.default)
            value = "" if value is None else str(value).strip()
            if f.field_type == "select" and f.options:
                if value not in {v for v, _ in f.options}:
                    value = f.default
            data[f.name] = value
            if require_fields and f.required and not value:
                missing.append(f.label)
        if missing:
            raise ValueError("Uzupełnij wymagane pola: " + ", ".join(missing) + ".")
        return data


#: Default registry of the three supported leave types.
REGISTRY = LeaveTypeRegistry()
