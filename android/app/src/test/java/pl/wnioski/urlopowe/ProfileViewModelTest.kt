package pl.wnioski.urlopowe

import kotlinx.coroutines.ExperimentalCoroutinesApi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Rule
import org.junit.Test
import pl.wnioski.urlopowe.data.ApplicationRepository
import pl.wnioski.urlopowe.data.FieldDto
import pl.wnioski.urlopowe.data.RegistryDto
import pl.wnioski.urlopowe.ui.ProfileViewModel

@OptIn(ExperimentalCoroutinesApi::class)
class ProfileViewModelTest {

    @get:Rule
    val main = MainDispatcherRule()

    private val registry = RegistryDto(
        wspolne = listOf(
            FieldDto(name = "miejscowosc", label = "Miejscowość"),
            FieldDto(name = "data", label = "Data sporządzenia", typPola = "date"),
            FieldDto(name = "imie_nazwisko", label = "Imię i nazwisko"),
            FieldDto(name = "stanowisko", label = "Stanowisko"),
        ),
    )

    @Test
    fun loadsCommonFieldsWithoutDataAndPrefillsFromProfile() {
        val api = FakeApi(registry = registry, profile = mapOf("imie_nazwisko" to "Jan Kowalski"))
        val vm = ProfileViewModel(ApplicationRepository(api), 2026)
        assertFalse(vm.state.value.loading)
        // pole „data" wykluczone
        assertEquals(listOf("miejscowosc", "imie_nazwisko", "stanowisko"), vm.state.value.fields.map { it.name })
        assertEquals("Jan Kowalski", vm.state.value.values["imie_nazwisko"])
    }

    @Test
    fun saveSendsProfileAndShowsMessage() {
        val api = FakeApi(registry = registry)
        val vm = ProfileViewModel(ApplicationRepository(api), 2026)
        vm.setValue("imie_nazwisko", "Anna Nowak")
        vm.setValue("stanowisko", "Specjalista")
        vm.save()
        assertEquals("Anna Nowak", api.savedProfile?.get("imie_nazwisko"))
        assertEquals("Specjalista", api.savedProfile?.get("stanowisko"))
        assertEquals("Zapisano profil.", vm.state.value.savedMessage)
    }
}
