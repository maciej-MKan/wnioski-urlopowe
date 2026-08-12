"""Persistence of records via SQLAlchemy Core — portable across SQLite and PostgreSQL.

Domyślnie SQLite (jeden plik w `WNIOSKI_DATA_DIR`), a przez `WNIOSKI_DB_URL` można wskazać
PostgreSQL (`postgresql+psycopg://user:pass@host:5432/db`). Silnik jest wybierany z URL-a, więc
testy/lokalnie chodzą na SQLite, a prod może użyć Postgresa bez zmian w kodzie repozytoriów.

PDF-y i załączniki nadal leżą na dysku w katalogu `WNIOSKI_DATA_DIR/pdfs` (nazwa z content-hasha).
Schema dla świeżej bazy tworzy `MetaData.create_all`; **istniejąca** baza SQLite z czasów przed
wielodostępem jest migrowana surowym kodem sqlite3 (`_sqlite_legacy_upgrade`, ścieżka v3→v4).

§18 multi-tenancy: każdy rekord i uprawnienie ma `user_id`; repozytoria rekordów/uprawnień są
**zawężone do jednego użytkownika**. `tresc_hash` jest namespace'owany id użytkownika
(`"<user_id>:<hash>"`), by idempotentny upsert był per-user. Nazwy kolumn zostają polskie.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    create_engine,
    delete,
    func,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from ..domain.entitlement import Entitlement
from ..domain.leave_record import LeaveRecord
from ..domain.ports import EntitlementRepository, LeaveRecordRepository, UserRepository
from ..domain.user import User
from ..domain.values import DateRange, Pool, Source, Status

_log = logging.getLogger("wnioski")
_SCHEMA_VERSION = 6

# MIME → rozszerzenie pliku na dysku (§13.1). Tylko dozwolone typy załączników.
_EXTENSION = {"application/pdf": ".pdf", "image/jpeg": ".jpg"}

# --- Schemat (SQLAlchemy Core — źródło prawdy dla świeżej bazy, oba dialekty) ----------

_metadata = MetaData()

app_user = Table(
    "app_user", _metadata,
    Column("id", Integer, primary_key=True),
    Column("username", Text, nullable=False, unique=True),
    Column("haslo_hash", Text, nullable=False, server_default=""),
    Column("google_sub", Text),
    Column("profil", Text, nullable=False, server_default="{}"),
    Column("utworzono", Text, nullable=False),
)

entitlement = Table(
    "entitlement", _metadata,
    Column("user_id", Integer, nullable=False),
    Column("rok", Integer, nullable=False),
    Column("typ", Text, nullable=False),
    Column("aktywny", Integer, nullable=False, server_default="1"),
    Column("limit_dni", Float),
    Column("limit_godzin", Float),
    Column("bilans_z_przeniesienia", Float),
    Column("uwagi", Text, nullable=False, server_default=""),
    PrimaryKeyConstraint("user_id", "rok", "typ"),
)

leave_record = Table(
    "leave_record", _metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer),
    Column("typ", Text, nullable=False),
    Column("rok", Integer),
    Column("za_okres", Text, nullable=False, server_default="biezacy"),
    Column("zrodlo", Text, nullable=False, server_default="wniosek"),
    Column("pdf_path", Text),
    Column("zalacznik_mime", Text),
    Column("zalacznik_nazwa", Text),
    Column("data_od", Text),
    Column("data_do", Text),
    Column("dni_robocze", Float),
    Column("godziny", Float),
    Column("dane_json", Text, nullable=False),
    Column("status", Text, nullable=False, server_default="do_akceptacji"),
    Column("korekta_powod", Text),
    Column("data_od_pierwotna", Text),
    Column("data_do_pierwotna", Text),
    Column("tresc_hash", Text, unique=True),
    Column("utworzono", Text, nullable=False),
    Column("zmieniono", Text, nullable=False),
    Index("idx_leave_record_typ", "typ"),
    Index("idx_leave_record_user", "user_id", "rok"),
)

# Unikalny częściowy indeks na google_sub (tylko gdy niepusty) — składnia per dialekt.
Index(
    "ux_user_google", app_user.c.google_sub, unique=True,
    sqlite_where=text("google_sub IS NOT NULL"),
    postgresql_where=text("google_sub IS NOT NULL"),
)


def default_data_dir() -> Path:
    """Katalog danych: z `WNIOSKI_DATA_DIR` albo `data/` w katalogu projektu."""
    fallback = Path(__file__).resolve().parent.parent.parent / "data"
    return Path(os.environ.get("WNIOSKI_DATA_DIR", str(fallback)))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --- Silnik (wybór z URL-a; cache per URL) --------------------------------------------

_engines: dict[str, Engine] = {}


def _database_url(data_dir: Optional[Path]) -> str:
    url = os.environ.get("WNIOSKI_DB_URL")
    if url:
        return url
    db = (Path(data_dir) if data_dir else default_data_dir()) / "wnioski.db"
    return f"sqlite:///{db}"


def _engine(data_dir: Optional[Path] = None) -> Engine:
    url = _database_url(data_dir)
    eng = _engines.get(url)
    if eng is None:
        if url.startswith("sqlite"):
            # NullPool + check_same_thread=False: nowe połączenie na operację (jak dotąd), bezpieczne
            # dla wątków workerów FastAPI.
            eng = create_engine(url, connect_args={"check_same_thread": False}, poolclass=NullPool, future=True)
        else:
            eng = create_engine(url, pool_pre_ping=True, future=True)
        _engines[url] = eng
    return eng


def _dialect_insert(engine: Engine):
    return pg_insert if engine.dialect.name == "postgresql" else sqlite_insert


# --- Schema: świeża (SQLAlchemy) + legacy upgrade istniejącego SQLite -------------------

def ensure_schema(data_dir: Optional[Path] = None) -> None:
    """Startowa inicjalizacja schematu. Świeża baza (SQLite/Postgres) → `create_all`;
    istniejąca **stara** baza SQLite (sprzed wielodostępu) → migracja surowym sqlite3 (v3→v4,
    dodanie `google_sub`/`profil`), by zachować dane pod kontem właściciela.
    """
    directory = Path(data_dir) if data_dir else default_data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "pdfs").mkdir(parents=True, exist_ok=True)
    engine = _engine(data_dir)
    if engine.dialect.name == "sqlite":
        _sqlite_legacy_upgrade(directory / "wnioski.db")
    _metadata.create_all(engine)


def _sqlite_connect(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(r["name"] == column for r in conn.execute(f"PRAGMA table_info({table})"))


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _sqlite_legacy_upgrade(db: Path) -> None:
    """Migruje istniejącą starą (jednoużytkownikową) bazę SQLite. Dla nieistniejącej/świeżej
    nic nie robi — resztę utworzy `create_all`."""
    if not db.exists():
        return
    conn = _sqlite_connect(db)
    try:
        if not _table_exists(conn, "leave_record"):
            return  # świeży plik bez tabel — zostawiamy create_all
        if not _has_column(conn, "leave_record", "user_id"):
            _upgrade_to_v4(conn)
        if _table_exists(conn, "app_user"):
            if not _has_column(conn, "app_user", "google_sub"):
                conn.execute("ALTER TABLE app_user ADD COLUMN google_sub TEXT")
            if not _has_column(conn, "app_user", "profil"):
                conn.execute("ALTER TABLE app_user ADD COLUMN profil TEXT NOT NULL DEFAULT '{}'")
        conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()


def _seed_owner(conn: sqlite3.Connection) -> int:
    """Zapewnia konto właściciela (do adopcji danych legacy); zwraca jego id."""
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
    """Migracja bazy sprzed wielodostępu: dodaj user_id, utwórz właściciela, adoptuj dane."""
    # app_user musi istnieć, by zasiać właściciela.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS app_user ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,"
        " haslo_hash TEXT NOT NULL DEFAULT '', google_sub TEXT,"
        " profil TEXT NOT NULL DEFAULT '{}', utworzono TEXT NOT NULL)"
    )
    for column in ("user_id", "zalacznik_mime", "zalacznik_nazwa"):
        if not _has_column(conn, "leave_record", column):
            kind = "INTEGER" if column == "user_id" else "TEXT"
            conn.execute(f"ALTER TABLE leave_record ADD COLUMN {column} {kind}")

    owner_id = _seed_owner(conn)
    conn.execute(
        "UPDATE leave_record SET user_id = ?, tresc_hash = ? || ':' || tresc_hash WHERE user_id IS NULL",
        (owner_id, str(owner_id)),
    )

    if not _has_column(conn, "entitlement", "user_id"):
        conn.execute("ALTER TABLE entitlement RENAME TO entitlement_old")
        conn.execute(
            "CREATE TABLE entitlement ("
            " user_id INTEGER NOT NULL, rok INTEGER NOT NULL, typ TEXT NOT NULL,"
            " aktywny INTEGER NOT NULL DEFAULT 1, limit_dni REAL, limit_godzin REAL,"
            " bilans_z_przeniesienia REAL, uwagi TEXT NOT NULL DEFAULT '',"
            " PRIMARY KEY (user_id, rok, typ))"
        )
        conn.execute(
            "INSERT INTO entitlement"
            " (user_id, rok, typ, aktywny, limit_dni, limit_godzin, bilans_z_przeniesienia, uwagi)"
            " SELECT ?, rok, typ, aktywny, limit_dni, limit_godzin, bilans_z_przeniesienia, uwagi"
            " FROM entitlement_old",
            (owner_id,),
        )
        conn.execute("DROP TABLE entitlement_old")


# --- User repository ------------------------------------------------------------------

class SqliteUserRepository(UserRepository):
    """Konta użytkowników w bazie (nazwa historyczna; działa też na Postgresie)."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._engine = _engine(data_dir)
        _metadata.create_all(self._engine)

    @staticmethod
    def _from_row(row: Any) -> User:
        return User(id=row["id"], username=row["username"], password_hash=row["haslo_hash"],
                    created_at=row["utworzono"], google_sub=row["google_sub"])

    def _one(self, whereclause) -> Optional[User]:
        with self._engine.connect() as conn:
            row = conn.execute(select(app_user).where(whereclause)).mappings().fetchone()
        return self._from_row(row) if row else None

    def get_by_username(self, username: str) -> Optional[User]:
        return self._one(app_user.c.username == username)

    def get_by_google_sub(self, google_sub: str) -> Optional[User]:
        return self._one(app_user.c.google_sub == google_sub)

    def get(self, user_id: int) -> Optional[User]:
        return self._one(app_user.c.id == user_id)

    def create(self, username: str, password_hash: str, now: str) -> User:
        return self._insert(username, password_hash, None, now)

    def create_google(self, username: str, google_sub: str, now: str) -> User:
        return self._insert(username, "", google_sub, now)

    def _insert(self, username: str, password_hash: str, google_sub: Optional[str], now: str) -> User:
        stmt = insert(app_user).values(
            username=username, haslo_hash=password_hash, google_sub=google_sub, utworzono=now,
        ).returning(app_user.c.id)
        with self._engine.begin() as conn:
            user_id = int(conn.execute(stmt).scalar_one())
        return User(id=user_id, username=username, password_hash=password_hash,
                    created_at=now, google_sub=google_sub)

    def count(self) -> int:
        with self._engine.connect() as conn:
            return int(conn.execute(select(func.count()).select_from(app_user)).scalar_one())

    def first(self) -> Optional[User]:
        with self._engine.connect() as conn:
            row = conn.execute(select(app_user).order_by(app_user.c.id).limit(1)).mappings().fetchone()
        return self._from_row(row) if row else None

    def set_password(self, user_id: int, password_hash: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(update(app_user).where(app_user.c.id == user_id).values(haslo_hash=password_hash))

    def delete(self, user_id: int) -> None:
        with self._engine.begin() as conn:
            conn.execute(delete(app_user).where(app_user.c.id == user_id))

    def get_profile(self, user_id: int) -> dict:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(app_user.c.profil).where(app_user.c.id == user_id)
            ).mappings().fetchone()
        if not row or not row["profil"]:
            return {}
        try:
            data = json.loads(row["profil"])
        except (ValueError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}

    def save_profile(self, user_id: int, profile: dict) -> dict:
        clean = {str(k): ("" if v is None else str(v)) for k, v in (profile or {}).items()}
        with self._engine.begin() as conn:
            conn.execute(
                update(app_user).where(app_user.c.id == user_id)
                .values(profil=json.dumps(clean, ensure_ascii=False))
            )
        return clean


