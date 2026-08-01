package pl.wnioski.urlopowe

import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import pl.wnioski.urlopowe.data.ApiContract
import pl.wnioski.urlopowe.data.ApiContract.Compatibility

class ApiContractTest {

    @Test
    fun versionInSupportedRangeIsOk() {
        assertTrue(ApiContract.check(ApiContract.MIN_SUPPORTED) is Compatibility.Ok)
        assertTrue(ApiContract.check(ApiContract.MAX_SUPPORTED) is Compatibility.Ok)
        assertNull(ApiContract.message(ApiContract.check(ApiContract.MAX_SUPPORTED)))
    }

    @Test
    fun newerServerMeansClientTooOld() {
        val c = ApiContract.check(ApiContract.MAX_SUPPORTED + 1)
        assertTrue(c is Compatibility.ClientTooOld)
        assertNotNull(ApiContract.message(c))
    }

    @Test
    fun olderOrMissingServerVersionMeansServerTooOld() {
        assertTrue(ApiContract.check(ApiContract.MIN_SUPPORTED - 1) is Compatibility.ServerTooOld)
        assertTrue(ApiContract.check(0) is Compatibility.ServerTooOld)
        assertNotNull(ApiContract.message(ApiContract.check(0)))
    }
}
