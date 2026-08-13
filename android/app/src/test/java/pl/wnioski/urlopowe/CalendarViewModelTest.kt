package pl.wnioski.urlopowe

import kotlinx.coroutines.ExperimentalCoroutinesApi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import pl.wnioski.urlopowe.data.CalendarRepository
import pl.wnioski.urlopowe.data.LeaveTypeDto
import pl.wnioski.urlopowe.data.RecordDto
import pl.wnioski.urlopowe.ui.CalendarViewModel
import java.time.LocalDate

@OptIn(ExperimentalCoroutinesApi::class)
class CalendarViewModelTest {

    @get:Rule
    val main = MainDispatcherRule()

    private val today = LocalDate.now().toString()
    private val types = listOf(LeaveTypeDto("wypoczynkowy", "Urlop wypoczynkowy", "#2f8f5b"))

    private fun vmWith(vararg recs: RecordDto): CalendarViewModel =
        CalendarViewModel(CalendarRepository(FakeApi(records = recs.toList(), types = types)))

    private fun todayRecord(id: Int, status: String = "do_akceptacji") =
        RecordDto(id = id, typ = "wypoczynkowy", status = status, dataOd = today, dataDo = today)

    @Test
    fun loadsCellsOnInit() {
        val vm = vmWith()
        assertTrue(vm.state.value.cells.isNotEmpty())
        assertFalse(vm.state.value.loading)
    }

    @Test
    fun noLoginFlagFollowsHealth() {
        assertFalse(vmWith().state.value.noLogin)  // domyślnie serwer wymaga logowania
        val bezLog = CalendarViewModel(
            CalendarRepository(FakeApi(types = types, health = pl.wnioski.urlopowe.data.HealthResponse(bezLogowania = true))),
        )
        assertTrue(bezLog.state.value.noLogin)
    }

    @Test
    fun approveUpdatesStatusAndKeepsSelection() {
        val vm = vmWith(todayRecord(1))
        val cell = vm.state.value.cells.filterNotNull().first { it.iso == today }
        vm.select(cell)
        vm.approve(1)
        assertEquals("zaakceptowany", vm.state.value.selected!!.records.first().status)
    }

    @Test
    fun deleteRemovesRecord() {
        val vm = vmWith(todayRecord(1))
        vm.deleteRecord(1)
        val remaining = vm.state.value.cells.filterNotNull().flatMap { it.records }
        assertTrue(remaining.isEmpty())
    }

    @Test
    fun rangeSelectionAcrossTwoTaps() {
        val vm = vmWith()
        val cells = vm.state.value.cells.filterNotNull()
        val d5 = cells.first { it.day == 5 }
        val d8 = cells.first { it.day == 8 }
        vm.select(d5)
        assertEquals(d5.iso, vm.state.value.selStart)
        assertEquals(d5.iso, vm.state.value.selEnd)   // pojedynczy dzień po pierwszym tapnięciu
        vm.select(d8)
        assertEquals(d5.iso, vm.state.value.selStart)
        assertEquals(d8.iso, vm.state.value.selEnd)   // zakres po drugim tapnięciu
        val d3 = cells.first { it.day == 3 }
        vm.select(d3)                                  // trzecie tapnięcie zaczyna od nowa
        assertEquals(d3.iso, vm.state.value.selStart)
        assertEquals(d3.iso, vm.state.value.selEnd)
    }

    @Test
    fun toggleViewBuildsYearGrid() {
        val vm = vmWith()
        vm.toggleView()
        assertEquals(pl.wnioski.urlopowe.ui.ViewMode.YEAR, vm.state.value.viewMode)
        assertEquals(12, vm.state.value.yearMonths.size)
        // klik mini-miesiąca wraca do widoku miesięcznego
        val target = vm.state.value.yearMonths[5].ym
        vm.openMonth(target)
        assertEquals(pl.wnioski.urlopowe.ui.ViewMode.MONTH, vm.state.value.viewMode)
        assertEquals(target, vm.state.value.ym)
    }

