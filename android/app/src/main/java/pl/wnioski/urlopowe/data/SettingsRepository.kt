package pl.wnioski.urlopowe.data

/** Saldo urlopów i uprawnienia (limity) roku — odczyt (§16). */
class SettingsRepository(private val api: ApiService) {

    suspend fun balance(year: Int): List<BalanceItemDto> = api.balance(year)

    suspend fun settings(year: Int): SettingsResponse = api.settings(year)

    suspend fun registry(year: Int): RegistryDto = api.registry(year)

    suspend fun saveSettings(year: Int, body: Map<String, EntitlementPatch>): SettingsResponse =
        api.saveSettings(year, body)
}
