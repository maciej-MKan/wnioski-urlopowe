package pl.wnioski.urlopowe.data

import kotlinx.serialization.json.Json
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

/** Buduje `ApiService` (Retrofit + OkHttp), dokładając bearer token z `TokenStore`. */
object ApiFactory {

    val json: Json = Json { ignoreUnknownKeys = true }

    /**
     * @param defaultBaseUrl adres-placeholder wymagany przez Retrofit (fallback z BuildConfig).
     * @param baseUrlProvider bieżący adres serwera (konfigurowalny przez użytkownika, §21) —
     *   interceptor przepisuje schemat/host/port każdego żądania na ten adres.
     * @param onUnauthorized wołane (z wątku sieciowego) po 401 z wygasłą/odrzuconą sesją — token jest
     *   wtedy już usunięty, a UI ma wrócić na ekran logowania.
     */
    fun create(
        defaultBaseUrl: String,
        baseUrlProvider: () -> String,
        tokenStore: TokenStore,
        onUnauthorized: () -> Unit = {},
    ): ApiService {
        // §21: podmiana hosta na adres wskazany przez użytkownika (ścieżki API są bezwzględne: /api/...).
        val hostSwap = Interceptor { chain ->
            val request = chain.request()
            val url = swapHost(request.url, baseUrlProvider())
            val next = if (url != null) request.newBuilder().url(url).build() else request
            chain.proceed(next)
        }
        val auth = Interceptor { chain ->
            val builder = chain.request().newBuilder()
            tokenStore.get()?.let { builder.header("Authorization", "Bearer $it") }
            chain.proceed(builder.build())
        }
        val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC }
        val client = OkHttpClient.Builder()
            .addInterceptor(hostSwap)
            .addInterceptor(unauthorizedInterceptor(tokenStore, onUnauthorized))
            .addInterceptor(auth)
            .addInterceptor(logging)
            .build()
        return Retrofit.Builder()
            .baseUrl(defaultBaseUrl)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(ApiService::class.java)
    }
}

/**
 * Zwraca `original` z podmienionym schematem/hostem/portem na te z `targetBaseUrl`
 * (ścieżka i query bez zmian). `null`, gdy `targetBaseUrl` nie jest poprawnym adresem.
 */
internal fun swapHost(original: HttpUrl, targetBaseUrl: String): HttpUrl? {
    val target = targetBaseUrl.toHttpUrlOrNull() ?: return null
    return original.newBuilder()
        .scheme(target.scheme)
        .host(target.host)
        .port(target.port)
        .build()
}

/** Ścieżki, w których 401 oznacza zły login/hasło, a nie wygasłą sesję. */
private val PUBLIC_AUTH_PATHS = setOf("/api/token", "/api/register")

/**
 * Wygasła/odrzucona sesja: odpowiedź 401 na żądanie z tokenem → usuwa token i wywołuje [onUnauthorized].
 * Pomija logowanie/rejestrację (tam 401 = zły login). Token jest usuwany tylko, gdy nadal jest tym samym,
 * z którym wysłano żądanie — spóźniona odpowiedź 401 na stary token nie może wylogować świeżo zalogowanego
 * użytkownika. Backend wystawia jeden token na 30 dni (bez refresh tokena), więc jedyną reakcją jest
 * ponowne logowanie.
 */
internal fun unauthorizedInterceptor(tokenStore: TokenStore, onUnauthorized: () -> Unit): Interceptor =
    Interceptor { chain ->
        val sentToken = tokenStore.get()
        val response = chain.proceed(chain.request())
        if (response.code == 401 && chain.request().url.encodedPath !in PUBLIC_AUTH_PATHS) {
            if (tokenStore.get() == sentToken) {
                tokenStore.clear()
                onUnauthorized()
            }
        }
        response
    }
