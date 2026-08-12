"""Persistence of records in SQLite (standard library, no dependencies).

Adapters of the repository ports. A single-file database in the data directory
(`WNIOSKI_DATA_DIR`, `data/` by default; `/srv/data` on a volume in the container). PDFs land
on disk under a name derived from the content hash. The schema is versioned via
`PRAGMA user_version`.

§18 multi-tenancy: every leave record and entitlement carries a `user_id`; the record and
entitlement repositories are **scoped to one user** (constructed with their id) and filter
every query by it, so a user only ever sees their own data. The stored `tresc_hash` is
namespaced with the user id (`"<user_id>:<content_hash>"`) so idempotent upsert stays
per-user without changing the global UNIQUE constraint.

SQLite column names stay Polish — they are the storage contract; the Python side is English
and the `_from_row` mapping bridges the two.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..domain.entitlement import Entitlement
from ..domain.leave_record import LeaveRecord
from ..domain.ports import EntitlementRepository, LeaveRecordRepository, UserRepository
from ..domain.user import User
from ..domain.values import DateRange, Pool, Source, Status

_log = logging.getLogger("wnioski")
_SCHEMA_VERSION = 6

# MIME → on-disk file extension (§13.1). Only allowed attachment types.
_EXTENSION = {"application/pdf": ".pdf", "image/jpeg": ".jpg"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_user (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL UNIQUE,
    haslo_hash TEXT NOT NULL DEFAULT '',
    google_sub TEXT,
    profil     TEXT NOT NULL DEFAULT '{}',
    utworzono  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entitlement (
    user_id                INTEGER NOT NULL,
    rok                    INTEGER NOT NULL,
    typ                    TEXT    NOT NULL,
    aktywny                INTEGER NOT NULL DEFAULT 1,
    limit_dni              REAL,
    limit_godzin           REAL,
    bilans_z_przeniesienia REAL,
    uwagi                  TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, rok, typ)
);
CREATE TABLE IF NOT EXISTS leave_record (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER,
    typ               TEXT    NOT NULL,
    rok               INTEGER,
    za_okres          TEXT    NOT NULL DEFAULT 'biezacy',
    zrodlo            TEXT    NOT NULL DEFAULT 'wniosek',
    pdf_path          TEXT,
    zalacznik_mime    TEXT,
    zalacznik_nazwa   TEXT,
    data_od           TEXT,
    data_do           TEXT,
    dni_robocze       REAL,
    godziny           REAL,
    dane_json         TEXT    NOT NULL,
    status            TEXT    NOT NULL DEFAULT 'do_akceptacji',
    korekta_powod     TEXT,
    data_od_pierwotna TEXT,
    data_do_pierwotna TEXT,
    tresc_hash        TEXT    UNIQUE,
    utworzono         TEXT    NOT NULL,
    zmieniono         TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_leave_record_typ ON leave_record(typ);
"""

