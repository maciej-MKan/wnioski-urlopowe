package pl.wnioski.urlopowe

import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.ResponseBody.Companion.toResponseBody
import pl.wnioski.urlopowe.data.ApiContract
import pl.wnioski.urlopowe.data.ApiService
import pl.wnioski.urlopowe.data.BalanceItemDto
import pl.wnioski.urlopowe.data.CreateApplicationsResponse
import pl.wnioski.urlopowe.data.CreatedApplicationDto
import pl.wnioski.urlopowe.data.HealthResponse
import pl.wnioski.urlopowe.data.HolidayDto
import pl.wnioski.urlopowe.data.LeaveTypeDto
import pl.wnioski.urlopowe.data.Me
import pl.wnioski.urlopowe.data.RecordDto
import pl.wnioski.urlopowe.data.RegisterRequest
import pl.wnioski.urlopowe.data.RegistryDto
import pl.wnioski.urlopowe.data.SettingsResponse
import pl.wnioski.urlopowe.data.StatusRequest
import pl.wnioski.urlopowe.data.TokenResponse
import pl.wnioski.urlopowe.data.TokenStore
import pl.wnioski.urlopowe.data.TypesResponse
import pl.wnioski.urlopowe.data.WorkingDaysResponse

class FakeApi(
    private val loginOk: Boolean = true,
    records: List<RecordDto> = emptyList(),
    private val types: List<LeaveTypeDto> = emptyList(),
    private val holidays: List<HolidayDto> = emptyList(),
    private val balance: List<BalanceItemDto> = emptyList(),
    private val settings: SettingsResponse? = null,
    private val registry: RegistryDto = RegistryDto(),
    private val workingDays: Double = 0.0,
    private val health: HealthResponse = HealthResponse(apiVersion = ApiContract.MAX_SUPPORTED),
    private val healthThrows: Boolean = false,
    profile: Map<String, String> = emptyMap(),
) : ApiService {

    /** Ostatnie żądanie rejestracji — do asercji. */
    var registered: RegisterRequest? = null

    /** Profil użytkownika (mutowalny) + ostatni zapis. */
    private var profileData: Map<String, String> = profile
    var savedProfile: Map<String, String>? = null

    /** Payloady przekazane do createApplications — do asercji w testach. */
    val created = mutableListOf<Map<String, String>>()

    private val recordList = records.toMutableList()

    override suspend fun login(username: String, password: String): TokenResponse {
        if (!loginOk) throw RuntimeException("401")
        return TokenResponse(accessToken = "tok-$username")
    }
    override suspend fun register(body: RegisterRequest): TokenResponse {
        registered = body
        return TokenResponse(accessToken = "tok-${body.username}")
    }
    override suspend fun health(): HealthResponse {
        if (healthThrows) throw RuntimeException("brak połączenia")
        return health
    }
    override suspend fun me(): Me = Me(1, "ola")
    override suspend fun getProfile(): Map<String, String> = profileData
    override suspend fun saveProfile(body: Map<String, String>): Map<String, String> {
        savedProfile = body
        profileData = body
        return body
    }
    override suspend fun types(rok: Int?): TypesResponse = TypesResponse(types)
    override suspend fun records(rok: Int?): List<RecordDto> = recordList.toList()
    override suspend fun holidays(rok: Int): List<HolidayDto> = holidays
    override suspend fun balance(rok: Int): List<BalanceItemDto> = balance
    override suspend fun settings(rok: Int): SettingsResponse =
        settings ?: SettingsResponse(rok = rok)
    override suspend fun registry(rok: Int): RegistryDto = registry
    override suspend fun workingDays(dataOd: String, dataDo: String): WorkingDaysResponse =
        WorkingDaysResponse(dniRobocze = workingDays)

    /** Ostatni payload przekazany do saveSettings — do asercji. */
    var savedSettings: Map<String, pl.wnioski.urlopowe.data.EntitlementPatch>? = null

    override suspend fun saveSettings(
        rok: Int,
        body: Map<String, pl.wnioski.urlopowe.data.EntitlementPatch>,
    ): SettingsResponse {
        savedSettings = body
        return settings ?: SettingsResponse(rok = rok)
    }

    override suspend fun createApplications(payload: Map<String, String>): CreateApplicationsResponse {
        created.add(payload)
        return CreateApplicationsResponse(
            wnioski = listOf(CreatedApplicationDto(id = 99, nazwaPliku = "wniosek.pdf", typ = payload["typ"] ?: ""))
        )
    }

    /** Payloady przekazane do createManual — do asercji w testach. */
    val manual = mutableListOf<Map<String, String>>()

    override suspend fun createManual(payload: Map<String, String>): RecordDto {
        manual.add(payload)
        return RecordDto(
            id = 77, typ = payload["typ"] ?: "", status = payload["status"] ?: "zaakceptowany",
            zrodlo = "reczny", dataOd = payload["data_od"], dataDo = payload["data_do"],
        )
    }

    override suspend fun setStatus(id: Int, body: StatusRequest): RecordDto {
        val idx = recordList.indexOfFirst { it.id == id }
        val updated = recordList[idx].copy(status = body.status)
        recordList[idx] = updated
        return updated
    }

    override suspend fun delete(id: Int) {
        recordList.removeAll { it.id == id }
    }

    override suspend fun pdf(id: Int): okhttp3.ResponseBody =
        "%PDF-1.4".toByteArray()
            .toResponseBody("application/pdf".toMediaTypeOrNull())
}

class FakeStore(initial: String? = null) : TokenStore {
    private var token: String? = initial
    override fun get(): String? = token
    override fun set(token: String) { this.token = token }
    override fun clear() { token = null }
}

class FakeServerUrlStore(initial: String? = "http://test.local/") : pl.wnioski.urlopowe.data.ServerUrlStore {
    private var url: String? = initial
    override fun get(): String? = url
    override fun set(url: String) { this.url = url }
}
