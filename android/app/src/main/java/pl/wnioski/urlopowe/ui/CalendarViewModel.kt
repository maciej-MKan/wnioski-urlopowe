package pl.wnioski.urlopowe.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import pl.wnioski.urlopowe.data.CalendarRepository
import pl.wnioski.urlopowe.data.LeaveTypeDto
import pl.wnioski.urlopowe.data.RecordDto
import java.time.LocalDate
import java.time.YearMonth

data class DayCell(
    val day: Int,
    val iso: String,
    val records: List<RecordDto>,
    val holiday: String?,
    val weekend: Boolean,
)

/** Tryb widoku kalendarza (§22.1): pojedynczy miesiąc vs siatka 12 mini-miesięcy roku. */
enum class ViewMode { MONTH, YEAR }

/** Mini-miesiąc do widoku rocznego. */
data class MonthMini(val ym: YearMonth, val cells: List<DayCell?>)

data class CalendarState(
    val ym: YearMonth,
    val loading: Boolean = false,
    val error: String? = null,
    val types: Map<String, LeaveTypeDto> = emptyMap(),
    val cells: List<DayCell?> = emptyList(),   // null = pusta komórka wyrównania
    val selected: DayCell? = null,             // komórka początku zaznaczenia (do panelu szczegółów)
    val selStart: String? = null,              // ISO początku zaznaczonego okresu
    val selEnd: String? = null,                // ISO końca (== selStart dla jednego dnia)
    val noLogin: Boolean = false,              // serwer w trybie bez logowania → ukryj „Wyloguj"
    val viewMode: ViewMode = ViewMode.MONTH,   // §22.1: miesiąc vs rok
    val yearMonths: List<MonthMini> = emptyList(),  // 12 mini-miesięcy (widok roczny)
)

class CalendarViewModel(private val repo: CalendarRepository) : ViewModel() {

    private val _state = MutableStateFlow(CalendarState(ym = YearMonth.now()))
    val state: StateFlow<CalendarState> = _state.asStateFlow()

    private var records: List<RecordDto> = emptyList()
    private var holidays: Map<String, String> = emptyMap()
    private var loadedYear: Int? = null
    private var anchor: String? = null   // pierwsze tapnięcie okresu (null = brak trwającego zaznaczania)

    init {
        load()
        // Tryb bez logowania serwera → chowamy „Wyloguj" (health niezależny od tokenu).
        viewModelScope.launch {
            runCatching { repo.health() }.onSuccess { h ->
                _state.update { it.copy(noLogin = h.bezLogowania) }
            }
        }
    }

    fun prevMonth() {
        clearSelection()
        _state.update { it.copy(ym = it.ym.minusMonths(1)) }
        refresh()
    }

    fun nextMonth() {
        clearSelection()
        _state.update { it.copy(ym = it.ym.plusMonths(1)) }
        refresh()
    }

    // --- Widok roczny (§22.1) ---

    /** Przełącza między widokiem miesiąca a rokiem. */
    fun toggleView() {
        val next = if (_state.value.viewMode == ViewMode.YEAR) ViewMode.MONTH else ViewMode.YEAR
        _state.update { it.copy(viewMode = next, yearMonths = if (next == ViewMode.YEAR) buildYearMonths() else emptyList()) }
    }

    fun prevYear() { changeYear(-1) }
    fun nextYear() { changeYear(1) }

    private fun changeYear(delta: Int) {
        clearSelection()
        _state.update { it.copy(ym = it.ym.plusYears(delta.toLong())) }
        load()   // przeładuj rekordy/święta nowego roku; load() odbuduje też mini-miesiące (tryb rok)
    }

    /** Otwiera wskazany miesiąc w widoku miesięcznym (klik mini-miesiąca). */
    fun openMonth(ym: YearMonth) {
        clearSelection()
        _state.update { it.copy(ym = ym, viewMode = ViewMode.MONTH) }
        refresh()
    }

    private fun buildYearMonths(): List<MonthMini> {
        val year = _state.value.ym.year
        return (1..12).map { m -> val ym = YearMonth.of(year, m); MonthMini(ym, monthCells(ym, records, holidays)) }
    }

    private fun clearSelection() {
        anchor = null
        _state.update { it.copy(selected = null, selStart = null, selEnd = null, error = null) }
    }

    /** §22.9/§20.4: czy zakres [start,end] nachodzi na istniejący rekord (≠ odrzucony). */
    private fun overlapsExisting(start: String, end: String): Boolean =
        records.any { r ->
            r.status != "odrzucony" &&
                !r.dataOd.isNullOrBlank() && !r.dataDo.isNullOrBlank() &&
                r.dataOd!! <= end && start <= r.dataDo!!
        }

    /** Czy dzień należy do istniejącego urlopu (rekord ≠ odrzucony) — spójne z [overlapsExisting]. */
    private fun isLeaveDay(cell: DayCell): Boolean = cell.records.any { it.status != "odrzucony" }

