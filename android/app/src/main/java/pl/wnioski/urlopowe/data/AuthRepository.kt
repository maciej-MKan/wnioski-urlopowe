package pl.wnioski.urlopowe.data

/** Logowanie/sesja: wymienia dane logowania na token i przechowuje go. */
class AuthRepository(
    private val api: ApiService,
    private val tokens: TokenStore,
) {
    fun isLoggedIn(): Boolean = tokens.get() != null

    suspend fun login(username: String, password: String) {
        val response = api.login(username.trim(), password)
        tokens.set(response.accessToken)
    }

    suspend fun register(username: String, password: String) {
        val response = api.register(RegisterRequest(username.trim(), password))
        tokens.set(response.accessToken)  // backend auto-loguje po rejestracji
    }

    /** Przyjmuje token z deep linka (Google OAuth → `pl.wnioski.urlopowe://auth#token=...`). */
    fun acceptToken(token: String) = tokens.set(token)

    suspend fun health(): HealthResponse = api.health()

    suspend fun me(): Me = api.me()

    /** §23.2: zmiana hasła (obecne + nowe). Rzuca HttpException 400 przy błędzie. */
    suspend fun changePassword(current: String, new: String) {
        api.changePassword(mapOf("obecne" to current, "nowe" to new))
    }

    fun logout() = tokens.clear()
}
