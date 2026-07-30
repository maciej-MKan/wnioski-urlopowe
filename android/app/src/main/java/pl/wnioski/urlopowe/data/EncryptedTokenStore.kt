package pl.wnioski.urlopowe.data

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/** Token w EncryptedSharedPreferences (szyfrowany kluczem w Android Keystore). */
class EncryptedTokenStore(context: Context) : TokenStore {

    private val prefs by lazy {
        val master = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            "auth",
            master,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    override fun get(): String? = prefs.getString("token", null)

    override fun set(token: String) {
        prefs.edit().putString("token", token).apply()
    }

    override fun clear() {
        prefs.edit().remove("token").apply()
    }
}
