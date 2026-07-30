package pl.wnioski.urlopowe.data

/** Tworzenie wniosków z dynamicznego rejestru (§15 dni za święto liczone osobno). */
class ApplicationRepository(private val api: ApiService) {

    suspend fun registry(year: Int): RegistryDto = api.registry(year)

    suspend fun workingDays(from: String, to: String): Double =
        api.workingDays(from, to).dniRobocze

    suspend fun balance(year: Int): List<BalanceItemDto> = api.balance(year)

    suspend fun create(payload: Map<String, String>): CreateApplicationsResponse =
        api.createApplications(payload)

    suspend fun createManual(payload: Map<String, String>): RecordDto =
        api.createManual(payload)

    suspend fun profile(): Map<String, String> = api.getProfile()

    suspend fun saveProfile(body: Map<String, String>): Map<String, String> =
        api.saveProfile(body)
}
