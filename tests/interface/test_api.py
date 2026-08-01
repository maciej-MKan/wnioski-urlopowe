"""API layer tests (FastAPI TestClient) on service doubles.

The wire contract stays Polish (route paths, JSON keys, enum values), so assertions use
Polish keys; only the test identifiers are English.
"""
from __future__ import annotations

ANNUAL = {
    "typ": "wypoczynkowy",
    "imie_nazwisko": "Jan Kowalski",
    "data_od": "2026-08-04",
    "data_do": "2026-08-08",
}


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert "srodowisko" in body  # prod/dev — do badge w UI


def test_health_reports_version(client):
    from app.version import API_VERSION, APP_VERSION

    body = client.get("/api/health").json()
    assert body["wersja"] == APP_VERSION
    assert body["api_version"] == API_VERSION
    assert isinstance(body["api_version"], int)  # klient mobilny porównuje jako liczbę


def test_home_serves_calendar(client):
    # Kalendarz jest stroną główną (§ kalendarz jako główny komponent).
    r = client.get("/")
    assert r.status_code == 200
    assert "Kalendarz urlopów" in r.text


def test_generator_moved_to_nowy(client):
    r = client.get("/nowy")
    assert r.status_code == 200
    assert "Generator wniosków urlopowych" in r.text


def test_types_structure(client):
    data = client.get("/api/typy").json()
    generatable = [t["id"] for t in data["typy"] if t["generowalny"]]
    assert generatable == ["wypoczynkowy", "ojcowski", "opieka"]
    weekend = next(t for t in data["typy"] if t["id"] == "wolne_za_swieta")
    assert weekend["generowalny"] is False
    assert any(p["name"] == "miejscowosc" for p in data["wspolne"])


def test_types_without_year_all_active(client):
    # Without ?rok — backward compatible: all types marked active.
    types = client.get("/api/typy").json()["typy"]
    assert all(t["aktywny"] for t in types)


def test_types_with_year_default_only_annual(client):
    types = {t["id"]: t for t in client.get("/api/typy?rok=2026").json()["typy"]}
    assert types["wypoczynkowy"]["aktywny"] is True
    assert types["ojcowski"]["aktywny"] is False
    assert types["opieka"]["aktywny"] is False


def test_types_with_year_reflects_settings(client):
    client.put("/api/ustawienia?rok=2026", json={"ojcowski": {"aktywny": True}})
    types = {t["id"]: t for t in client.get("/api/typy?rok=2026").json()["typy"]}
    assert types["ojcowski"]["aktywny"] is True


def test_preview_returns_html(client):
    r = client.post("/api/podglad", json=ANNUAL)
    assert r.status_code == 200
    assert "wypoczynkowy" in r.text


def test_preview_unknown_type_400(client):
    assert client.post("/api/podglad", json={"typ": "nieistnieje"}).status_code == 400


def test_generate_returns_pdf_and_id(client):
    r = client.post("/api/generuj", json=ANNUAL)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["x-rekord-id"] == "1"


def test_generate_idempotent(client):
    r1 = client.post("/api/generuj", json=ANNUAL)
    r2 = client.post("/api/generuj", json=ANNUAL)
    assert r1.headers["x-rekord-id"] == r2.headers["x-rekord-id"]


def test_generate_unknown_type_400(client):
    assert client.post("/api/generuj", json={"typ": "nieistnieje"}).status_code == 400


def test_wnioski_single(client):
    r = client.post("/api/wnioski", json=ANNUAL)
    assert r.status_code == 200
    wnioski = r.json()["wnioski"]
    assert len(wnioski) == 1
    assert wnioski[0]["typ"] == "wypoczynkowy"
    assert wnioski[0]["nazwa_pliku"].endswith(".pdf")


def test_wnioski_split_creates_two(client):
    payload = {"typ": "wypoczynkowy", "data_od": "2026-08-10", "data_do": "2026-08-21", "dni_za_swieto": 1}
    wnioski = client.post("/api/wnioski", json=payload).json()["wnioski"]
    types = {w["typ"] for w in wnioski}
    assert types == {"wypoczynkowy", "wolne_za_swieta"}
    # both PDFs are retrievable
    for w in wnioski:
        assert client.get(f"/api/rekordy/{w['id']}/pdf").content.startswith(b"%PDF")


