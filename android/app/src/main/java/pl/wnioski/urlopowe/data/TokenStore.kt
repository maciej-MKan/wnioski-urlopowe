package pl.wnioski.urlopowe.data

/** Przechowywanie tokenu sesji. Abstrakcja, by w testach JVM podstawić wersję in-memory. */
interface TokenStore {
    fun get(): String?
    fun set(token: String)
    fun clear()
}
