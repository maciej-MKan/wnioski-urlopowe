package pl.wnioski.urlopowe

import kotlinx.coroutines.ExperimentalCoroutinesApi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import pl.wnioski.urlopowe.data.ApplicationRepository
import pl.wnioski.urlopowe.data.RegistryDto
import pl.wnioski.urlopowe.data.RegistryTypeDto
import pl.wnioski.urlopowe.ui.ManualViewModel

@OptIn(ExperimentalCoroutinesApi::class)
class ManualViewModelTest {

    @get:Rule
    val main = MainDispatcherRule()

    private val registry = RegistryDto(
        typy = listOf(
            RegistryTypeDto(id = "wypoczynkowy", nazwa = "Urlop wypoczynkowy", aktywny = true, generowalny = true),
            RegistryTypeDto(id = "wolne_za_swieta", nazwa = "Dzień wolny", aktywny = true, generowalny = false),
            RegistryTypeDto(id = "ojcowski", nazwa = "Urlop ojcowski", aktywny = false, generowalny = true),
            RegistryTypeDto(id = "opieka", nazwa = "Opieka", aktywny = true, generowalny = true),
        ),
    )

    private fun vm(from: String? = null, to: String? = null): Pair<ManualViewModel, FakeApi> {
        val api = FakeApi(registry = registry)
        return ManualViewModel(ApplicationRepository(api), from, to, 2026) to api
    }

    @Test
    fun loadsActiveTypesInclNonGeneratable() {
        val (v, _) = vm()
        assertFalse(v.state.value.loading)
        // aktywne: wypoczynkowy, wolne_za_swieta, opieka — nieaktywny ojcowski odfiltrowany
        assertEquals(listOf("wypoczynkowy", "wolne_za_swieta", "opieka"), v.state.value.types.map { it.id })
        assertEquals("wypoczynkowy", v.state.value.typ)
        assertEquals("zaakceptowany", v.state.value.status)
    }

    @Test
    fun submitPostsManualPayloadWithPrefillAndStatus() {
        val (v, api) = vm(from = "2026-07-20", to = "2026-07-20")
        v.setStatus("do_akceptacji")
        v.submit()
        assertEquals(1, api.manual.size)
        val p = api.manual.first()
        assertEquals("wypoczynkowy", p["typ"])
        assertEquals("do_akceptacji", p["status"])
        assertEquals("2026-07-20", p["data_od"])
        assertFalse(p.containsKey("wymiar"))
        assertTrue(v.state.value.done)
    }

    @Test
    fun opiekaWithWymiarAddsFormaGodziny() {
        val (v, api) = vm()
        v.setTyp("opieka")
        v.setWymiar("8")
        v.submit()
        val p = api.manual.first()
        assertEquals("opieka", p["typ"])
        assertEquals("8", p["wymiar"])
        assertEquals("godziny", p["forma"])
    }
}
