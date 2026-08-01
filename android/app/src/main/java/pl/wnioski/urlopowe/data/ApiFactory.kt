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
     */
    fun create(defaultBaseUrl: String, baseUrlProvider: () -> String, tokenStore: TokenStore): ApiService {
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
