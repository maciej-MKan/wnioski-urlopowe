package pl.wnioski.urlopowe

import okhttp3.HttpUrl.Companion.toHttpUrl
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import pl.wnioski.urlopowe.data.swapHost

class ApiFactoryTest {

    @Test fun rewritesSchemeHostPortKeepsPathAndQuery() {
        val original = "http://10.0.2.2:8138/api/bilans?rok=2026".toHttpUrl()
        val result = swapHost(original, "https://serwer.example:9443/")
        assertEquals("https://serwer.example:9443/api/bilans?rok=2026", result.toString())
    }

    @Test fun usesDefaultPortForScheme() {
        val original = "http://10.0.2.2:8138/api/health".toHttpUrl()
        val result = swapHost(original, "https://serwer.example/")
        assertEquals("https://serwer.example/api/health", result.toString())
    }

    @Test fun returnsNullForInvalidTarget() {
        val original = "http://10.0.2.2:8138/api/health".toHttpUrl()
        assertNull(swapHost(original, "nie-adres"))
    }
}
