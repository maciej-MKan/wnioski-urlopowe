package pl.wnioski.urlopowe.data

import android.content.Context

/** Adres serwera w zwykłych SharedPreferences (to nie sekret — nie wymaga szyfrowania). */
class PrefsServerUrlStore(context: Context) : ServerUrlStore {

    private val prefs = context.applicationContext.getSharedPreferences("server", Context.MODE_PRIVATE)

    override fun get(): String? = prefs.getString("base_url", null)?.takeIf { it.isNotBlank() }

    override fun set(url: String) {
        prefs.edit().putString("base_url", url).apply()
    }
}
