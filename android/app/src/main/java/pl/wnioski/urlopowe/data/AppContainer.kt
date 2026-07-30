package pl.wnioski.urlopowe.data

import android.content.Context
import pl.wnioski.urlopowe.BuildConfig

/** Korzeń kompozycji zależności (odpowiednik composition root z backendu). */
class AppContainer(context: Context) {
    private val tokenStore: TokenStore = EncryptedTokenStore(context.applicationContext)
    private val api: ApiService = ApiFactory.create(BuildConfig.BASE_URL, tokenStore)

    val auth: AuthRepository = AuthRepository(api, tokenStore)
    val calendar: CalendarRepository = CalendarRepository(api)
    val settings: SettingsRepository = SettingsRepository(api)
    val applications: ApplicationRepository = ApplicationRepository(api)
}
