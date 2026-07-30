package pl.wnioski.urlopowe

import kotlinx.serialization.decodeFromString
import org.junit.Assert.assertEquals
import org.junit.Test
import pl.wnioski.urlopowe.data.ApiFactory
import pl.wnioski.urlopowe.data.RecordDto
import pl.wnioski.urlopowe.data.TokenResponse
import pl.wnioski.urlopowe.data.TypesResponse

class SerializationTest {

    private val json = ApiFactory.json

    @Test
    fun parseRecord_ignoresExtraKeys() {
        val r = json.decodeFromString<RecordDto>(
            """{"id":5,"typ":"wypoczynkowy","rok":2026,"status":"do_akceptacji","zrodlo":"wniosek",
                "za_okres":"biezacy","data_od":"2026-08-04","data_do":"2026-08-08","dni_robocze":4.0,
                "godziny":null,"ma_zalacznik":false,"zalacznik_mime":null,"korekta_powod":null,
                "utworzono":"x","zmieniono":"y","dane":{"typ":"wypoczynkowy"}}"""
        )
        assertEquals(5, r.id)
        assertEquals("wypoczynkowy", r.typ)
        assertEquals(4.0, r.dniRobocze!!, 0.0)
        assertEquals("2026-08-04", r.dataOd)
    }

    @Test
    fun parseToken() {
        val t = json.decodeFromString<TokenResponse>("""{"access_token":"abc","token_type":"bearer"}""")
        assertEquals("abc", t.accessToken)
    }

    @Test
    fun parseTypes() {
        val t = json.decodeFromString<TypesResponse>(
            """{"wspolne":[],"typy":[{"id":"wypoczynkowy","nazwa":"Urlop wypoczynkowy",
                "kolor":"#2f8f5b","aktywny":true,"generowalny":true}]}"""
        )
        assertEquals(1, t.typy.size)
        assertEquals("#2f8f5b", t.typy[0].kolor)
    }
}