def test_dni_robocze_endpoint(client):
    r = client.get("/api/dni-robocze?data_od=2026-08-04&data_do=2026-08-08")
    assert r.status_code == 200
    assert r.json() == {"dni_robocze": 4}


def test_records_list_grows(client):
    assert client.get("/api/rekordy").json() == []
    client.post("/api/generuj", json=ANNUAL)
    records = client.get("/api/rekordy").json()
    assert len(records) == 1
    assert records[0]["typ"] == "wypoczynkowy"
    assert records[0]["status"] == "do_akceptacji"


def test_record_pdf_served(client):
    rid = client.post("/api/generuj", json=ANNUAL).headers["x-rekord-id"]
    r = client.get(f"/api/rekordy/{rid}/pdf")
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


def test_record_pdf_404_for_nonexistent(client):
    assert client.get("/api/rekordy/999/pdf").status_code == 404


def test_generate_saves_amount(client):
    client.post("/api/generuj", json=ANNUAL)
    record = client.get("/api/rekordy").json()[0]
    assert record["dni_robocze"] == 4  # 04–08.08.2026 without Saturday


def test_calendar_page_served(client):
    r = client.get("/kalendarz")
    assert r.status_code == 200
    assert "Kalendarz urlopów" in r.text


def test_holidays_endpoint(client):
    r = client.get("/api/swieta?rok=2026")
    assert r.status_code == 200
    data = r.json()
    assert {"data": "2026-01-01", "nazwa": "Nowy Rok"} in data
    assert any(s["data"] == "2026-06-04" for s in data)  # Corpus Christi


def test_holidays_endpoint_requires_year(client):
    assert client.get("/api/swieta").status_code == 422


def test_settings_get_default(client):
    data = client.get("/api/ustawienia?rok=2026").json()
    ent = {u["typ"]: u for u in data["uprawnienia"]}
    assert ent["wypoczynkowy"]["limit_dni"] == 26
    assert ent["wypoczynkowy"]["aktywny"] is True


def test_settings_put_and_balance(client):
    client.put("/api/ustawienia?rok=2026", json={
        "wypoczynkowy": {"limit_dni": "26", "bilans_z_przeniesienia": "0"},
        "opieka": {"aktywny": True},
    })
    ent = {u["typ"]: u for u in client.get("/api/ustawienia?rok=2026").json()["uprawnienia"]}
    assert ent["opieka"]["aktywny"] is True

    balance = client.get("/api/bilans?rok=2026").json()
    assert any(p["etykieta"] == "Urlop wypoczynkowy (bieżący)" for p in balance)
    assert any("Opieka" in p["etykieta"] for p in balance)


def test_settings_returns_single_shift_flag(client):
    data = client.get("/api/ustawienia?rok=2025").json()
    assert data["jednozmianowy"] is True


def test_balance_has_saturday_holiday_item(client):
    # §16.1: per-month highlighted lines, each with a `miesiac` (month) field.
    balance = client.get("/api/bilans?rok=2025").json()
    weekend = [p for p in balance if p.get("krotki_termin")]
    assert weekend
    assert {p["miesiac"] for p in weekend} >= {5, 11}  # May and November 2025
    assert all("Dni wolne za święto" in p["etykieta"] for p in weekend)


def test_toggle_single_shift_off(client):
    client.put("/api/ustawienia?rok=2025", json={"wolne_za_swieta": {"aktywny": False}})
    data = client.get("/api/ustawienia?rok=2025").json()
    assert data["jednozmianowy"] is False
    balance = client.get("/api/bilans?rok=2025").json()
    assert not any(p.get("krotki_termin") for p in balance)


def test_generate_overdue_sets_pool(client):
    # §16.3: a settlement year earlier than the leave's year charges the overdue pool.
    client.post("/api/generuj", json={**ANNUAL, "rok_rozliczenia": "2025"})
    record = client.get("/api/rekordy").json()[0]
    assert record["za_okres"] == "zalegly"


def test_settings_page_served(client):
    r = client.get("/ustawienia")
    assert r.status_code == 200
    assert "Mój profil" in r.text
    assert "Bilans wykorzystania" not in r.text  # bilans wydzielony do /saldo


def test_balance_page_served(client):
    r = client.get("/saldo")
    assert r.status_code == 200
    assert "Bilans wykorzystania" in r.text


