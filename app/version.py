"""Wspólne źródło wersji aplikacji i kontraktu API.

`APP_VERSION` — wersja czytelna dla człowieka `MAJOR.MINOR[.PATCH]` (pokazywana w UI, spójna
z `versionName` klienta Androida, użyta też do cache-bustingu statyków `?v=`). Jest **kosmetyczna**:
NIE bramkuje zgodności klient↔serwer.

`API_VERSION` — całkowita, monotoniczna wersja kontraktu HTTP z klientami (mobilny/web). To ona
JEDYNIE decyduje o zgodności: klient (Android `ApiContract.MIN_SUPPORTED..MAX_SUPPORTED`) odrzuca
serwer, którego `api_version` wypada poza obsługiwanym zakresem.

Reguła wersjonowania (żeby fixy nie robiły rozjazdu klient↔serwer):
- **PATCH** (np. 0.5 → 0.5.1) — poprawka bez zmiany kontraktu HTTP. Podbij TYLKO `APP_VERSION`
  (+ Android `versionName`/`versionCode`). `API_VERSION` bez zmian → mobilny klient z inną
  ostatnią cyfrą zostaje w pełni zgodny. Tak wydajemy fixy.
- **Zmiana kontraktu** (nowe/zmienione pola, endpointy, semantyka) — to NIE jest patch. Podbij
  `API_VERSION` ORAZ Android `ApiContract.MAX_SUPPORTED` (i `MIN_SUPPORTED`, gdy usuwasz stare).
  Nigdy nie zmieniaj kontraktu „po cichu" pod pozorem patcha — to jedyny sposób na rozjazd.
"""
from __future__ import annotations

APP_VERSION = "0.5.1"
API_VERSION = 1
