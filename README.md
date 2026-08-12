# Generator wniosków urlopowych

Prosta aplikacja na użytek własny do generowania wniosków urlopowych w formacie **PDF**,
gotowych do podpisania **Profilem Zaufanym** (gov.pl → „Podpisz dokument elektronicznie").

Obsługiwane wnioski:

| Wniosek | Podstawa prawna |
|---|---|
| Urlop wypoczynkowy | art. 152 i 163 Kodeksu pracy |
| Urlop ojcowski | art. 182³ Kodeksu pracy (do 2 tygodni, do ukończenia przez dziecko 12 m-ca życia) |
| Opieka nad dzieckiem do 14 lat | art. 188 Kodeksu pracy (2 dni albo 16 godzin rocznie) |

## Stos technologiczny

- **Backend:** Python + FastAPI, generowanie PDF przez WeasyPrint (HTML+CSS → PDF, pełne wsparcie polskich znaków).
- **Frontend:** vanilla JS, cztery strony z nawigacją — **kalendarz** (`/`, strona główna),
  **generator** (`/nowy`), **saldo** (`/saldo`, podgląd bilansu) i **ustawienia** (`/ustawienia`, profil + limity). Wspólne helpery i style wydzielone do
  `static/common.js` (skrót `$`, klient `api`, narzędzia dat) i `static/common.css` (tokeny,
  nawigacja, modale), serwowanych z montażu `/static`. W generatorze zakładki i pola formularza
  są **generowane z rejestru typów** (`/api/typy`) — nie ma kodu per-typ w HTML; dane wspólne
  (imię i nazwisko, stanowisko, pracodawca…) zapisywane jako **profil użytkownika w bazie**
  (`/api/profil`) i automatycznie wstawiane do kolejnych wniosków — wspólne z klientem mobilnym.
  Kliknięcie w kalendarzu zaznacza okres → dialog „Dodaj ręcznie” / „Utwórz wniosek” z prefill dat.
  Kalendarz (widok miesięczny/roczny) koloruje urlopy wg rejestru, nakłada święta i weekendy,
  wyróżnia statusy rekordów, a w panelu szczegółów pozwala oznaczać status, korygować okres
  (z powodem), usuwać oraz **dodawać urlopy odbyte ręcznie** (z możliwością **dopięcia skanu
  PDF/JPG**). Zarówno zakładki generatora, jak i wybór typu przy dodawaniu ręcznym pokazują
  tylko rodzaje urlopu **przysługujące w danym roku** wg zakładki Ustawienia.
- **Klient mobilny (Android, `android/`):** natywna aplikacja **Kotlin + Jetpack Compose**
  korzystająca z tego samego API (Retrofit + kotlinx.serialization; token trzymany w
  `EncryptedSharedPreferences`). Funkcje: logowanie/rejestracja hasłem (+ opcjonalnie Google),
  **kalendarz** miesięczny z panelem dnia i akcjami (zaakceptuj/odrzuć/usuń, pobranie PDF),
  **zaznaczanie okresu** kliknięciami, **nowy wniosek** z dynamicznego rejestru (wraz z pytaniem
  o dni wolne za święto), **dodawanie ręczne**, **saldo + edycja limitów** oraz **profil**
  (te same dane wspólne co web). Budowanie i testy: patrz [`android/`](android/).
- **Rejestr typów (`app/domain/leave_type.py`):** jedyne źródło prawdy o rodzajach urlopu.
  Walidacja, generator dokumentu i frontend czytają wyłącznie stąd. Dodanie nowego rodzaju
  urlopu = dodanie deskryptora `RodzajUrlopu` (+ opcjonalnie szablon HTML w `app/templates/`),
  bez zmian w logice.
- **Trwałość (`app/infrastructure/persistence.py`):** SQLite na wolumenie Dockera. Każde
  wygenerowanie PDF zapisuje rekord urlopu (`leave_record`, status `do_akceptacji`).
  Zapis jest idempotentny — ponowne pobranie tej samej treści nie tworzy duplikatu.
  Baza i PDF-y leżą w katalogu `WNIOSKI_DATA_DIR` (w kontenerze `/srv/data`, wolumen
  `wnioski-dane`).
- **Architektura:** warstwy DDD (domena → aplikacja → infrastruktura → interfejs) —
  patrz [Architektura](#architektura). **Testy:** pytest — patrz [Testy](#testy).
- **Uruchomienie:** Docker.

## Uruchomienie

Dwa niezależne środowiska (osobne bazy/wolumeny — testy nie ruszają danych produkcyjnych):

```bash
# PRODUKCJA — port 8137, wolumen wnioski-urlopowe_wnioski-dane
docker compose up -d --build

# DEV / TEST — port 8138, osobny wolumen wnioski-dev_wnioski-dane-dev
docker compose -f docker-compose.dev.yml up -d --build
```

- **Prod:** http://localhost:8137 — realne dane. **Dev/test:** http://localhost:8138 — piaskownica
  na testy manualne (pusta, odseparowana baza). Na środowisku nieprodukcyjnym w nawigacji świeci
  pomarańczowy badge **`DEV`** (z pola `srodowisko` w `/api/health`), by nie pomylić środowisk.
- Zatrzymanie: `docker compose down` (prod) / `docker compose -f docker-compose.dev.yml down` (dev).

Strona główna (`/`) to **kalendarz**; generator wniosków jest pod **`/nowy`**.

### Konta i logowanie

Aplikacja jest **wielodostępna** — każdy użytkownik widzi wyłącznie swoje dane (rekordy,
uprawnienia, ustawienia). Logowanie tokenem (OAuth2 password → **JWT bearer**), hasła hashowane
bcrypt. Endpointy `/api/*` (poza `/api/health`, `/api/token`, `/api/register`) wymagają tokenu.

- **Pierwsze uruchomienie:** wejdź na stronę i **załóż konto** (formularz logowania → „Załóż konto”).
- **Migracja starej (jednoosobowej) bazy:** przy pierwszym starcie po aktualizacji istniejące dane
  zostają przypisane do konta **`owner`**. Hasło ustaw przez `WNIOSKI_OWNER_PASSWORD` (jeśli puste —
  zostanie wygenerowane i **wypisane w logach**: `docker compose logs`).

Zmienne środowiskowe (opcjonalne):

| Zmienna | Znaczenie | Domyślnie |
|---|---|---|
| `WNIOSKI_SECRET` | sekret podpisu JWT | generowany i zapisany w `secret.key` w katalogu danych |
| `WNIOSKI_OWNER` / `WNIOSKI_OWNER_PASSWORD` | konto właściciela przy migracji starej bazy | `owner` / hasło losowe (w logach) |
| `WNIOSKI_ALLOW_REGISTER` | czy dozwolona rejestracja (`0` wyłącza) | `1` |
| `WNIOSKI_NO_LOGIN` | **tryb bez logowania** dla instancji jednoużytkownikowej (`1` włącza) | `0` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | włączają **logowanie przez Google** | brak → wyłączone |

**Tryb bez logowania (opcjonalny).** `WNIOSKI_NO_LOGIN=1` przełącza instancję w tryb
jednoużytkownikowy bez ekranu logowania — wygodny, gdy każdy hostuje backend tylko dla siebie:

- gdy w bazie jest **dokładnie jedno** konto, backend uwierzytelnia je automatycznie przy każdym
  żądaniu (token pomijany), a web i klient mobilny wchodzą od razu, bez logowania;
- gdy kont **nie ma**, aplikacja wymusza jednorazowe **utworzenie jedynego konta** (rejestracja
  dozwolona tylko wtedy);
- gdy kont jest **więcej niż jedno**, flaga jest nieaktywna (niejednoznaczne) i obowiązuje zwykłe
  logowanie tokenem.

Stan trybu zgłasza `/api/health` (`bez_logowania`, `wymaga_konta`); w tym trybie znika też
„Wyloguj”. Klient mobilny sprawdza dodatkowo zgodność wersji API (`api_version` z `/api/health`)
i blokuje logowanie, gdy aplikacja i serwer są niezgodne.

**Logowanie przez Google (opcjonalne).** Ustaw `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` (klient
OAuth z Google Cloud Console), a w konfiguracji klienta dodaj **Authorized redirect URI**:
`http://localhost:8138/api/auth/google/callback` (dev) / `…:8137/…` (prod). Wtedy w oknie
logowania pojawia się „Zaloguj przez Google”. Konto Google jest łączone po `sub` (bez hasła),
obok kont lokalnych. Bez tych zmiennych przycisk się nie pokazuje i nic się nie zmienia. Ten sam
przepływ obsługuje **klient mobilny** — po zalogowaniu backend wraca deep linkiem
`pl.wnioski.urlopowe://auth` z tokenem (parametr `?native=1`).

**Zarządzanie kontem.** W **Ustawieniach** (web i mobile) można:
- **zmienić hasło** (podając obecne) — `POST /api/haslo`;
- **usunąć konto** wraz ze wszystkimi danymi (wnioski, limity, profil, pliki PDF/załączniki) —
  `DELETE /api/konto`, nieodwracalne, z dwustopniowym potwierdzeniem.

**Reset zapomnianego hasła (self-host).** Bez poczty — administrator serwera resetuje hasło z CLI
(pominięcie hasła → zostanie wygenerowane i wypisane):

```bash
docker compose exec wnioski python -m app reset-haslo <username> [<nowe-haslo>]
```

**Bezpieczeństwo danych „at-rest”.** Baza (SQLite) i pliki PDF/załączniki leżą w wolumenie
`WNIOSKI_DATA_DIR`. Hasła są hashowane (bcrypt), ale reszta danych jest **jawna** dla kogoś z
dostępem do hosta/wolumenu. Aby zaszyfrować dane w spoczynku, **postaw wolumen na zaszyfrowanym
nośniku (LUKS/dm-crypt)** — transparentne dla aplikacji, chroni całość (baza + pliki):

```bash
cryptsetup luksFormat /dev/sdX
cryptsetup open /dev/sdX wnioski-crypt
mkfs.ext4 /dev/mapper/wnioski-crypt
mount /dev/mapper/wnioski-crypt /srv/wnioski-data   # montujemy tu WNIOSKI_DATA_DIR
```

Po restarcie serwera wolumen trzeba odblokować (`cryptsetup open` + `mount`) przed startem kontenera.
Migracja bazy na **PostgreSQL** (poświadczenia w env) jest planowana osobno (§23.1 w planie); Postgres
nie zastępuje szyfrowania at-rest — nadal wymaga LUKS/szyfrowania nośnika po stronie serwera bazy.

## Jak używać

1. Wypełnij **dane wspólne** (miejscowość, data, imię i nazwisko, pracodawca) — możesz je zapisać
   jako **profil** (przycisk pod formularzem lub w Ustawieniach), by wstawiały się automatycznie.
2. Wybierz zakładkę z rodzajem wniosku i uzupełnij pola szczegółowe.
3. Kliknij **Podgląd**, aby sprawdzić treść, albo **Dodaj do kalendarza** / **Dodaj do kalendarza i pobierz**.
   Dla urlopu wypoczynkowego, gdy w danym roku przysługują niewykorzystane **dni wolne za święto
   (sobota)**, aplikacja zapyta, czy część okresu przeznaczyć na taki dzień — powstaną wtedy **dwa
   osobne wnioski** (urlop + dzień wolny), bo mają różną podstawę prawną.
4. Wejdź na [gov.pl → Podpisz dokument elektronicznie](https://www.gov.pl/web/gov/podpisz-dokument-elektronicznie-wykorzystaj-podpis-zaufany),
   wgraj pobrany PDF i podpisz Profilem Zaufanym. Wynikowy plik (`...-podpisany.pdf` / XAdES) prześlij do kadr.

## API

| Metoda | Ścieżka | Opis |
|---|---|---|
| `GET` | `/` | kalendarz urlopów (strona główna; alias `/kalendarz`) |
| `GET` | `/nowy` | generator wniosków (interfejs) |
| `GET` | `/saldo` | podgląd bilansu wykorzystania (tylko odczyt) |
| `GET` | `/ustawienia` | profil + ustawienia limitów |
| `GET` | `/api/typy` | rejestr typów wniosków (zakładki + pola); `?rok=RRRR` dokłada flagę `aktywny` per typ wg Ustawień |
| `GET` | `/api/swieta?rok=RRRR` | dni ustawowo wolne od pracy w danym roku |
| `GET`/`PUT` | `/api/ustawienia?rok=RRRR` | odczyt / zapis limitów + przełącznik `jednozmianowy` (dni wolne za święta w sobotę) |
| `GET` | `/api/bilans?rok=RRRR` | bilans wykorzystania urlopu (limit/wykorzystano/pozostało; z wyróżnioną pozycją dni wolnych za święta w sobotę) |
| `POST` | `/api/token` | logowanie (OAuth2 password, form `username`/`password`) → `access_token` (JWT) |
| `POST` | `/api/register` | rejestracja konta (JSON `username`/`password`) → auto-login (token) |
| `GET` | `/api/me` | zalogowany użytkownik (`id`, `username`) |
| `GET`/`PUT` | `/api/profil` | profil użytkownika — domyślne dane wspólne wstawiane do wniosków (web + mobile) |
| `GET` | `/api/auth/google/login` `…/callback` | logowanie przez Google (OIDC; aktywne, gdy ustawiono `GOOGLE_CLIENT_ID/SECRET`; `?native=1` wraca deep linkiem do klienta Android) |
| `POST` | `/api/generuj` | zwraca PDF (`application/pdf`) i zapisuje rekord (nagłówek `X-Rekord-Id`) |
| `POST` | `/api/wnioski` | tworzy i zapisuje 1–2 wnioski (`dni_za_swieto` dzieli urlop na wypoczynkowy + dzień wolny za święto); zwraca id + nazwy plików |
| `GET` | `/api/dni-robocze?data_od&data_do` | liczba dni roboczych w zakresie (do dialogu o dni wolne za święto) |
| `POST` | `/api/podglad` | zwraca podgląd HTML (bez zapisu) |
| `GET` | `/api/rekordy` | lista zapisanych rekordów urlopu (opcjonalnie `?rok=RRRR`) |
| `POST` | `/api/rekordy/reczny` | dodaje urlop odbyty spoza aplikacji (bez PDF) |
| `POST` | `/api/rekordy/przelicz-wymiary` | wstecznie wylicza dni robocze / godziny w rekordach |
| `PATCH` | `/api/rekordy/{id}/status` | oznacza rekord (zaakceptowany/odrzucony/do akceptacji) |
| `PATCH` | `/api/rekordy/{id}/okres` | korekta okresu z powodem (przelicza wymiar, audyt) |
| `DELETE` | `/api/rekordy/{id}` | usuwa rekord i jego plik (PDF/załącznik) |
| `GET` | `/api/rekordy/{id}/pdf` | zapisany PDF danego rekordu (wnioski) |
| `POST` | `/api/rekordy/{id}/zalacznik` | dopina plik PDF/JPG do rekordu ręcznego (multipart, ≤ 5 MB) |
| `GET` | `/api/rekordy/{id}/zalacznik` | serwuje dopięty plik z właściwym typem MIME |
| `GET` | `/api/health` | health-check |
| `GET` | `/api/docs` | dokumentacja OpenAPI (Swagger) |

Przykład:

```bash
curl -X POST http://localhost:8000/api/generuj \
  -H "Content-Type: application/json" \
  -d '{"typ":"wypoczynkowy","miejscowosc":"Warszawa","data":"2026-07-24",
       "imie_nazwisko":"Jan Kowalski","pracodawca":"Firma Sp. z o.o.",
       "data_od":"2026-08-04","data_do":"2026-08-08"}' --output wniosek.pdf
```

## Architektura

Aplikacja jest zorganizowana w warstwy w duchu **DDD** (Domain-Driven Design) — celowo
„na wyrost" jak na jej rozmiar, jako czytelny przykład edukacyjny. Zależności wskazują
zawsze do wewnątrz: warstwy zewnętrzne znają wewnętrzne, nigdy odwrotnie.

**Język kodu:** identyfikatory, docstringi i komentarze są **po angielsku**; po polsku
pozostają wyłącznie **teksty widoczne dla użytkownika** (UI, szablony PDF, nazwy typów,
etykiety, nazwy świąt) oraz **kontrakt danych/wire** — wartości enumów, klucze JSON i nazwy
kolumn SQLite (np. `class Status(str, Enum): PENDING = "do_akceptacji"`). Serializatory i
repozytoria SQLite są mostem między angielskimi atrybutami a polskimi kluczami/kolumnami.

```
app/
├─ domain/          # Domena — czysta logika, zero zależności od frameworków
│  ├─ values.py       # value objects i enumy (DateRange, Status, Source, Pool, Unit)
│  ├─ leave_record.py # agregat LeaveRecord (factory, przejścia statusów, korekta, hash)
│  ├─ leave_type.py   # rejestr LeaveType/LeaveTypeRegistry + walidacja payloadu
│  ├─ holidays.py     # dni ustawowo wolne w PL (algorytm paschalny, święta ruchome)
│  ├─ working_days.py # liczenie dni roboczych (pon–pt minus święta)
│  ├─ leave_amount.py # wyliczanie wymiaru wg jednostki typu (dni robocze/kalendarzowe/godziny)
│  ├─ entitlement.py  # Entitlement — przysługujący limit per rok/typ
│  ├─ balance.py      # bilans: limit vs wykorzystano vs zaplanowano vs pozostało
│  ├─ ports.py        # porty: LeaveRecordRepository (ABC), DocumentGenerator (Protocol)
│  └─ errors.py       # wyjątki domenowe
├─ application/     # Aplikacja — przypadki użycia (LeaveService)
├─ infrastructure/  # Infrastruktura — adaptery portów
│  ├─ persistence.py  # SqliteLeaveRecordRepository, SqliteEntitlementRepository
│  ├─ templates.py    # JinjaTemplates (HTML, bez WeasyPrint)
│  ├─ pdf.py          # WeasyPrintDocumentGenerator (jedyny import weasyprint)
│  └─ formatting.py   # formatowanie dat po polsku
├─ interface/       # Interfejs — router FastAPI + serializatory JSON
├─ composition.py   # korzeń kompozycji (create_app) — tu warstwy są zszywane
└─ main.py          # punkt wejścia: app = create_app()
```

Kluczowa decyzja: **WeasyPrint jest odizolowany za portem `DocumentGenerator`** i
importowany leniwie tylko w produkcyjnym montażu. Dzięki temu domena, aplikacja i większość
testów działają bez ciężkich bibliotek systemowych (Pango/Cairo). W testach porty
podmieniamy na atrapy przez wstrzykiwanie zależności do `create_app(service=...)`.

## Testy

Pełna piramida testów w `pytest` (jednostkowe domeny/aplikacji, integracyjne repozytorium
SQLite i szablonów Jinja, testy API przez `TestClient`). Test realnego WeasyPrint jest
pomijany, gdy biblioteka nie jest dostępna (uruchamia się w obrazie Dockera).

```bash
# Lokalnie (bez WeasyPrint — jeden test pominięty):
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest

# Pełny bieg w obrazie (z WeasyPrint):
docker compose build
docker run --rm -v "$PWD":/work -w /work -e WNIOSKI_DATA_DIR=/tmp/testdata \
  --entrypoint sh wnioski-urlopowe-wnioski \
  -c "pip install -q pytest httpx && python -m pytest"
```

## Uwagi prawne

Szablony mają charakter pomocniczy i odzwierciedlają typowy układ wniosków oraz aktualne
podstawy prawne (stan na 2024/2025). Twój pracodawca może wymagać własnego wzoru lub
dodatkowych oświadczeń/załączników — w razie potrzeby dostosuj szablony w `app/templates/`.

Zmiana treści dokumentów = edycja plików `app/templates/*.html` (składnia Jinja2 + CSS).

## Licencja

Projekt udostępniony na licencji **MIT** — patrz [`LICENSE`](LICENSE).