# Indexes created separately — after the columns exist (fresh: table def; legacy: migration).
_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_leave_record_user ON leave_record(user_id, rok);
CREATE UNIQUE INDEX IF NOT EXISTS ux_user_google ON app_user(google_sub) WHERE google_sub IS NOT NULL;
"""


def default_data_dir() -> Path:
    """Data directory: from `WNIOSKI_DATA_DIR` or `data/` in the project directory."""
    fallback = Path(__file__).resolve().parent.parent.parent / "data"
    return Path(os.environ.get("WNIOSKI_DATA_DIR", str(fallback)))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(r["name"] == column for r in conn.execute(f"PRAGMA table_info({table})"))


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _create_tables(db: Path) -> None:
    """Idempotently create the current-schema tables (no migration/seeding)."""
    conn = _connect(db)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def ensure_schema(data_dir: Optional[Path] = None) -> None:
    """One-time startup: create tables, migrate v3→v4 and adopt legacy data to an owner.

    Fresh installs get the v4 schema directly. Upgrading a single-user (v<4) database adds
    `user_id`, seeds an **owner** account and assigns all existing records/entitlements to it,
    so pre-multi-user data is preserved under one account.
    """
    directory = Path(data_dir) if data_dir else default_data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "pdfs").mkdir(parents=True, exist_ok=True)
    conn = _connect(directory / "wnioski.db")
    try:
        legacy = _table_exists(conn, "leave_record") and not _has_column(conn, "leave_record", "user_id")
        conn.executescript(_SCHEMA)  # creates any missing tables (app_user; on fresh: all v5)
        if legacy:
            _upgrade_to_v4(conn)
        # v4 → v5: Google account linking column.
        if not _has_column(conn, "app_user", "google_sub"):
            conn.execute("ALTER TABLE app_user ADD COLUMN google_sub TEXT")
        # v5 → v6: per-user profile (default common fields — name, position, employer, §19).
        if not _has_column(conn, "app_user", "profil"):
            conn.execute("ALTER TABLE app_user ADD COLUMN profil TEXT NOT NULL DEFAULT '{}'")
        conn.executescript(_INDEXES)  # columns now exist in all paths
        conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()


def _seed_owner(conn: sqlite3.Connection) -> int:
    """Ensures an owner account exists (to adopt legacy data); returns its id."""
    row = conn.execute("SELECT id FROM app_user ORDER BY id LIMIT 1").fetchone()
    if row:
        return row["id"]
    from .security import hash_password

    username = os.environ.get("WNIOSKI_OWNER", "owner")
    password = os.environ.get("WNIOSKI_OWNER_PASSWORD")
    generated = password is None
    if generated:
        password = secrets.token_urlsafe(12)
    cur = conn.execute(
        "INSERT INTO app_user (username, haslo_hash, utworzono) VALUES (?, ?, ?)",
        (username, hash_password(password), _now()),
    )
    if generated:
        _log.warning(
            "Utworzono konto wlasciciela '%s' z wygenerowanym haslem: %s "
            "(ustaw WNIOSKI_OWNER_PASSWORD i zmien je po zalogowaniu).",
            username, password,
        )
    return int(cur.lastrowid or 0)


def _upgrade_to_v4(conn: sqlite3.Connection) -> None:
    """Migrate a pre-multi-user database: add user_id, seed owner, adopt existing data."""
    for column in ("user_id", "zalacznik_mime", "zalacznik_nazwa"):
        if not _has_column(conn, "leave_record", column):
            kind = "INTEGER" if column == "user_id" else "TEXT"
            conn.execute(f"ALTER TABLE leave_record ADD COLUMN {column} {kind}")

    owner_id = _seed_owner(conn)

    # Adopt orphan records; namespace the content hash so per-user idempotency holds.
    conn.execute(
        "UPDATE leave_record SET user_id = ?, tresc_hash = ? || ':' || tresc_hash "
        "WHERE user_id IS NULL",
        (owner_id, str(owner_id)),
    )

    # Rebuild entitlement with the composite primary key (user_id, rok, typ).
    if not _has_column(conn, "entitlement", "user_id"):
        conn.execute("ALTER TABLE entitlement RENAME TO entitlement_old")
        conn.executescript(_SCHEMA)  # recreates `entitlement` with the new shape
        conn.execute(
            """
            INSERT INTO entitlement
                (user_id, rok, typ, aktywny, limit_dni, limit_godzin, bilans_z_przeniesienia, uwagi)
            SELECT ?, rok, typ, aktywny, limit_dni, limit_godzin, bilans_z_przeniesienia, uwagi
            FROM entitlement_old
            """,
            (owner_id,),
        )
        conn.execute("DROP TABLE entitlement_old")


# --- User repository ------------------------------------------------------------------

class SqliteUserRepository(UserRepository):
    """User accounts in the shared SQLite database (§18)."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._db = (Path(data_dir) if data_dir else default_data_dir()) / "wnioski.db"
        _create_tables(self._db)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> User:
        return User(id=row["id"], username=row["username"], password_hash=row["haslo_hash"],
                    created_at=row["utworzono"], google_sub=row["google_sub"])

    def get_by_username(self, username: str) -> Optional[User]:
        conn = _connect(self._db)
        try:
            row = conn.execute("SELECT * FROM app_user WHERE username = ?", (username,)).fetchone()
        finally:
            conn.close()
        return self._from_row(row) if row else None

    def get_by_google_sub(self, google_sub: str) -> Optional[User]:
        conn = _connect(self._db)
        try:
            row = conn.execute("SELECT * FROM app_user WHERE google_sub = ?", (google_sub,)).fetchone()
        finally:
            conn.close()
        return self._from_row(row) if row else None

    def get(self, user_id: int) -> Optional[User]:
        conn = _connect(self._db)
        try:
            row = conn.execute("SELECT * FROM app_user WHERE id = ?", (user_id,)).fetchone()
        finally:
            conn.close()
        return self._from_row(row) if row else None

    def create(self, username: str, password_hash: str, now: str) -> User:
        return self._insert(username, password_hash, None, now)

    def create_google(self, username: str, google_sub: str, now: str) -> User:
        return self._insert(username, "", google_sub, now)

    def _insert(self, username: str, password_hash: str, google_sub: Optional[str], now: str) -> User:
        conn = _connect(self._db)
        try:
            cur = conn.execute(
                "INSERT INTO app_user (username, haslo_hash, google_sub, utworzono) VALUES (?, ?, ?, ?)",
                (username, password_hash, google_sub, now),
            )
            conn.commit()
            user_id = int(cur.lastrowid or 0)
        finally:
            conn.close()
        return User(id=user_id, username=username, password_hash=password_hash,
                    created_at=now, google_sub=google_sub)

    def count(self) -> int:
        conn = _connect(self._db)
        try:
            return int(conn.execute("SELECT COUNT(*) FROM app_user").fetchone()[0])
        finally:
            conn.close()

    def first(self) -> Optional[User]:
        conn = _connect(self._db)
        try:
            row = conn.execute("SELECT * FROM app_user ORDER BY id LIMIT 1").fetchone()
        finally:
            conn.close()
        return self._from_row(row) if row else None

    def set_password(self, user_id: int, password_hash: str) -> None:
        conn = _connect(self._db)
        try:
            conn.execute("UPDATE app_user SET haslo_hash = ? WHERE id = ?", (password_hash, user_id))
            conn.commit()
        finally:
            conn.close()

    def delete(self, user_id: int) -> None:
        conn = _connect(self._db)
        try:
            conn.execute("DELETE FROM app_user WHERE id = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()

    def get_profile(self, user_id: int) -> dict:
        conn = _connect(self._db)
        try:
            row = conn.execute("SELECT profil FROM app_user WHERE id = ?", (user_id,)).fetchone()
        finally:
            conn.close()
        if not row or not row["profil"]:
            return {}
        try:
            data = json.loads(row["profil"])
        except (ValueError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}

    def save_profile(self, user_id: int, profile: dict) -> dict:
        clean = {str(k): ("" if v is None else str(v)) for k, v in (profile or {}).items()}
        conn = _connect(self._db)
        try:
            conn.execute(
                "UPDATE app_user SET profil = ? WHERE id = ?",
                (json.dumps(clean, ensure_ascii=False), user_id),
            )
            conn.commit()
        finally:
            conn.close()
        return clean


# --- Leave record repository (user-scoped) --------------------------------------------

class SqliteLeaveRecordRepository(LeaveRecordRepository):
    """Leave-record repository backed by SQLite + PDF files on disk, scoped to one user."""

    def __init__(self, user_id: int, data_dir: Optional[Path] = None) -> None:
        self._user_id = user_id
        self._dir = Path(data_dir) if data_dir else default_data_dir()
        self._db = self._dir / "wnioski.db"
        self._pdf_dir = self._dir / "pdfs"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._pdf_dir.mkdir(parents=True, exist_ok=True)
        _create_tables(self._db)

    def _connect(self) -> sqlite3.Connection:
        return _connect(self._db)

    def _hash_key(self, record: LeaveRecord) -> str:
        return f"{self._user_id}:{record.content_hash}"  # namespaced per user

    @staticmethod
    def _from_row(row: sqlite3.Row) -> LeaveRecord:
        original = None
        if row["data_od_pierwotna"] or row["data_do_pierwotna"]:
            original = DateRange.from_strings(row["data_od_pierwotna"], row["data_do_pierwotna"])
        mime = row["zalacznik_mime"]
        if row["pdf_path"] and not mime:
            mime = "application/pdf"
        return LeaveRecord(
            id=row["id"],
            leave_type=row["typ"],
            year=row["rok"],
            data=json.loads(row["dane_json"]),
            period=DateRange.from_strings(row["data_od"], row["data_do"]),
            status=Status(row["status"]),
            source=Source(row["zrodlo"]),
            pool=Pool(row["za_okres"]),
            working_days=row["dni_robocze"],
            hours=row["godziny"],
            attachment_mime=mime,
            attachment_name=row["zalacznik_nazwa"],
            correction_reason=row["korekta_powod"],
            original_period=original,
            created_at=row["utworzono"],
            updated_at=row["zmieniono"],
        )

    def save(self, record: LeaveRecord) -> LeaveRecord:
        content_hash = self._hash_key(record)
        pdf_name = f"{content_hash}.pdf".replace(":", "_")
        if record.document is not None:
            (self._pdf_dir / pdf_name).write_bytes(record.document)

        original = record.original_period
        params = {
            "user_id": self._user_id,
            "typ": record.leave_type,
            "rok": record.year,
            "za_okres": record.pool.value,
            "zrodlo": record.source.value,
            "pdf_path": pdf_name if record.document is not None else None,
            "zalacznik_mime": "application/pdf" if record.document is not None else None,
            "data_od": record.period.start_iso,
            "data_do": record.period.end_iso,
            "dni_robocze": record.working_days,
            "godziny": record.hours,
            "dane_json": json.dumps(record.data, ensure_ascii=False),
            "status": record.status.value,
            "korekta_powod": record.correction_reason,
            "data_od_pierwotna": original.start_iso if original else None,
            "data_do_pierwotna": original.end_iso if original else None,
            "tresc_hash": content_hash,
            "utworzono": record.created_at,
            "zmieniono": record.updated_at,
        }
        conn = self._connect()
        try:
            row = conn.execute(
                """
                INSERT INTO leave_record
                    (user_id, typ, rok, za_okres, zrodlo, pdf_path, zalacznik_mime, data_od, data_do,
                     dni_robocze, godziny, dane_json, status, korekta_powod, data_od_pierwotna,
                     data_do_pierwotna, tresc_hash, utworzono, zmieniono)
                VALUES
                    (:user_id, :typ, :rok, :za_okres, :zrodlo, :pdf_path, :zalacznik_mime, :data_od,
                     :data_do, :dni_robocze, :godziny, :dane_json, :status, :korekta_powod,
                     :data_od_pierwotna, :data_do_pierwotna, :tresc_hash, :utworzono, :zmieniono)
                ON CONFLICT(tresc_hash) DO UPDATE SET
                    pdf_path       = COALESCE(excluded.pdf_path, pdf_path),
                    zalacznik_mime = COALESCE(excluded.zalacznik_mime, zalacznik_mime),
                    zmieniono      = excluded.zmieniono
                RETURNING *
                """,
                params,
            ).fetchone()
            conn.commit()
        finally:
            conn.close()
        return self._from_row(row)

    def update(self, record: LeaveRecord) -> LeaveRecord:
        if record.id is None:
            raise ValueError("Update requires a record with an assigned id.")
        original = record.original_period
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE leave_record SET
                    status            = :status,
                    za_okres          = :za_okres,
                    dni_robocze       = :dni_robocze,
                    godziny           = :godziny,
                    data_od           = :data_od,
                    data_do           = :data_do,
                    korekta_powod     = :korekta_powod,
                    data_od_pierwotna = :data_od_pierwotna,
                    data_do_pierwotna = :data_do_pierwotna,
                    zmieniono         = :zmieniono
                WHERE id = :id AND user_id = :user_id
                """,
                {
                    "status": record.status.value,
                    "za_okres": record.pool.value,
                    "dni_robocze": record.working_days,
                    "godziny": record.hours,
                    "data_od": record.period.start_iso,
                    "data_do": record.period.end_iso,
                    "korekta_powod": record.correction_reason,
                    "data_od_pierwotna": original.start_iso if original else None,
                    "data_do_pierwotna": original.end_iso if original else None,
                    "zmieniono": record.updated_at,
                    "id": record.id,
                    "user_id": self._user_id,
                },
            )
            conn.commit()
        finally:
            conn.close()
        return record

    def list(self, year: Optional[int] = None) -> list[LeaveRecord]:
        query = "SELECT * FROM leave_record WHERE user_id = ?"
        params: tuple = (self._user_id,)
        if year is not None:
            query += " AND rok = ?"
            params = (self._user_id, year)
        query += " ORDER BY COALESCE(data_od, utworzono) DESC, id DESC"
        conn = self._connect()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
        return [self._from_row(r) for r in rows]

    def get(self, record_id: int) -> Optional[LeaveRecord]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM leave_record WHERE id = ? AND user_id = ?", (record_id, self._user_id)
            ).fetchone()
        finally:
            conn.close()
        return self._from_row(row) if row else None

    def document(self, record_id: int) -> Optional[bytes]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT pdf_path FROM leave_record WHERE id = ? AND user_id = ?",
                (record_id, self._user_id),
            ).fetchone()
        finally:
            conn.close()
        if not row or not row["pdf_path"]:
            return None
        path = self._pdf_dir / row["pdf_path"]
        return path.read_bytes() if path.exists() else None

    def delete_all(self) -> None:
        """§23.4: kasuje wszystkie rekordy użytkownika oraz ich pliki (PDF/załączniki) z dysku."""
        conn = self._connect()
        try:
            paths = [
                r["pdf_path"]
                for r in conn.execute(
                    "SELECT pdf_path FROM leave_record WHERE user_id = ?", (self._user_id,)
                ).fetchall()
                if r["pdf_path"]
            ]
            conn.execute("DELETE FROM leave_record WHERE user_id = ?", (self._user_id,))
            conn.commit()
        finally:
            conn.close()
        for path in paths:
            (self._pdf_dir / path).unlink(missing_ok=True)

    def save_attachment(
        self, record_id: int, content: bytes, mime: str, name: Optional[str], now: str
    ) -> Optional[LeaveRecord]:
        extension = _EXTENSION.get(mime)
        if extension is None:
            raise ValueError(f"Disallowed attachment type: {mime}")
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT pdf_path FROM leave_record WHERE id = ? AND user_id = ?",
                (record_id, self._user_id),
            ).fetchone()
            if row is None:
                return None
            old = row["pdf_path"]
            new = f"zal_{self._user_id}_{record_id}{extension}"
            (self._pdf_dir / new).write_bytes(content)
            if old and old != new:
                (self._pdf_dir / old).unlink(missing_ok=True)
            conn.execute(
                """
                UPDATE leave_record SET
                    pdf_path        = :pdf_path,
                    zalacznik_mime  = :mime,
                    zalacznik_nazwa = :name,
                    zmieniono       = :now
                WHERE id = :id AND user_id = :user_id
                """,
                {"pdf_path": new, "mime": mime, "name": name, "now": now,
                 "id": record_id, "user_id": self._user_id},
            )
            conn.commit()
            fresh = conn.execute(
                "SELECT * FROM leave_record WHERE id = ? AND user_id = ?", (record_id, self._user_id)
            ).fetchone()
        finally:
            conn.close()
        return self._from_row(fresh) if fresh else None

    def attachment(self, record_id: int) -> Optional[tuple[bytes, str, Optional[str]]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT pdf_path, zalacznik_mime, zalacznik_nazwa FROM leave_record "
                "WHERE id = ? AND user_id = ?",
                (record_id, self._user_id),
            ).fetchone()
        finally:
            conn.close()
        if not row or not row["pdf_path"]:
            return None
        path = self._pdf_dir / row["pdf_path"]
        if not path.exists():
            return None
        mime = row["zalacznik_mime"] or "application/pdf"
        return path.read_bytes(), mime, row["zalacznik_nazwa"]

    def delete(self, record_id: int) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT pdf_path FROM leave_record WHERE id = ? AND user_id = ?",
                (record_id, self._user_id),
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                "DELETE FROM leave_record WHERE id = ? AND user_id = ?", (record_id, self._user_id)
            )
            conn.commit()
        finally:
            conn.close()
        if row["pdf_path"]:
            (self._pdf_dir / row["pdf_path"]).unlink(missing_ok=True)
        return True


# --- Entitlement repository (user-scoped) ---------------------------------------------

class SqliteEntitlementRepository(EntitlementRepository):
    """Entitlement (limits) repository in the same SQLite database, scoped to one user."""

    def __init__(self, user_id: int, data_dir: Optional[Path] = None) -> None:
        self._user_id = user_id
        self._db = (Path(data_dir) if data_dir else default_data_dir()) / "wnioski.db"
        _create_tables(self._db)

    def _connect(self) -> sqlite3.Connection:
        return _connect(self._db)

    def delete_all(self) -> None:
        """§23.4: kasuje wszystkie uprawnienia użytkownika (wszystkie lata)."""
        conn = self._connect()
        try:
            conn.execute("DELETE FROM entitlement WHERE user_id = ?", (self._user_id,))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Entitlement:
        return Entitlement(
            year=row["rok"],
            leave_type=row["typ"],
            active=bool(row["aktywny"]),
            limit_days=row["limit_dni"],
            limit_hours=row["limit_godzin"],
            carried_over=row["bilans_z_przeniesienia"],
            notes=row["uwagi"],
        )

    def for_year(self, year: int) -> dict[str, Entitlement]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM entitlement WHERE user_id = ? AND rok = ?", (self._user_id, year)
            ).fetchall()
        finally:
            conn.close()
        return {r["typ"]: self._from_row(r) for r in rows}

    def save(self, entitlement: Entitlement) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO entitlement
                    (user_id, rok, typ, aktywny, limit_dni, limit_godzin, bilans_z_przeniesienia, uwagi)
                VALUES
                    (:user_id, :rok, :typ, :aktywny, :limit_dni, :limit_godzin, :bilans_z_przeniesienia, :uwagi)
                ON CONFLICT(user_id, rok, typ) DO UPDATE SET
                    aktywny                = excluded.aktywny,
                    limit_dni              = excluded.limit_dni,
                    limit_godzin           = excluded.limit_godzin,
                    bilans_z_przeniesienia = excluded.bilans_z_przeniesienia,
                    uwagi                  = excluded.uwagi
                """,
                {
                    "user_id": self._user_id,
                    "rok": entitlement.year,
                    "typ": entitlement.leave_type,
                    "aktywny": 1 if entitlement.active else 0,
                    "limit_dni": entitlement.limit_days,
                    "limit_godzin": entitlement.limit_hours,
                    "bilans_z_przeniesienia": entitlement.carried_over,
                    "uwagi": entitlement.notes,
                },
            )
            conn.commit()
        finally:
            conn.close()
