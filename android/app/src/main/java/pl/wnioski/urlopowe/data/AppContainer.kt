package pl.wnioski.urlopowe.data

import android.content.Context
import pl.wnioski.urlopowe.BuildConfig

/** Korzeń kompozycji zależności (odpowiednik composition root z backendu). */
class AppContainer(context: Context) {
    private val tokenStore: TokenStore = EncryptedTokenStore(context.applicationContext)

    /** Adres backendu wskazany przez użytkownika; brak = domyślny z BuildConfig (§21). */
    val serverUrl: ServerUrlStore = PrefsServerUrlStore(context.applicationContext)

    private val api: ApiService = ApiFactory.create(
        defaultBaseUrl = BuildConfig.BASE_URL,
        baseUrlProvider = { serverUrl.get() ?: BuildConfig.BASE_URL },
        tokenStore = tokenStore,
    )

    val auth: AuthRepository = AuthRepository(api, tokenStore)
    val calendar: CalendarRepository = CalendarRepository(api)
    val settings: SettingsRepository = SettingsRepository(api)
    val applications: ApplicationRepository = ApplicationRepository(api)
}
