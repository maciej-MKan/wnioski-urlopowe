package pl.wnioski.urlopowe

import kotlinx.coroutines.ExperimentalCoroutinesApi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import pl.wnioski.urlopowe.data.AuthRepository
import pl.wnioski.urlopowe.data.HealthResponse
import pl.wnioski.urlopowe.ui.LoginMode
import pl.wnioski.urlopowe.ui.LoginViewModel

@OptIn(ExperimentalCoroutinesApi::class)
class LoginViewModelTest {

    @get:Rule
    val main = MainDispatcherRule()

    @Test
    fun successSetsFlag() {
        val vm = LoginViewModel(AuthRepository(FakeApi(loginOk = true), FakeStore()))
        vm.onUsername("ola"); vm.onPassword("tajne123")
        vm.submit()
        assertTrue(vm.state.value.success)
    }

    @Test
    fun failureSetsError() {
        val vm = LoginViewModel(AuthRepository(FakeApi(loginOk = false), FakeStore()))
        vm.onUsername("ola"); vm.onPassword("zle")
        vm.submit()
        assertFalse(vm.state.value.success)
        assertNotNull(vm.state.value.error)
    }

    @Test
    fun emptyFieldsShowError() {
        val vm = LoginViewModel(AuthRepository(FakeApi(), FakeStore()))
        vm.submit()
        assertNotNull(vm.state.value.error)
        assertFalse(vm.state.value.success)
    }

    @Test
    fun healthDrivesRegisterAndGoogleFlags() {
        val api = FakeApi(health = HealthResponse(rejestracja = true, google = true))
        val vm = LoginViewModel(AuthRepository(api, FakeStore()))
        assertTrue(vm.state.value.canRegister)
        assertTrue(vm.state.value.hasGoogle)
    }

    @Test
    fun registerModeCallsRegisterAndStoresToken() {
        val api = FakeApi()
        val store = FakeStore()
        val vm = LoginViewModel(AuthRepository(api, store))
        vm.toggleMode()
        assertEquals(LoginMode.REGISTER, vm.state.value.mode)
        vm.onUsername("nowy"); vm.onPassword("tajne123")
        vm.submit()
        assertTrue(vm.state.value.success)
        assertEquals("nowy", api.registered?.username)
        assertEquals("tok-nowy", store.get())
    }
}
