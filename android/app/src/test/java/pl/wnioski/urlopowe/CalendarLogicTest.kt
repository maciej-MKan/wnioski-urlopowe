package pl.wnioski.urlopowe

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import pl.wnioski.urlopowe.data.RecordDto
import pl.wnioski.urlopowe.ui.monthCells
import java.time.YearMonth

class CalendarLogicTest {

    @Test
    fun cellsHaveLeadingOffsetAndAllDays() {
        // 1 sierpnia 2026 to sobota → 5 pustych komórek na początku, potem 31 dni.
        val cells = monthCells(YearMonth.of(2026, 8), emptyList(), emptyMap())
        assertEquals(5, cells.takeWhile { it == null }.size)
        assertEquals(5 + 31, cells.size)
    }

    @Test
    fun recordAppearsOnEverySpannedDay() {
        val rec = RecordDto(id = 1, typ = "wypoczynkowy", status = "zaakceptowany",
            dataOd = "2026-08-04", dataDo = "2026-08-06")
        val days = monthCells(YearMonth.of(2026, 8), listOf(rec), emptyMap()).filterNotNull()
        assertEquals(1, days.first { it.day == 4 }.records.size)
        assertEquals(1, days.first { it.day == 5 }.records.size)
        assertEquals(1, days.first { it.day == 6 }.records.size)
        assertEquals(0, days.first { it.day == 7 }.records.size)
    }

    @Test
    fun holidayAndWeekendFlags() {
        val days = monthCells(YearMonth.of(2026, 8), emptyList(),
            mapOf("2026-08-15" to "Wniebowzięcie NMP")).filterNotNull()
        val d15 = days.first { it.day == 15 }
        assertEquals("Wniebowzięcie NMP", d15.holiday)
        assertTrue(d15.weekend)  // 15.08.2026 = sobota
    }
}
