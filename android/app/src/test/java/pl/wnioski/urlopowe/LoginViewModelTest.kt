package pl.wnioski.urlopowe

import kotlinx.coroutines.ExperimentalCoroutinesApi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import pl.wnioski.urlopowe.data.ApiContract
import pl.wnioski.urlopowe.data.AuthRepository
import pl.wnioski.urlopowe.data.HealthResponse
import pl.wnioski.urlopowe.ui.LoginMode
import pl.wnioski.urlopowe.ui.LoginStep
import pl.wnioski.urlopowe.ui.LoginViewModel

@OptIn(ExperimentalCoroutinesApi::class)
class LoginViewModelTest {

    @get:Rule
    val main = MainDispatcherRule()

    @Test
    fun successSetsFlag() {
        val vm = LoginViewModel(AuthRepository(FakeApi(loginOk = true), FakeStore()), FakeServerUrlStore())
        vm.onUsername("ola"); vm.onPassword("tajne123")
        vm.submit()
        assertTrue(vm.state.value.success)
    }

    @Test
    fun failureSetsError() {
        val vm = LoginViewModel(AuthRepository(FakeApi(loginOk = false), FakeStore()), FakeServerUrlStore())
        vm.onUsername("ola"); vm.onPassword("zle")
        vm.submit()
        assertFalse(vm.state.value.success)
        assertNotNull(vm.state.value.error)
    }

    @Test
    fun emptyFieldsShowError() {
        val vm = LoginViewModel(AuthRepository(FakeApi(), FakeStore()), FakeServerUrlStore())
        vm.submit()
        assertNotNull(vm.state.value.error)
        assertFalse(vm.state.value.success)
    }

    @Test
    fun healthDrivesRegisterAndGoogleFlags() {
        val api = FakeApi(health = HealthResponse(rejestracja = true, google = true, apiVersion = ApiContract.MAX_SUPPORTED))
        val vm = LoginViewModel(AuthRepository(api, FakeStore()), FakeServerUrlStore())
        assertTrue(vm.state.value.canRegister)
        assertTrue(vm.state.value.hasGoogle)
        assertTrue(vm.state.value.connected)
        assertTrue(vm.state.value.compatible)
    }

    @Test
    fun serverApiTooNewBlocksLogin() {
        val api = FakeApi(health = HealthResponse(apiVersion = ApiContract.MAX_SUPPORTED + 1))
        val vm = LoginViewModel(AuthRepository(api, FakeStore()), FakeServerUrlStore())
        assertTrue(vm.state.value.connected)          // serwer osiągalny…
        assertFalse(vm.state.value.compatible)        // …ale wersja niezgodna
        assertNotNull(vm.state.value.error)
        vm.onUsername("ola"); vm.onPassword("tajne123")
        vm.submit()
        assertFalse(vm.state.value.success)           // logowanie zablokowane
    }

    @Test
    fun serverWithoutApiVersionIsTooOld() {
        val api = FakeApi(health = HealthResponse(apiVersion = 0)) // stary serwer nie zgłasza wersji
        val vm = LoginViewModel(AuthRepository(api, FakeStore()), FakeServerUrlStore())
        assertFalse(vm.state.value.compatible)
        assertNotNull(vm.state.value.error)
    }

    @Test
    fun registerModeCallsRegisterAndStoresToken() {
        val api = FakeApi()
        val store = FakeStore()
        val vm = LoginViewModel(AuthRepository(api, store), FakeServerUrlStore())
        vm.toggleMode()
        assertEquals(LoginMode.REGISTER, vm.state.value.mode)
        vm.onUsername("nowy"); vm.onPassword("tajne123")
        vm.submit()
        assertTrue(vm.state.value.success)
        assertEquals("nowy", api.registered?.username)
        assertEquals("tok-nowy", store.get())
    }

    @Test
    fun connectPersistsNormalizedUrlAndAdvancesToCredentials() {
        val api = FakeApi(health = HealthResponse(rejestracja = true, google = false, apiVersion = ApiContract.MAX_SUPPORTED))
        val urlStore = FakeServerUrlStore(initial = null)
        val vm = LoginViewModel(AuthRepository(api, FakeStore()), urlStore)
        assertEquals(LoginStep.SERVER, vm.state.value.step)   // brak adresu → ekran serwera
        vm.onServerUrl("moj-serwer:8137")
        vm.connect()
        assertEquals("http://moj-serwer:8137/", urlStore.get())
        assertTrue(vm.state.value.connected)
        assertTrue(vm.state.value.canRegister)
        assertEquals(LoginStep.CREDENTIALS, vm.state.value.step)
    }

    @Test
    fun savedReachableServerStartsOnCredentialsStep() {
        val vm = LoginViewModel(AuthRepository(FakeApi(), FakeStore()), FakeServerUrlStore())
        assertEquals(LoginStep.CREDENTIALS, vm.state.value.step)
    }

    @Test
    fun unreachableServerFallsBackToServerStep() {
        val api = FakeApi(healthThrows = true)
        val vm = LoginViewModel(AuthRepository(api, FakeStore()), FakeServerUrlStore())
        assertEquals(LoginStep.SERVER, vm.state.value.step)
        assertNotNull(vm.state.value.error)
        assertFalse(vm.state.value.connected)
    }

    @Test
    fun submitWithoutServerUrlShowsError() {
        val vm = LoginViewModel(AuthRepository(FakeApi(), FakeStore()), FakeServerUrlStore(initial = null))
        vm.onUsername("ola"); vm.onPassword("tajne123")
        vm.submit()
        assertFalse(vm.state.value.success)
        assertNotNull(vm.state.value.error)
    }
}
