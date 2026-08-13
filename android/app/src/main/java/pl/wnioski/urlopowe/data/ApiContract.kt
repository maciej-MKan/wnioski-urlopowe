package pl.wnioski.urlopowe.data

/**
 * Zakres wersji kontraktu API (`api_version` z `/api/health`), z którym potrafi rozmawiać ten
 * klient. Bumpuj razem z backendowym `API_VERSION`, gdy zmienia się kontrakt. Klient blokuje
 * logowanie, gdy `api_version` serwera wypada poza `MIN_SUPPORTED..MAX_SUPPORTED`.
 *
 * UWAGA: zgodność zależy WYŁĄCZNIE od `api_version`, nie od `versionName`/`APP_VERSION`. Fix
 * (patch, np. 0.5 → 0.5.1) NIE rusza `API_VERSION`, więc różnica ostatniej cyfry wersji między
 * serwerem a tym klientem jest w pełni dozwolona i celowa (patrz backend `app/version.py`).
 */
object ApiContract {
    const val MIN_SUPPORTED = 1
    const val MAX_SUPPORTED = 1

    sealed interface Compatibility {
        /** Wersje zgodne — można się logować. */
        data object Ok : Compatibility

        /** Serwer nowszy niż klient — trzeba zaktualizować aplikację. */
        data class ClientTooOld(val serverApi: Int) : Compatibility

        /** Serwer starszy niż klient (lub nie zgłasza wersji) — trzeba zaktualizować serwer. */
        data class ServerTooOld(val serverApi: Int) : Compatibility
    }

    fun check(serverApiVersion: Int): Compatibility = when {
        serverApiVersion > MAX_SUPPORTED -> Compatibility.ClientTooOld(serverApiVersion)
        serverApiVersion < MIN_SUPPORTED -> Compatibility.ServerTooOld(serverApiVersion)
        else -> Compatibility.Ok
    }

    /** Komunikat dla użytkownika przy niezgodności (`null`, gdy zgodne). */
    fun message(c: Compatibility): String? = when (c) {
        is Compatibility.Ok -> null
        is Compatibility.ClientTooOld ->
            "Ta wersja aplikacji jest zbyt stara dla tego serwera " +
                "(API serwera v${c.serverApi}, aplikacja obsługuje do v$MAX_SUPPORTED). Zaktualizuj aplikację."
        is Compatibility.ServerTooOld ->
            if (c.serverApi <= 0) {
                "Serwer nie zgłasza wersji API — jest zbyt stary dla tej aplikacji. Zaktualizuj serwer."
            } else {
                "Serwer jest zbyt stary dla tej aplikacji " +
                    "(API serwera v${c.serverApi}, aplikacja wymaga min. v$MIN_SUPPORTED). Zaktualizuj serwer."
            }
    }
}
