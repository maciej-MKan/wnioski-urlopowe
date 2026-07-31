"""Application service — the use cases of the leave application generator."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

from ..domain.balance import WEEKEND_OFF_ID, BalanceItem, compute_balance, weekend_holiday_items
from ..domain.entitlement import Entitlement
from ..domain.errors import RecordNotFound
from ..domain.holidays import polish_holidays_named, saturday_holidays
from ..domain.leave_amount import compute_amount
from ..domain.leave_record import LeaveRecord
from ..domain.leave_type import REGISTRY, LeaveType, LeaveTypeRegistry
from ..domain.ports import DocumentGenerator, EntitlementRepository, LeaveRecordRepository
from ..domain.values import DateRange, Status
from ..domain.working_days import nth_working_day_from_end, working_days


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# Paternity leave rules (art. 182³ K.p.): ≤ 2 tygodnie, w maks. 2 częściach po min. 1 tydzień.
_PATERNITY_ID = "ojcowski"
_PATERNITY_MIN_PART = 7
_PATERNITY_MAX_TOTAL = 14
_PATERNITY_MAX_PARTS = 2


def _child_key(data: dict) -> str:
    """Groups paternity parts per child (birth date preferred, else name)."""
    return str(data.get("dziecko_data_urodzenia") or data.get("dziecko_imie_nazwisko") or "").strip()


def _number(value: object, default: Optional[float]) -> Optional[float]:
    """Parses a number (comma allowed); returns `default` when empty or non-numeric."""
    text = str(value if value is not None else "").strip().replace(",", ".")
    if not text:
        return default
    try:
        number = float(text)
    except ValueError:
        return default
    return int(number) if number.is_integer() else number


@dataclass(frozen=True)
class PreparedApplication:
    """Result of preparing an application: ready PDF + file name + normalized data."""

    pdf: bytes
    file_name: str
    data: dict


class LeaveService:
    """Orchestration: validation → document → persistence.

    Dependencies are injected via the constructor (repository, generator, registry, clock)
    — so tests substitute doubles without SQLite and WeasyPrint.
    """

    def __init__(
        self,
        repository: LeaveRecordRepository,
        generator: DocumentGenerator,
        entitlements: EntitlementRepository,
        registry: LeaveTypeRegistry = REGISTRY,
        clock: Callable[[], str] = _now_iso,
    ) -> None:
        self._repository = repository
        self._generator = generator
        self._entitlements = entitlements
        self._registry = registry
        self._clock = clock

    @property
    def registry(self) -> LeaveTypeRegistry:
        return self._registry

    def preview(self, payload: dict) -> str:
        """HTML preview of the application — without saving (raises `UnknownLeaveType`)."""
        data = self._registry.validate(payload)
        return self._generator.html(data)

    def prepare(self, payload: dict) -> PreparedApplication:
        """Validates data and generates the PDF. Deliberately *without* saving — persistence
        is a side effect and must not block downloading the document (see `save`)."""
        data = self._registry.validate(payload)
        pdf = self._generator.pdf(data)
        return PreparedApplication(pdf=pdf, file_name=self._file_name(data), data=data)

    def create_applications(self, payload: dict, weekend_days: int = 0) -> list[LeaveRecord]:
        """Generates and saves the application(s), splitting off days off for Saturday
        holidays (§15). Returns 1 record normally, or 2 when `weekend_days > 0` for annual
        leave: the trailing `k` working days become a separate `wolne_za_swieta` record
        (with its own PDF), the rest stays annual leave. Different legal basis → two documents.
        """
        data = self._registry.validate(payload)
        self._require_paternity_rules(data)  # §20.2: urlop ojcowski — min./maks. część, suma
        period = DateRange.from_strings(data.get("data_od"), data.get("data_do"))
        total = working_days(period) or 0
        k = min(max(0, int(weekend_days or 0)), total)

        # §16.1 hard validation: a day off settles in the month of the Saturday holiday, so
        # the split can carve off at most the remaining capacity of the leave-end month.
        if data["typ"] == "wypoczynkowy" and k > 0 and period.valid and period.end is not None:
            k = min(k, self._weekend_capacity_remaining(period.end.year, period.end.month))

        if data["typ"] != "wypoczynkowy" or k <= 0 or not period.valid:
            return [self._generate(data)]

        assert period.start is not None and period.end is not None
        comp_start = nth_working_day_from_end(period, k)
        assert comp_start is not None
        records: list[LeaveRecord] = []
        # Annual-leave part: [start, day before the first comp day] — skip if it would be empty.
        annual_end = comp_start - timedelta(days=1)
        if annual_end >= period.start:
            records.append(self._generate({**data, "data_do": annual_end.isoformat()}))
        # Day-off-for-holiday part: [comp_start, end], carrying the common header fields.
        common = {f.name: data.get(f.name, "") for f in self._registry.common}
        records.append(self._generate({
            **common, "typ": WEEKEND_OFF_ID,
            "data_od": comp_start.isoformat(), "data_do": period.end_iso,
        }))
        return records

    def _generate(self, payload: dict) -> LeaveRecord:
        prepared = self.prepare(payload)
        return self.save(prepared.data, prepared.pdf)

    def application_file_name(self, record: LeaveRecord) -> str:
        """Suggested download file name for a saved record's PDF."""
        return self._file_name(record.data)

    def working_days_in(self, data_od: str, data_do: str) -> Optional[int]:
        """Working days in a range — used to bound the §15 dialog's day count."""
        return working_days(DateRange.from_strings(data_od, data_do))

    def _weekend_capacity_remaining(self, year: int, month: int) -> int:
        """Unredeemed days off for Saturday holidays in a given month (§16.1).

        Capacity = number of Saturday holidays in that month minus days already booked as
        `wolne_za_swieta` in that month (approved or pending; rejected does not count).
        """
        limit = sum(1 for d in saturday_holidays(year) if d.month == month)
        if limit == 0:
            return 0
        used = sum(
            r.working_days or 0
            for r in self._repository.list(year)
            if r.leave_type == WEEKEND_OFF_ID
            and r.status != Status.REJECTED
            and r.period.start is not None
            and r.period.start.month == month
        )
        return max(0, int(limit - used))

    def _require_weekend_capacity(self, data: dict) -> None:
        """Rejects a manual day off for a Saturday holiday that exceeds the month's capacity (§16.1)."""
        period = DateRange.from_strings(data.get("data_od"), data.get("data_do"))
        if period.start is None:
            return
        remaining = self._weekend_capacity_remaining(period.start.year, period.start.month)
        needed = working_days(period) or 0
        if needed > remaining:
            raise ValueError(
                f"Brak dostępnych dni wolnych za święto w miesiącu {period.start.month:02d}.{period.start.year} "
                f"(pozostało {remaining})."
            )

    def _require_paternity_rules(self, data: dict, exclude_id: Optional[int] = None) -> None:
        """Paternity leave (art. 182³): each part ≥ 7 days, ≤ 14 days total, ≤ 2 parts — per child.

        Enforced on every write path (create, manual, period correction), so the correction
        endpoint can't be a back door (§20.2). Grouped by child (birth date, else name) because
        the entitlement is per child, not per year.
        """
        if data.get("typ") != _PATERNITY_ID:
            return
        period = DateRange.from_strings(data.get("data_od"), data.get("data_do"))
        part = period.calendar_days()
        if part is None:
            return  # no dates — length rule needs a range; other validation covers empties
        if part < _PATERNITY_MIN_PART:
            raise ValueError(
                f"Urlop ojcowski musi trwać co najmniej {_PATERNITY_MIN_PART} dni (podano {part})."
            )
        child = _child_key(data)
        others = []
        for r in self._repository.list():
            if r.leave_type != _PATERNITY_ID or r.status == Status.REJECTED or r.id == exclude_id:
                continue
            if _child_key(r.data) != child:
                continue
            # Skip an identical period (idempotent re-submit of the same application).
            if r.period.start_iso == period.start_iso and r.period.end_iso == period.end_iso:
                continue
            others.append(r)
        if len(others) + 1 > _PATERNITY_MAX_PARTS:
            raise ValueError(f"Urlop ojcowski: maksymalnie {_PATERNITY_MAX_PARTS} części na dziecko.")
        total = sum((r.period.calendar_days() or 0) for r in others) + part
        if total > _PATERNITY_MAX_TOTAL:
            raise ValueError(
                f"Urlop ojcowski: łącznie do {_PATERNITY_MAX_TOTAL} dni na dziecko (byłoby {total})."
            )

    def _require_no_overlap(self, record: LeaveRecord, exclude_id: Optional[int] = None) -> None:
        """One leave per day: reject a period overlapping any existing (non-rejected) record (§20.4).

        Excludes the identical application (same content hash) so an idempotent re-save isn't
        treated as a self-collision; `exclude_id` skips the record being corrected in place.
        """
        period = record.period
        if period.start is None or period.end is None:
            return
        for r in self._repository.list():
            if r.status == Status.REJECTED or r.id == exclude_id:
                continue
            if r.content_hash == record.content_hash:
                continue
            if r.period.start is None or r.period.end is None:
                continue
            if r.period.start <= period.end and period.start <= r.period.end:  # zakresy się nakładają
                raise ValueError(
                    f"Okres {period.start_iso}–{period.end_iso} nachodzi na istniejący urlop "
                    f"({r.period.start_iso}–{r.period.end_iso}). W jednym dniu może być tylko jeden urlop."
                )

    def save(self, data: dict, pdf: bytes) -> LeaveRecord:
        """Builds an aggregate from the generated application and persists it (idempotent by content)."""
        days, hours = self._amount(data)
        record = LeaveRecord.from_application(
            data, now=self._clock(), working_days=days, hours=hours, document=pdf
        )
        self._require_no_overlap(record)  # §20.4
        return self._repository.save(record)

    def recompute_amounts(self) -> int:
        """Recomputes `working_days`/`hours` on all records.

        Needed because records from before Phase 2 have an empty amount. Returns the number
        of updated records.
        """
        changed = 0
        for record in self._repository.list():
            days, hours = self._amount(record.data)
            if (days, hours) != (record.working_days, record.hours):
                record.working_days = days
                record.hours = hours
                record.updated_at = self._clock()
                self._repository.update(record)
                changed += 1
        return changed

    def _amount(self, data: dict) -> tuple[Optional[float], Optional[float]]:
        leave_type = self._registry.required(data.get("typ"))
        return compute_amount(leave_type, data)

    def list_records(self, year: Optional[int] = None) -> list[LeaveRecord]:
        return self._repository.list(year)

    # --- Phase 5: statuses, corrections, manual records, deletion --------------------

    def change_status(self, record_id: int, status: str) -> LeaveRecord:
        """Marks a record as approved / rejected / pending."""
        record = self._required_record(record_id)
        record.mark(Status(status), self._clock())
        return self._repository.update(record)

    def correct_period(self, record_id: int, start: str, end: str, reason: str) -> LeaveRecord:
        """Changes a record's period (e.g. shortened by sick leave) and recomputes its amount."""
        record = self._required_record(record_id)
        record.correct_period(DateRange.from_strings(start, end), reason, self._clock())
        # The amount is computed from the new range — we also update the dates in the source data.
        record.data = {**record.data, "data_od": record.period.start_iso or "", "data_do": record.period.end_iso or ""}
        self._require_paternity_rules(record.data, exclude_id=record_id)  # §20.2: nie omijaj walidacji korektą
        self._require_no_overlap(record, exclude_id=record_id)  # §20.4
        record.working_days, record.hours = self._amount(record.data)
        return self._repository.update(record)

    def add_manual(self, payload: dict, status: str = "zaakceptowany") -> LeaveRecord:
        """Adds leave taken outside the application (no PDF)."""
        data = self._registry.validate(payload)
        if data["typ"] == WEEKEND_OFF_ID:
            self._require_weekend_capacity(data)  # §16.1: only within the holiday's month, up to capacity
        self._require_paternity_rules(data)  # §20.2
        days, hours = self._amount(data)
        record = LeaveRecord.manual(data, now=self._clock(), status=Status(status), working_days=days, hours=hours)
        self._require_no_overlap(record)  # §20.4
        return self._repository.save(record)

    def delete_record(self, record_id: int) -> bool:
        return self._repository.delete(record_id)

    def _required_record(self, record_id: int) -> LeaveRecord:
        record = self._repository.get(record_id)
        if record is None:
            raise RecordNotFound(record_id)
        return record

    # --- Attachments (§13.1) ---------------------------------------------------------

    #: Allowed types of files attached to records (server-side validation).
    ALLOWED_ATTACHMENTS = frozenset({"application/pdf", "image/jpeg"})

    def add_attachment(self, record_id: int, content: bytes, mime: str, name: Optional[str]) -> LeaveRecord:
        """Attaches a file (PDF/JPG) to an existing record, replacing the previous one."""
        if mime not in self.ALLOWED_ATTACHMENTS:
            raise ValueError(f"Disallowed file type: {mime}. Allowed: PDF, JPG.")
        record = self._repository.save_attachment(record_id, content, mime, name, self._clock())
        if record is None:
            raise RecordNotFound(record_id)
        return record

    def attachment(self, record_id: int) -> Optional[tuple[bytes, str, Optional[str]]]:
        """The record's attachment as (content, mime, original name) or None."""
        return self._repository.attachment(record_id)

    def holidays(self, year: int) -> list[tuple[str, str]]:
        """Statutory days off in the given year as (ISO date, name), ascending."""
        named = polish_holidays_named(year)
        return [(d.isoformat(), named[d]) for d in sorted(named)]

    # --- Settings (entitlements) and balance -----------------------------------------

    def settings(self, year: int) -> list[Entitlement]:
        """Effective entitlements of the year: saved or default values from the descriptor."""
        saved = self._entitlements.for_year(year)
        return [saved.get(t.id) or self._default_entitlement(t, year) for t in self._registry.all()]

    def save_settings(self, year: int, payload: dict) -> list[Entitlement]:
        """Saves the year's entitlements from the Settings tab data.

        For annual leave it takes numeric limits from the payload; for "checkbox" types
        (paternity, child care) the limits come from the descriptor, and the user controls
        only whether the leave is due (`active`).
        """
        # `wolne_za_swieta` (§14/§15) is a registry type too; its `active` = the single-shift
        # toggle, and it defaults on. Its limit is dynamic (Saturday count), not from here.
        active_by_default = ("wypoczynkowy", WEEKEND_OFF_ID)
        for leave_type in self._registry.all():
            entry = payload.get(leave_type.id, {}) or {}
            self._entitlements.save(
                Entitlement(
                    year=year,
                    leave_type=leave_type.id,
                    active=bool(entry.get("aktywny", leave_type.id in active_by_default)),
                    limit_days=_number(entry.get("limit_dni"), leave_type.default_limit_days),
                    limit_hours=leave_type.default_limit_hours,
                    carried_over=(
                        _number(entry.get("bilans_z_przeniesienia"), 0) if leave_type.has_overdue else None
                    ),
                    notes=str(entry.get("uwagi", "")),
                )
            )
        return self.settings(year)

    def single_shift_enabled(self, year: int) -> bool:
        """Whether extra days off for Saturday holidays are counted (§14). Default: on."""
        saved = self._entitlements.for_year(year).get(WEEKEND_OFF_ID)
        return saved.active if saved is not None else True

    def balance(self, year: int) -> list[BalanceItem]:
        """Leave usage balance for the given year (incl. the §14 Saturday-holiday line)."""
        records = self._repository.list(year)
        effective = {e.leave_type: e for e in self.settings(year)}
        items = compute_balance(self._registry, effective, records)
        if self.single_shift_enabled(year):
            # §16.1: one highlighted line per month that has a Saturday holiday.
            items.extend(weekend_holiday_items(year, saturday_holidays(year), records))
        return items

    def _default_entitlement(self, leave_type: LeaveType, year: int) -> Entitlement:
        # Annual leave and the Saturday-holiday line (§14) are active by default.
        return Entitlement(
            year=year,
            leave_type=leave_type.id,
            active=(leave_type.id in ("wypoczynkowy", WEEKEND_OFF_ID)),
            limit_days=leave_type.default_limit_days,
            limit_hours=leave_type.default_limit_hours,
            carried_over=(0 if leave_type.has_overdue else None),
        )

    def record_pdf(self, record_id: int) -> Optional[bytes]:
        return self._repository.document(record_id)

    @staticmethod
    def _file_name(data: dict) -> str:
        leave_type = data.get("typ", "wniosek")
        person = (data.get("imie_nazwisko") or "").strip().replace(" ", "_")
        date_str = (data.get("data_od") or data.get("data") or "").strip()
        parts = ["wniosek", leave_type]
        if person:
            parts.append(person)
        if date_str:
            parts.append(date_str)
        safe = "_".join(parts)
        allowed = "".join(c for c in safe if c.isalnum() or c in "_-ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
        return f"{allowed or 'wniosek'}.pdf"
