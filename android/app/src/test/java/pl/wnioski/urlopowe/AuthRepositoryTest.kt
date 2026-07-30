package pl.wnioski.urlopowe

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import pl.wnioski.urlopowe.data.AuthRepository

class AuthRepositoryTest {

    @Test
    fun loginStoresToken() = runTest {
        val store = FakeStore()
        val repo = AuthRepository(FakeApi(loginOk = true), store)
        assertFalse(repo.isLoggedIn())
        repo.login("ola", "tajne123")
        assertTrue(repo.isLoggedIn())
        assertEquals("tok-ola", store.get())
    }

    @Test
    fun logoutClearsToken() = runTest {
        val store = FakeStore(initial = "x")
        AuthRepository(FakeApi(), store).logout()
        assertNull(store.get())
    }

    @Test(expected = RuntimeException::class)
    fun loginFailurePropagates() = runTest {
        AuthRepository(FakeApi(loginOk = false), FakeStore()).login("a", "b")
    }
}
