package pl.wnioski.urlopowe

import kotlinx.coroutines.ExperimentalCoroutinesApi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
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
    fun rangeSelectionSortsReversedTaps() {
        val vm = vmWith()
        val cells = vm.state.value.cells.filterNotNull()
        vm.select(cells.first { it.day == 8 })
        vm.select(cells.first { it.day == 5 })
        assertEquals(cells.first { it.day == 5 }.iso, vm.state.value.selStart)
        assertEquals(cells.first { it.day == 8 }.iso, vm.state.value.selEnd)
    }
}