# --- Leave record repository (user-scoped) --------------------------------------------

class SqliteLeaveRecordRepository(LeaveRecordRepository):
    """Repozytorium rekordów urlopu (baza + pliki PDF na dysku), zawężone do użytkownika."""

    def __init__(self, user_id: int, data_dir: Optional[Path] = None) -> None:
        self._user_id = user_id
        self._dir = Path(data_dir) if data_dir else default_data_dir()
        self._pdf_dir = self._dir / "pdfs"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._pdf_dir.mkdir(parents=True, exist_ok=True)
        self._engine = _engine(data_dir)
        _metadata.create_all(self._engine)

    def _hash_key(self, record: LeaveRecord) -> str:
        return f"{self._user_id}:{record.content_hash}"  # namespaced per user

    @staticmethod
    def _from_row(row: Any) -> LeaveRecord:
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
        values = {
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
        ins = _dialect_insert(self._engine)(leave_record).values(**values)
        stmt = ins.on_conflict_do_update(
            index_elements=[leave_record.c.tresc_hash],
            set_={
                "pdf_path": func.coalesce(ins.excluded.pdf_path, leave_record.c.pdf_path),
                "zalacznik_mime": func.coalesce(ins.excluded.zalacznik_mime, leave_record.c.zalacznik_mime),
                "zmieniono": ins.excluded.zmieniono,
            },
        ).returning(leave_record)
        with self._engine.begin() as conn:
            row = conn.execute(stmt).mappings().fetchone()
        return self._from_row(row)

    def update(self, record: LeaveRecord) -> LeaveRecord:
        if record.id is None:
            raise ValueError("Update requires a record with an assigned id.")
        original = record.original_period
        with self._engine.begin() as conn:
            conn.execute(
                update(leave_record)
                .where(leave_record.c.id == record.id, leave_record.c.user_id == self._user_id)
                .values(
                    status=record.status.value,
                    za_okres=record.pool.value,
                    dni_robocze=record.working_days,
                    godziny=record.hours,
                    data_od=record.period.start_iso,
                    data_do=record.period.end_iso,
                    korekta_powod=record.correction_reason,
                    data_od_pierwotna=original.start_iso if original else None,
                    data_do_pierwotna=original.end_iso if original else None,
                    zmieniono=record.updated_at,
                )
            )
        return record

    def list(self, year: Optional[int] = None) -> list[LeaveRecord]:
        stmt = select(leave_record).where(leave_record.c.user_id == self._user_id)
        if year is not None:
            stmt = stmt.where(leave_record.c.rok == year)
        stmt = stmt.order_by(
            func.coalesce(leave_record.c.data_od, leave_record.c.utworzono).desc(),
            leave_record.c.id.desc(),
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().fetchall()
        return [self._from_row(r) for r in rows]

    def get(self, record_id: int) -> Optional[LeaveRecord]:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(leave_record).where(
                    leave_record.c.id == record_id, leave_record.c.user_id == self._user_id)
            ).mappings().fetchone()
        return self._from_row(row) if row else None

    def document(self, record_id: int) -> Optional[bytes]:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(leave_record.c.pdf_path).where(
                    leave_record.c.id == record_id, leave_record.c.user_id == self._user_id)
            ).mappings().fetchone()
        if not row or not row["pdf_path"]:
            return None
        path = self._pdf_dir / row["pdf_path"]
        return path.read_bytes() if path.exists() else None

    def delete_all(self) -> None:
        """§23.4: kasuje wszystkie rekordy użytkownika oraz ich pliki (PDF/załączniki) z dysku."""
        with self._engine.begin() as conn:
            paths = [
                r["pdf_path"]
                for r in conn.execute(
                    select(leave_record.c.pdf_path).where(leave_record.c.user_id == self._user_id)
                ).mappings().fetchall()
                if r["pdf_path"]
            ]
            conn.execute(delete(leave_record).where(leave_record.c.user_id == self._user_id))
        for path in paths:
            (self._pdf_dir / path).unlink(missing_ok=True)

    def save_attachment(
        self, record_id: int, content: bytes, mime: str, name: Optional[str], now: str
    ) -> Optional[LeaveRecord]:
        extension = _EXTENSION.get(mime)
        if extension is None:
            raise ValueError(f"Disallowed attachment type: {mime}")
        with self._engine.begin() as conn:
            row = conn.execute(
                select(leave_record.c.pdf_path).where(
                    leave_record.c.id == record_id, leave_record.c.user_id == self._user_id)
            ).mappings().fetchone()
            if row is None:
                return None
            old = row["pdf_path"]
            new = f"zal_{self._user_id}_{record_id}{extension}"
            (self._pdf_dir / new).write_bytes(content)
            if old and old != new:
                (self._pdf_dir / old).unlink(missing_ok=True)
            conn.execute(
                update(leave_record)
                .where(leave_record.c.id == record_id, leave_record.c.user_id == self._user_id)
                .values(pdf_path=new, zalacznik_mime=mime, zalacznik_nazwa=name, zmieniono=now)
            )
            fresh = conn.execute(
                select(leave_record).where(
                    leave_record.c.id == record_id, leave_record.c.user_id == self._user_id)
            ).mappings().fetchone()
        return self._from_row(fresh) if fresh else None

    def attachment(self, record_id: int) -> Optional[tuple[bytes, str, Optional[str]]]:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(leave_record.c.pdf_path, leave_record.c.zalacznik_mime, leave_record.c.zalacznik_nazwa)
                .where(leave_record.c.id == record_id, leave_record.c.user_id == self._user_id)
            ).mappings().fetchone()
        if not row or not row["pdf_path"]:
            return None
        path = self._pdf_dir / row["pdf_path"]
        if not path.exists():
            return None
        mime = row["zalacznik_mime"] or "application/pdf"
        return path.read_bytes(), mime, row["zalacznik_nazwa"]

    def delete(self, record_id: int) -> bool:
        with self._engine.begin() as conn:
            row = conn.execute(
                select(leave_record.c.pdf_path).where(
                    leave_record.c.id == record_id, leave_record.c.user_id == self._user_id)
            ).mappings().fetchone()
            if row is None:
                return False
            conn.execute(delete(leave_record).where(
                leave_record.c.id == record_id, leave_record.c.user_id == self._user_id))
        if row["pdf_path"]:
            (self._pdf_dir / row["pdf_path"]).unlink(missing_ok=True)
        return True


