# Wnioski urlopowe — cienkie demo web (GitHub Pages)

Demonstracyjny klient web działający **w całości w przeglądarce** (bez backendu), gotowy do
opublikowania na **GitHub Pages**. Służy do pokazania wyglądu i przepływu aplikacji — **nie** jest
pełną wersją.

> **To jest DEMO.** Dane trzymane są **tylko w pamięci** karty przeglądarki i **znikają po
> odświeżeniu** strony. Baner na górze i strona [`roznice.html`](public/roznice.html) opisują
> różnice względem pełnej aplikacji.

## Czego brakuje vs pełna wersja

| Obszar | Pełna aplikacja | To demo |
|---|---|---|
| Trwałość danych | SQLite na serwerze | **w pamięci**, znika po odświeżeniu |
| PDF | WeasyPrint (HTML+CSS → PDF) | **podgląd HTML + druk** przeglądarki |
| Logowanie / konta | JWT, bcrypt, Google, wielodostęp | brak — **jeden lokalny profil** |
| Synchronizacja | wspólne dane z klientem Android | brak |
| Święta | liczone algorytmem (dowolny rok) | **statyczna lista 2026** |
| Reguły | dni wolne za święto, walidacja ojcowskiego, blokada nakładania | **uproszczone / pominięte** |
| Ustawienia limitów | edytowalne | wartości domyślne (read-only) |

## Co działa
- Kalendarz miesięczny (kolory urlopów, święta, panel dnia: zaakceptuj / odrzuć / usuń, PDF).
- Nowy wniosek z formularza generowanego z rejestru typów (prefill dat i danych profilu).
- Saldo (limit / wykorzystano / zaplanowano / pozostało).
- Edycja lokalnego profilu (dane wspólne).

## Stack
Vanilla **TypeScript + Vite** (bez frameworka). Logika domenowa (dni robocze, święta, saldo) jest
uproszczonym portem z `app/domain/*` pełnej aplikacji. Style bazują na `app/static/common.css`.

## Uruchomienie lokalne
```bash
cd web-demo
npm install
npm run dev      # serwer deweloperski (http://localhost:5173)
npm run build    # produkcyjny build do web-demo/dist/
npm run preview  # podgląd builda
```

## Deploy na GitHub Pages
Robi to workflow `.github/workflows/pages.yml` (build `web-demo/` → publikacja na Pages).
W repo: **Settings → Pages → Source: GitHub Actions**. Po wypchnięciu na `main` demo ląduje pod
`https://<user>.github.io/<repo>/`.

## Uwaga
To osobny, jednorazowy kod pokazowy — **nie** współdzieli logiki z backendem Python. Zmiany reguł w
pełnej aplikacji nie propagują się tu automatycznie.
