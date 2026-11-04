package pl.wnioski.urlopowe

import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import pl.wnioski.urlopowe.data.TokenStore
import pl.wnioski.urlopowe.data.unauthorizedInterceptor

class UnauthorizedInterceptorTest {

    private class MemTokens(var token: String?) : TokenStore {
        override fun get() = token
        override fun set(token: String) { this.token = token }
        override fun clear() { token = null }
    }

    /** Klient z interceptorem i „serwerem”, który odpowiada [code]; [beforeReply] symuluje zdarzenie w trakcie żądania. */
    private fun call(tokens: TokenStore, path: String, code: Int, beforeReply: () -> Unit = {}, onUnauthorized: () -> Unit): Int {
        val server = Interceptor { chain ->
            beforeReply()
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1)
                .code(code).message("x").body("".toResponseBody()).build()
        }
        val client = OkHttpClient.Builder()
            .addInterceptor(unauthorizedInterceptor(tokens, onUnauthorized))
            .addInterceptor(server).build()
        return client.newCall(Request.Builder().url("http://h$path").build()).execute().use { it.code }
    }

    @Test fun clearsTokenAndNotifiesOn401() {
        val tokens = MemTokens("stary")
        var calls = 0
        assertEquals(401, call(tokens, "/api/bilans", 401) { calls++ })
        assertNull(tokens.get())
        assertEquals(1, calls)
    }

    @Test fun ignoresSuccessfulResponses() {
        val tokens = MemTokens("t")
        var calls = 0
        call(tokens, "/api/bilans", 200) { calls++ }
        assertEquals("t", tokens.get())
        assertEquals(0, calls)
    }

    @Test fun ignores401FromLoginAndRegister() {
        val tokens = MemTokens(null)
        var calls = 0
        call(tokens, "/api/token", 401) { calls++ }
        call(tokens, "/api/register", 401) { calls++ }
        assertEquals(0, calls)
    }

    @Test fun ignoresOtherErrorCodes() {
        val tokens = MemTokens("t")
        var calls = 0
        call(tokens, "/api/bilans", 403) { calls++ }
        call(tokens, "/api/bilans", 500) { calls++ }
        assertEquals("t", tokens.get())
        assertEquals(0, calls)
    }

    @Test fun lateStale401DoesNotLogOutFreshLogin() {
        val tokens = MemTokens("stary")
        var calls = 0
        // w trakcie żądania użytkownik zalogował się ponownie (nowy token)
        call(tokens, "/api/bilans", 401, beforeReply = { tokens.set("nowy") }) { calls++ }
        assertEquals("nowy", tokens.get())
        assertEquals(0, calls)
    }
}
