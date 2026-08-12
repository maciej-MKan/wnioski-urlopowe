package pl.wnioski.urlopowe.data

import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/** Kontrakt HTTP backendu (te same endpointy co web; §18 auth bearer). */
interface ApiService {

    @FormUrlEncoded
    @POST("api/token")
    suspend fun login(
        @Field("username") username: String,
        @Field("password") password: String,
    ): TokenResponse

    @POST("api/register")
    suspend fun register(@Body body: RegisterRequest): TokenResponse

    @GET("api/health")
    suspend fun health(): HealthResponse

    @GET("api/me")
    suspend fun me(): Me

    @GET("api/profil")
    suspend fun getProfile(): Map<String, String>

    @PUT("api/profil")
    suspend fun saveProfile(@Body body: Map<String, String>): Map<String, String>

    @GET("api/typy")
    suspend fun types(@Query("rok") rok: Int? = null): TypesResponse

    @GET("api/rekordy")
    suspend fun records(@Query("rok") rok: Int? = null): List<RecordDto>

    @GET("api/swieta")
    suspend fun holidays(@Query("rok") rok: Int): List<HolidayDto>

    @GET("api/typy")
    suspend fun registry(@Query("rok") rok: Int): RegistryDto

    @GET("api/dni-robocze")
    suspend fun workingDays(
        @Query("data_od") dataOd: String,
        @Query("data_do") dataDo: String,
    ): WorkingDaysResponse

    @POST("api/wnioski")
    suspend fun createApplications(@Body payload: Map<String, String>): CreateApplicationsResponse

    @POST("api/rekordy/reczny")
    suspend fun createManual(@Body payload: Map<String, String>): RecordDto

    @GET("api/bilans")
    suspend fun balance(@Query("rok") rok: Int): List<BalanceItemDto>

    @GET("api/ustawienia")
    suspend fun settings(@Query("rok") rok: Int): SettingsResponse

    @PUT("api/ustawienia")
    suspend fun saveSettings(
        @Query("rok") rok: Int,
        @Body body: Map<String, EntitlementPatch>,
    ): SettingsResponse

    @PATCH("api/rekordy/{id}/status")
    suspend fun setStatus(@Path("id") id: Int, @Body body: StatusRequest): RecordDto

    @DELETE("api/rekordy/{id}")
    suspend fun delete(@Path("id") id: Int)

    @GET("api/rekordy/{id}/pdf")
    suspend fun pdf(@Path("id") id: Int): ResponseBody

    @GET("api/rekordy/{id}/zalacznik")
    suspend fun attachment(@Path("id") id: Int): ResponseBody
}
