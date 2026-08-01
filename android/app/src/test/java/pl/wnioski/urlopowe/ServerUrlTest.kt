package pl.wnioski.urlopowe

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import pl.wnioski.urlopowe.data.normalizeServerUrl

class ServerUrlTest {

    @Test fun addsSchemeAndTrailingSlash() {
        assertEquals("http://192.168.1.10:8137/", normalizeServerUrl("192.168.1.10:8137"))
    }

    @Test fun keepsHttps() {
        assertEquals("https://serwer.example/", normalizeServerUrl("https://serwer.example"))
    }

    @Test fun keepsExistingTrailingSlash() {
        assertEquals("http://host/", normalizeServerUrl("http://host/"))
    }

    @Test fun trimsWhitespace() {
        assertEquals("http://host/", normalizeServerUrl("  host  "))
    }

    @Test fun rejectsBlank() {
        assertNull(normalizeServerUrl(""))
        assertNull(normalizeServerUrl("   "))
        assertNull(normalizeServerUrl(null))
    }

    @Test fun rejectsSchemeWithoutHost() {
        assertNull(normalizeServerUrl("http://"))
    }
}