    @Test
    fun overlappingRangeSelectionBlocked() {
        val ym = java.time.YearMonth.now()
        val rec = RecordDto(
            id = 1, typ = "wypoczynkowy", status = "do_akceptacji",
            dataOd = ym.atDay(10).toString(), dataDo = ym.atDay(14).toString(),
        )
        val vm = CalendarViewModel(CalendarRepository(FakeApi(records = listOf(rec), types = types)))
        val cells = vm.state.value.cells.filterNotNull()
        val d8 = cells.first { it.day == 8 }
        val d16 = cells.first { it.day == 16 }         // wolny dzień za urlopem 10–14
        vm.select(d8)
        vm.select(d16)                                 // 8–16 krzyżuje 10–14 → blokada (§22.9)
        assertNotNull(vm.state.value.error)
        assertEquals(d8.iso, vm.state.value.selStart)  // zakres nie domknięty
        assertEquals(d8.iso, vm.state.value.selEnd)
        // Rozłączny zakres domyka się bez błędu.
        val d2 = cells.first { it.day == 2 }
        val d5 = cells.first { it.day == 5 }
        vm.select(d2); vm.select(d5)
        assertEquals(d5.iso, vm.state.value.selEnd)
        assertNull(vm.state.value.error)
    }

    @Test
    fun reclickStartDeselects() {
        val vm = vmWith()
        val cells = vm.state.value.cells.filterNotNull()
        val d5 = cells.first { it.day == 5 }
        vm.select(d5)                                  // pojedynczy dzień zaznaczony
        assertEquals(d5.iso, vm.state.value.selStart)
        vm.select(d5)                                  // ponowne kliknięcie startu → odznacz (§22.7)
        assertEquals(null, vm.state.value.selStart)
        assertEquals(null, vm.state.value.selEnd)
        assertEquals(null, vm.state.value.selected)
        // Po odznaczeniu można zaznaczyć od nowa.
        vm.select(d5)
        assertEquals(d5.iso, vm.state.value.selStart)
    }

    @Test
    fun rangeSelectionSortsReversedTaps() {
        val vm = vmWith()
        val cells = vm.state.value.cells.filterNotNull()
        vm.select(cells.first { it.day == 8 })
        vm.select(cells.first { it.day == 5 })
        assertEquals(cells.first { it.day == 5 }.iso, vm.state.value.selStart)
        assertEquals(cells.first { it.day == 8 }.iso, vm.state.value.selEnd)
    }

    private fun vmWithLeave(status: String = "do_akceptacji"): Pair<CalendarViewModel, List<pl.wnioski.urlopowe.ui.DayCell>> {
        val ym = java.time.YearMonth.now()
        val rec = RecordDto(
            id = 1, typ = "wypoczynkowy", status = status,
            dataOd = ym.atDay(10).toString(), dataDo = ym.atDay(14).toString(),
        )
        val vm = CalendarViewModel(CalendarRepository(FakeApi(records = listOf(rec), types = types)))
        return vm to vm.state.value.cells.filterNotNull()
    }

    @Test
    fun clickLeaveDayShowsInfoWithoutStartingSelection() {
        val (vm, cells) = vmWithLeave()
        val leaveDay = cells.first { it.day == 12 }
        vm.select(leaveDay)                                // klik w urlop bez wybranego początku
        assertEquals(leaveDay.iso, vm.state.value.selected!!.iso)  // pokazuje szczegóły
        assertNull(vm.state.value.selStart)                // NIE ustala początku
        assertNull(vm.state.value.selEnd)
        assertNull(vm.state.value.error)
    }

    @Test
    fun clickLeaveDayClearsPendingStart() {
        val (vm, cells) = vmWithLeave()
        val free = cells.first { it.day == 5 }
        val leaveDay = cells.first { it.day == 12 }
        vm.select(free)                                    // wybrany początek (wolny dzień)
        assertEquals(free.iso, vm.state.value.selStart)
        vm.select(leaveDay)                                // klik w urlop → czyści początek, bez błędu
        assertNull(vm.state.value.selStart)
        assertNull(vm.state.value.selEnd)
        assertNull(vm.state.value.error)
        assertEquals(leaveDay.iso, vm.state.value.selected!!.iso)
    }

    @Test
    fun rejectedLeaveDayIsSelectable() {
        val (vm, cells) = vmWithLeave(status = "odrzucony")
        val d12 = cells.first { it.day == 12 }
        vm.select(d12)                                     // odrzucony urlop nie blokuje zaznaczania
        assertEquals(d12.iso, vm.state.value.selStart)
    }
}
