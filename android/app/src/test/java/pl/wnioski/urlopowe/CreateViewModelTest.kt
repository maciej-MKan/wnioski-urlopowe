package pl.wnioski.urlopowe

import kotlinx.coroutines.ExperimentalCoroutinesApi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import pl.wnioski.urlopowe.data.ApplicationRepository
import pl.wnioski.urlopowe.data.FieldDto
import pl.wnioski.urlopowe.data.RegistryDto
import pl.wnioski.urlopowe.data.RegistryTypeDto
import pl.wnioski.urlopowe.ui.CreateViewModel

@OptIn(ExperimentalCoroutinesApi::class)
class CreateViewModelTest {

    @get:Rule
    val main = MainDispatcherRule()

    private val registry = RegistryDto(
        wspolne = listOf(
            FieldDto(name = "miejscowosc", label = "Miejscowość", wymagane = true),
            FieldDto(name = "pracodawca", label = "Pracodawca", typPola = "textarea", wymagane = true),
            FieldDto(name = "data", label = "Data sporządzenia", typPola = "date"),
        ),
        typy = listOf(
            RegistryTypeDto(
                id = "wypoczynkowy", nazwa = "Urlop wypoczynkowy", aktywny = true, generowalny = true,
                pola = listOf(
                    FieldDto(name = "data_od", label = "Data od", typPola = "date", wymagane = true),
                    FieldDto(name = "data_do", label = "Data do", typPola = "date", wymagane = true),
                ),
            ),
            RegistryTypeDto(  // niegenerowalny → odfiltrowany
                id = "wolne_za_swieta", nazwa = "Dzień wolny", aktywny = true, generowalny = false,
            ),
        ),
    )

    private fun vm(from: String? = null, to: String? = null): Pair<CreateViewModel, FakeApi> {
        val api = FakeApi(registry = registry)
        val v = CreateViewModel(ApplicationRepository(api), prefillFrom = from, prefillTo = to, year = 2026)
        return v to api
    }

    @Test
    fun filtersToGeneratableTypesAndSetsDefaults() {
        val (v, _) = vm()
        assertFalse(v.state.value.loading)
        assertEquals(1, v.state.value.types.size)               // tylko generowalny
        assertEquals("wypoczynkowy", v.state.value.activeType)
        // domyślna data sporządzenia = dziś
        assertTrue(v.state.value.commonValues["data"]!!.isNotBlank())
    }

    @Test
    fun prefillsDatesFromCalendar() {
        val (v, _) = vm(from = "2026-07-13", to = "2026-07-17")
        assertEquals("2026-07-13", v.state.value.fieldValues["data_od"])
        assertEquals("2026-07-17", v.state.value.fieldValues["data_do"])
    }

    @Test
    fun prefillsCommonFieldsFromProfile() {
        val api = FakeApi(registry = registry, profile = mapOf("miejscowosc" to "Warszawa"))
        val v = CreateViewModel(ApplicationRepository(api), year = 2026)
        assertEquals("Warszawa", v.state.value.commonValues["miejscowosc"])
        // „data" nie pochodzi z profilu — ustawiona na dziś (niepusta)
        assertTrue(v.state.value.commonValues["data"]!!.isNotBlank())
    }

    @Test
    fun computesWorkingDaysFromApi() {
        // §22.4: po prefillu dat VM pobiera dni robocze z /api/dni-robocze
        val api = FakeApi(registry = registry, workingDays = 5.0)
        val v = CreateViewModel(ApplicationRepository(api), prefillFrom = "2026-07-13", prefillTo = "2026-07-17", year = 2026)
        assertEquals(5, v.state.value.dniRobocze)
    }

    @Test
    fun submitBlockedWhenRequiredMissing() {
        // brak miejscowości/pracodawcy → walidacja klienta blokuje (§22.2), nic nie wysyła
        val (v, api) = vm(from = "2026-07-13", to = "2026-07-17")
        v.submit()
        assertTrue(api.created.isEmpty())
        assertFalse(v.state.value.done)
        assertTrue(v.state.value.error!!.contains("Miejscowość") && v.state.value.error!!.contains("Pracodawca"))
    }

    @Test
    fun submitSendsPayloadWithoutWeekendWhenNoBalance() {
        // FakeApi.balance puste → brak dialogu §15, tworzy od razu
        val (v, api) = vm(from = "2026-07-13", to = "2026-07-17")
        v.setCommon("miejscowosc", "Warszawa")
        v.setCommon("pracodawca", "ACME")
        v.submit()
        assertEquals(1, api.created.size)
        val payload = api.created.first()
        assertEquals("wypoczynkowy", payload["typ"])
        assertEquals("Warszawa", payload["miejscowosc"])
        assertEquals("2026-07-13", payload["data_od"])
        assertFalse(payload.containsKey("dni_za_swieto"))
        assertTrue(v.state.value.done)
    }
}