def _new_record_id(client):
    return client.post("/api/generuj", json=ANNUAL).headers["x-rekord-id"]


def test_patch_status(client):
    rid = _new_record_id(client)
    r = client.patch(f"/api/rekordy/{rid}/status", json={"status": "zaakceptowany"})
    assert r.status_code == 200
    assert r.json()["status"] == "zaakceptowany"


def test_patch_status_unknown_400(client):
    rid = _new_record_id(client)
    assert client.patch(f"/api/rekordy/{rid}/status", json={"status": "kosmos"}).status_code == 400


def test_patch_status_no_record_404(client):
    assert client.patch("/api/rekordy/999/status", json={"status": "zaakceptowany"}).status_code == 404


def test_patch_period(client):
    rid = _new_record_id(client)
    r = client.patch(f"/api/rekordy/{rid}/okres",
                     json={"data_od": "2026-08-04", "data_do": "2026-08-05", "powod": "L4"})
    assert r.status_code == 200
    assert r.json()["data_do"] == "2026-08-05"
    assert r.json()["dni_robocze"] == 2


def test_patch_period_without_reason_400(client):
    rid = _new_record_id(client)
    r = client.patch(f"/api/rekordy/{rid}/okres", json={"data_od": "2026-08-04", "data_do": "2026-08-05", "powod": ""})
    assert r.status_code == 400


def test_add_manual(client):
    r = client.post("/api/rekordy/reczny", json={"typ": "wypoczynkowy", "data_od": "2026-05-04", "data_do": "2026-05-05"})
    assert r.status_code == 200
    assert r.json()["zrodlo"] == "reczny"
    assert r.json()["status"] == "zaakceptowany"


def _manual_id(client):
    return client.post(
        "/api/rekordy/reczny", json={"typ": "wypoczynkowy", "data_od": "2026-05-04", "data_do": "2026-05-05"}
    ).json()["id"]


def test_attachment_upload_pdf(client):
    rid = _manual_id(client)
    r = client.post(f"/api/rekordy/{rid}/zalacznik",
                    files={"plik": ("skan.pdf", b"%PDF-1.4 tresc", "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert body["ma_zalacznik"] is True
    assert body["zalacznik_mime"] == "application/pdf"
    assert body["zalacznik_nazwa"] == "skan.pdf"


def test_attachment_upload_jpg_and_serving(client):
    rid = _manual_id(client)
    jpg = b"\xff\xd8\xff\xe0 udawany-jpeg"
    client.post(f"/api/rekordy/{rid}/zalacznik", files={"plik": ("foto.jpg", jpg, "image/jpeg")})
    r = client.get(f"/api/rekordy/{rid}/zalacznik")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content == jpg


def test_attachment_rejects_disallowed_type(client):
    rid = _manual_id(client)
    r = client.post(f"/api/rekordy/{rid}/zalacznik",
                    files={"plik": ("z.txt", b"zwykly tekst", "text/plain")})
    assert r.status_code == 415


def test_attachment_upload_no_record_404(client):
    r = client.post("/api/rekordy/999/zalacznik",
                    files={"plik": ("skan.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 404


def test_attachment_get_missing_404(client):
    rid = _manual_id(client)
    assert client.get(f"/api/rekordy/{rid}/zalacznik").status_code == 404


def test_attachment_too_large_413(client, monkeypatch):
    import app.interface.api as api_mod
    monkeypatch.setattr(api_mod, "_ATTACHMENT_MAX", 8)
    rid = _manual_id(client)
    r = client.post(f"/api/rekordy/{rid}/zalacznik",
                    files={"plik": ("skan.pdf", b"%PDF-1.4 duzo tresci", "application/pdf")})
    assert r.status_code == 413


def test_delete_record(client):
    rid = _new_record_id(client)
    assert client.delete(f"/api/rekordy/{rid}").status_code == 204
    assert client.get("/api/rekordy").json() == []


def test_delete_no_record_404(client):
    assert client.delete("/api/rekordy/999").status_code == 404


def test_recompute_amounts_endpoint(client):
    client.post("/api/generuj", json=ANNUAL)
    r = client.post("/api/rekordy/przelicz-wymiary")
    assert r.status_code == 200
    # The record already has an amount from saving, so the backfill changes nothing.
    assert r.json() == {"zaktualizowano": 0}
