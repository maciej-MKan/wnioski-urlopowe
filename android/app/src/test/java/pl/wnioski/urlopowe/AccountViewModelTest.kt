package pl.wnioski.urlopowe

import kotlinx.coroutines.ExperimentalCoroutinesApi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import pl.wnioski.urlopowe.data.AuthRepository
import pl.wnioski.urlopowe.ui.AccountViewModel

@OptIn(ExperimentalCoroutinesApi::class)
class AccountViewModelTest {

    @get:Rule
    val main = MainDispatcherRule()

    private fun vm(): Pair<AccountViewModel, FakeApi> {
        val api = FakeApi()
        return AccountViewModel(AuthRepository(api, FakeStore())) to api
    }

    @Test
    fun changePasswordSendsRequest() {
        val (v, api) = vm()
        v.setCurrent("stare123"); v.setNew("nowe1234"); v.setRepeat("nowe1234")
        v.changePassword()
        assertTrue(v.state.value.done)
        assertEquals("stare123", api.passwordChange?.get("obecne"))
        assertEquals("nowe1234", api.passwordChange?.get("nowe"))
    }

    @Test
    fun mismatchedRepeatBlocks() {
        val (v, api) = vm()
        v.setNew("nowe1234"); v.setRepeat("inne")
        v.changePassword()
        assertNull(api.passwordChange)
        assertFalse(v.state.value.done)
        assertNotNull(v.state.value.error)
    }

    @Test
    fun emptyNewBlocks() {
        val (v, api) = vm()
        v.setCurrent("stare123")
        v.changePassword()
        assertNull(api.passwordChange)
        assertNotNull(v.state.value.error)
    }

    @Test
    fun deleteAccountIsTwoStep() {
        val (v, api) = vm()
        v.deleteAccount()                              // pierwsze tapnięcie — tylko potwierdzenie
        assertTrue(v.state.value.deleteConfirm)
        assertFalse(api.accountDeleted)
        assertFalse(v.state.value.deleted)
        v.deleteAccount()                              // drugie — faktyczne usunięcie
        assertTrue(api.accountDeleted)
        assertTrue(v.state.value.deleted)
    }
}
