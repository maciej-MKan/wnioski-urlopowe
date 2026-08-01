package pl.wnioski.urlopowe.data

import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

/**
 * Adres backendu wskazany przez użytkownika (self-hosting — każdy stawia własny serwer).
 * Abstrakcja, by w testach JVM podstawić wersję in-memory. Przechowuje jedną wartość: bazowy URL.
 */
interface ServerUrlStore {
    /** Zapisany, znormalizowany adres bazowy (z końcowym `/`), lub `null` gdy nie ustawiono. */
    fun get(): String?
    fun set(url: String)
}

/**
 * Sprowadza wpisany adres do postaci bazowego URL: dokłada `http://` gdy brak schematu,
 * zapewnia końcowy `/`. Zwraca `null` dla pustego lub niepoprawnego adresu.
 */
fun normalizeServerUrl(raw: String?): String? {
    val t = raw?.trim().orEmpty()
    if (t.isEmpty()) return null
    val withScheme = if (t.startsWith("http://") || t.startsWith("https://")) t else "http://$t"
    // Walidacja składni (host, port) — odrzuca np. "http://" bez hosta.
    val parsed = withScheme.toHttpUrlOrNull() ?: return null
    if (parsed.host.isBlank()) return null
    return if (withScheme.endsWith("/")) withScheme else "$withScheme/"
}
