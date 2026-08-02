"""Wspólne źródło wersji aplikacji i kontraktu API.

`APP_VERSION` — wersja czytelna dla człowieka (pokazywana w UI, spójna z `versionName`
klienta Androida). `API_VERSION` — całkowita, monotoniczna wersja kontraktu HTTP z klientami
(mobilny/web). Bumpuj `API_VERSION` przy KAŻDEJ niekompatybilnej zmianie kontraktu; klient
odrzuca serwer, którego `api_version` wypada poza obsługiwanym przez niego zakresem.
"""
from __future__ import annotations

APP_VERSION = "0.4"
API_VERSION = 1