# --- Entitlement repository (user-scoped) ---------------------------------------------

class SqliteEntitlementRepository(EntitlementRepository):
    """Repozytorium uprawnień (limitów), zawężone do użytkownika."""

    def __init__(self, user_id: int, data_dir: Optional[Path] = None) -> None:
        self._user_id = user_id
        self._engine = _engine(data_dir)
        _metadata.create_all(self._engine)

    def delete_all(self) -> None:
        """§23.4: kasuje wszystkie uprawnienia użytkownika (wszystkie lata)."""
        with self._engine.begin() as conn:
            conn.execute(delete(entitlement).where(entitlement.c.user_id == self._user_id))

    @staticmethod
    def _from_row(row: Any) -> Entitlement:
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
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(entitlement).where(
                    entitlement.c.user_id == self._user_id, entitlement.c.rok == year)
            ).mappings().fetchall()
        return {r["typ"]: self._from_row(r) for r in rows}

    def save(self, ent: Entitlement) -> None:
        values = {
            "user_id": self._user_id,
            "rok": ent.year,
            "typ": ent.leave_type,
            "aktywny": 1 if ent.active else 0,
            "limit_dni": ent.limit_days,
            "limit_godzin": ent.limit_hours,
            "bilans_z_przeniesienia": ent.carried_over,
            "uwagi": ent.notes,
        }
        ins = _dialect_insert(self._engine)(entitlement).values(**values)
        stmt = ins.on_conflict_do_update(
            index_elements=[entitlement.c.user_id, entitlement.c.rok, entitlement.c.typ],
            set_={
                "aktywny": ins.excluded.aktywny,
                "limit_dni": ins.excluded.limit_dni,
                "limit_godzin": ins.excluded.limit_godzin,
                "bilans_z_przeniesienia": ins.excluded.bilans_z_przeniesienia,
                "uwagi": ins.excluded.uwagi,
            },
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)
