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

    private fun clearSelection() {
        anchor = null
        _state.update { it.copy(selected = null, selStart = null, selEnd = null) }
    }

    /**
     * Zaznaczanie okresu przez kliknięcia (§17): pierwsze tapnięcie ustawia początek (jeden dzień),
     * drugie domyka zakres. Ponowne kliknięcie w zaznaczony dzień startowy odznacza wybór (§22.7).
     */
    fun select(cell: DayCell?) {
        val d = cell?.iso ?: return clearSelection()
        val a = anchor
        val s = _state.value
        when {
            // Brak trwającego zaznaczania, ale klik w już zaznaczony pojedynczy dzień → odznacz (§22.7).
            a == null && s.selStart == d && s.selEnd == d -> clearSelection()
            a == null -> {
                anchor = d
                _state.update { it.copy(selected = cell, selStart = d, selEnd = d) }
            }
            // Ponowne kliknięcie dnia startowego (zaznaczanie w toku) → odznacz (§22.7).
            d == a -> clearSelection()
            else -> {
                val start = if (a <= d) a else d
                val end = if (a <= d) d else a
                anchor = null
                val startCell = _state.value.cells.filterNotNull().firstOrNull { it.iso == start } ?: cell
                _state.update { it.copy(selected = startCell, selStart = start, selEnd = end) }
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
                val selIso = _state.value.selStart
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
                _state.update { it.copy(loading = false, types = types, cells = cells, selected = newSel) }
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
