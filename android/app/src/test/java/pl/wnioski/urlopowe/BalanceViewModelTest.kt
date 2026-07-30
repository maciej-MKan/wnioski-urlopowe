package pl.wnioski.urlopowe

import kotlinx.coroutines.ExperimentalCoroutinesApi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Rule
import org.junit.Test
import pl.wnioski.urlopowe.data.BalanceItemDto
import pl.wnioski.urlopowe.data.EntitlementDto
import pl.wnioski.urlopowe.data.RegistryDto
import pl.wnioski.urlopowe.data.RegistryTypeDto
import pl.wnioski.urlopowe.data.SettingsRepository
import pl.wnioski.urlopowe.data.SettingsResponse
import pl.wnioski.urlopowe.ui.BalanceViewModel
import org.junit.Assert.assertNotNull

@OptIn(ExperimentalCoroutinesApi::class)
class BalanceViewModelTest {

    @get:Rule
    val main = MainDispatcherRule()

    private val item = BalanceItemDto(
        typ = "wypoczynkowy", etykieta = "Urlop wypoczynkowy", jednostka = "dni",
        limit = 26.0, wykorzystano = 0.0, zaplanowano = 10.0, pozostalo = 16.0,
    )

    private fun vm(initialYear: Int = 2026): BalanceViewModel =
        BalanceViewModel(SettingsRepository(FakeApi(balance = listOf(item))), initialYear)

    @Test
    fun loadsBalanceOnInit() {
        val vm = vm()
        assertFalse(vm.state.value.loading)
        assertEquals(1, vm.state.value.items.size)
        assertEquals(16.0, vm.state.value.items.first().pozostalo, 0.001)
    }

    @Test
    fun yearNavigationChangesYearAndReloads() {
        val vm = vm(2026)
        vm.prevYear()
        assertEquals(2025, vm.state.value.year)
        assertFalse(vm.state.value.loading)
        vm.nextYear()
        vm.nextYear()
        assertEquals(2027, vm.state.value.year)
    }

    private val settingsRegistry = RegistryDto(
        typy = listOf(
            RegistryTypeDto(id = "wypoczynkowy", nazwa = "Urlop", generowalny = true, maZalegly = true),
            RegistryTypeDto(id = "ojcowski", nazwa = "Ojcowski", generowalny = true, maZalegly = false),
            RegistryTypeDto(id = "wolne_za_swieta", nazwa = "Wolne", generowalny = false),
        ),
    )

    @Test
    fun saveBuildsEntitlementPayload() {
        val api = FakeApi(
            registry = settingsRegistry,
            settings = SettingsResponse(
                rok = 2026, jednozmianowy = true,
                uprawnienia = listOf(
                    EntitlementDto("wypoczynkowy", true, 26.0, null, 0.0, ""),
                    EntitlementDto("ojcowski", false, 14.0, null, null, ""),
                ),
            ),
        )
        val v = BalanceViewModel(SettingsRepository(api), 2026)
        v.setLimit("wypoczynkowy", "20")
        v.setActive("ojcowski", true)
        v.setSingleShift(false)
        v.save()

        val body = api.savedSettings!!
        assertEquals("20", body["wypoczynkowy"]!!.limitDni)
        assertEquals(true, body["wypoczynkowy"]!!.aktywny)
        assertEquals(true, body["ojcowski"]!!.aktywny)
        assertEquals(false, body["wolne_za_swieta"]!!.aktywny)
        assertNotNull(v.state.value.savedMessage)
    }
}