    /**
     * Zaznaczanie okresu przez kliknięcia (§17): pierwsze tapnięcie ustawia początek (jeden dzień),
     * drugie domyka zakres. Ponowne kliknięcie w zaznaczony dzień startowy odznacza wybór (§22.7).
     * Kliknięcie w dzień należący do urlopu NIE ustala początku ani końca: pokazuje tylko informacje
     * o tym urlopie, a jeśli był wybrany początek zakresu — czyści go.
     */
    fun select(cell: DayCell?) {
        val d = cell?.iso ?: return clearSelection()
        val a = anchor
        val s = _state.value
        when {
            // Klik w dzień należący do urlopu → tylko podgląd, bez ustalania początku/końca.
            // Ewentualny wybrany początek zakresu zostaje wyczyszczony.
            isLeaveDay(cell) -> {
                anchor = null
                _state.update { it.copy(selected = cell, selStart = null, selEnd = null, error = null) }
            }
            // Brak trwającego zaznaczania, ale klik w już zaznaczony pojedynczy dzień → odznacz (§22.7).
            a == null && s.selStart == d && s.selEnd == d -> clearSelection()
            a == null -> {
                anchor = d
                _state.update { it.copy(selected = cell, selStart = d, selEnd = d, error = null) }
            }
            // Ponowne kliknięcie dnia startowego (zaznaczanie w toku) → odznacz (§22.7).
            d == a -> clearSelection()
            else -> {
                val start = if (a <= d) a else d
                val end = if (a <= d) d else a
                anchor = null
                if (overlapsExisting(start, end)) {
                    // §22.9: nie domykamy zakresu nachodzącego na istniejący urlop — komunikat.
                    _state.update { it.copy(error = "Zaznaczony okres nachodzi na istniejący urlop — wybierz inny.") }
                } else {
                    val startCell = _state.value.cells.filterNotNull().firstOrNull { it.iso == start } ?: cell
                    _state.update { it.copy(selected = startCell, selStart = start, selEnd = end, error = null) }
                }
            }
        }
    }

    fun approve(id: Int) = act { repo.setStatus(id, "zaakceptowany") }
    fun reject(id: Int) = act { repo.setStatus(id, "odrzucony") }
    fun deleteRecord(id: Int) = act { repo.delete(id) }

    /** Wykonuje akcję na rekordzie, przeładowuje rok i zachowuje zaznaczony dzień. */
    private fun act(block: suspend () -> Unit) {
        viewModelScope.launch {
            try {
                block()
                val ym = _state.value.ym
                records = repo.records(ym.year)
                val cells = monthCells(ym, records, holidays)
                val selIso = _state.value.selected?.iso   // zachowaj podglądany dzień (także urlop bez selStart)
                val newSel = selIso?.let { iso -> cells.filterNotNull().firstOrNull { it.iso == iso } }
                _state.update { it.copy(cells = cells, selected = newSel) }
            } catch (e: Exception) {
                _state.update { it.copy(error = "Akcja nie powiodła się.") }
            }
        }
    }

    fun load() {
        val ym = _state.value.ym
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val types = repo.types()
                records = repo.records(ym.year)
                holidays = repo.holidays(ym.year)
                loadedYear = ym.year
                val cells = buildCells(ym)
                val selIso = _state.value.selStart
                val newSel = selIso?.let { iso -> cells.filterNotNull().firstOrNull { it.iso == iso } }
                _state.update {
                    it.copy(
                        loading = false, types = types, cells = cells, selected = newSel,
                        yearMonths = if (it.viewMode == ViewMode.YEAR) buildYearMonths() else it.yearMonths,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = "Nie udało się wczytać danych.") }
            }
        }
    }

    private fun refresh() {
        val ym = _state.value.ym
        if (loadedYear == ym.year) {
            _state.update { it.copy(cells = buildCells(ym)) }  // ten sam rok — tylko przelicz komórki
        } else {
            load()
        }
    }

    private fun buildCells(ym: YearMonth): List<DayCell?> = monthCells(ym, records, holidays)
}

/** Czysta funkcja budowania komórek miesiąca (pon-pierwszy) — testowalna bez Androida. */
fun monthCells(
    ym: YearMonth,
    records: List<RecordDto>,
    holidays: Map<String, String>,
): List<DayCell?> {
    val offset = (ym.atDay(1).dayOfWeek.value + 6) % 7  // poniedziałek = 0
    val cells = ArrayList<DayCell?>()
    repeat(offset) { cells.add(null) }
    for (d in 1..ym.lengthOfMonth()) {
        val date: LocalDate = ym.atDay(d)
        val iso = date.toString()
        val recs = records.filter { r ->
            val od = r.dataOd ?: return@filter false
            val do_ = r.dataDo ?: od
            iso in od..do_    // porównanie ISO (YYYY-MM-DD) leksykograficznie = chronologicznie
        }
        cells.add(DayCell(d, iso, recs, holidays[iso], date.dayOfWeek.value >= 6))
    }
    return cells
}
