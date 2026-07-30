package pl.wnioski.urlopowe.data

import kotlinx.serialization.json.Json
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

/** Buduje `ApiService` (Retrofit + OkHttp), dokładając bearer token z `TokenStore`. */
object ApiFactory {

    val json: Json = Json { ignoreUnknownKeys = true }

    fun create(baseUrl: String, tokenStore: TokenStore): ApiService {
        val auth = Interceptor { chain ->
            val builder = chain.request().newBuilder()
            tokenStore.get()?.let { builder.header("Authorization", "Bearer $it") }
            chain.proceed(builder.build())
        }
        val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC }
        val client = OkHttpClient.Builder()
            .addInterceptor(auth)
            .addInterceptor(logging)
            .build()
        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(ApiService::class.java)
    }
}
