package pl.wnioski.urlopowe.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import pl.wnioski.urlopowe.data.AppContainer
import pl.wnioski.urlopowe.data.LeaveTypeDto

private val MIESIACE = listOf(
    "styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec",
    "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień",
)
private val DNI = listOf("Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd")
private val STATUS_LABEL = mapOf(
    "do_akceptacji" to "do akceptacji", "zaakceptowany" to "zaakceptowany", "odrzucony" to "odrzucony",
)

private fun parseColor(hex: String?): Color? = try {
    if (hex.isNullOrBlank()) null else Color(android.graphics.Color.parseColor(hex))
} catch (e: Exception) { null }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CalendarScreen(
    container: AppContainer,
    onLogout: () -> Unit,
    onOpenBalance: (Int) -> Unit,
    onCreate: (String?, String?) -> Unit,
    onManual: (String?, String?) -> Unit,
    onSettings: () -> Unit,
) {
    val vm: CalendarViewModel = viewModel(
        factory = viewModelFactory { initializer { CalendarViewModel(container.calendar) } }
    )
    val state by vm.state.collectAsStateWithLifecycle()
    // Po powrocie z innego ekranu (np. utworzeniu wniosku) odśwież dane.
    androidx.compose.runtime.LaunchedEffect(Unit) { vm.load() }
    var menu by remember { mutableStateOf(false) }
    val downloadPdf = rememberPdfDownloader { id -> container.calendar.pdfBytes(id) }
    val downloadAttachment = rememberPdfDownloader { id -> container.calendar.attachmentBytes(id) }

    Column(modifier = Modifier.fillMaxSize().safeDrawingPadding()) {
        // §22.3: nagłówek aplikacji z menu (nawigacja + wyloguj).
        TopAppBar(
            title = { Text("Wnioski urlopowe", fontWeight = FontWeight.Bold) },
            actions = {
                Box {
                    IconButton(onClick = { menu = true }) {
                        Icon(Icons.Filled.MoreVert, contentDescription = "Menu")
                    }
                    DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                        DropdownMenuItem(text = { Text("Nowy wniosek") }, onClick = {
                            menu = false
                            onCreate(state.selStart, state.selEnd)
                        })
                        DropdownMenuItem(text = { Text("Dodaj ręcznie") }, onClick = {
                            menu = false
                            onManual(state.selStart, state.selEnd)
                        })
                        DropdownMenuItem(text = { Text("Saldo") }, onClick = {
                            menu = false; onOpenBalance(state.ym.year)
                        })
                        DropdownMenuItem(text = { Text("Ustawienia") }, onClick = { menu = false; onSettings() })
                        // W trybie bez logowania „Wyloguj" nie ma sensu (serwer auto-uwierzytelnia jedyne konto).
                        if (!state.noLogin) {
                            DropdownMenuItem(text = { Text("Wyloguj") }, onClick = { menu = false; onLogout() })
                        }
                    }
                }
            },
        )

      Column(modifier = Modifier.fillMaxSize().padding(12.dp)) {
        // §22.1: nawigacja (miesiąc/rok) + przełącznik widoku
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            TextButton(onClick = { if (state.viewMode == ViewMode.YEAR) vm.prevYear() else vm.prevMonth() }) { Text("‹") }
            Text(
                if (state.viewMode == ViewMode.YEAR) "${state.ym.year}"
                else "${MIESIACE[state.ym.monthValue - 1]} ${state.ym.year}",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f),
            )
            TextButton(onClick = { if (state.viewMode == ViewMode.YEAR) vm.nextYear() else vm.nextMonth() }) { Text("›") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(bottom = 4.dp)) {
            FilterChip(selected = state.viewMode == ViewMode.MONTH,
                onClick = { if (state.viewMode != ViewMode.MONTH) vm.toggleView() }, label = { Text("Miesiąc") })
            FilterChip(selected = state.viewMode == ViewMode.YEAR,
                onClick = { if (state.viewMode != ViewMode.YEAR) vm.toggleView() }, label = { Text("Rok") })
        }

        if (state.loading) LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp))
        state.error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 4.dp))
        }

        if (state.viewMode == ViewMode.YEAR) {
            YearGrid(state.yearMonths, state.types, modifier = Modifier.weight(1f)) { vm.openMonth(it) }
        } else {
            // Nagłówek dni tygodnia
            Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                DNI.forEach {
                    Text(it, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.weight(1f), textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                }
            }

            LazyVerticalGrid(columns = GridCells.Fixed(7), modifier = Modifier.weight(1f)) {
                itemsIndexed(state.cells) { _, cell ->
                    val inRange = cell != null && state.selStart != null &&
                        cell.iso >= state.selStart!! && cell.iso <= (state.selEnd ?: state.selStart!!)
                    DayCellView(cell, state.types, inRange) { vm.select(cell) }
                }
            }

            state.selected?.let { cell ->
                DetailsPanel(
                    cell, state.types,
                    selStart = state.selStart,
                    selEnd = state.selEnd,
                    onApprove = vm::approve,
                    onReject = vm::reject,
                    onDelete = vm::deleteRecord,
                    onPdf = { id -> downloadPdf(id, "wniosek-$id.pdf") },
                    onAttachment = { id -> downloadAttachment(id, "zalacznik-$id") },
                    onCreate = onCreate,
                    onManual = onManual,
                )
            }
        }
      }
    }
}

/** §22.1: siatka 12 mini-miesięcy (3 kolumny), klik miesiąca → widok miesięczny. */
@Composable
private fun YearGrid(
    months: List<MonthMini>,
    types: Map<String, LeaveTypeDto>,
    modifier: Modifier = Modifier,
    onMonth: (java.time.YearMonth) -> Unit,
) {
    Column(modifier = modifier.verticalScroll(rememberScrollState())) {
        months.chunked(3).forEach { row ->
            Row(modifier = Modifier.fillMaxWidth()) {
                row.forEach { mini -> Box(modifier = Modifier.weight(1f)) { MiniMonth(mini, types, onMonth) } }
                repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
private fun MiniMonth(mini: MonthMini, types: Map<String, LeaveTypeDto>, onMonth: (java.time.YearMonth) -> Unit) {
    val weekend = MaterialTheme.colorScheme.surfaceVariant
    Column(modifier = Modifier.padding(4.dp).clickable { onMonth(mini.ym) }) {
        Text(
            MIESIACE[mini.ym.monthValue - 1], fontSize = 12.sp, fontWeight = FontWeight.Medium,
            modifier = Modifier.fillMaxWidth(), textAlign = androidx.compose.ui.text.style.TextAlign.Center,
        )
        mini.cells.chunked(7).forEach { week ->
            Row(modifier = Modifier.fillMaxWidth()) {
                week.forEach { cell ->
                    Box(
                        modifier = Modifier.weight(1f).aspectRatio(1f).padding(0.5.dp)
                            .clip(RoundedCornerShape(2.dp)).background(cellColor(cell, types, weekend)),
                        contentAlignment = Alignment.Center,
                    ) {
                        if (cell != null) Text("${cell.day}", fontSize = 8.sp)
                    }
                }
                repeat(7 - week.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
private fun DayCellView(cell: DayCell?, types: Map<String, LeaveTypeDto>, inRange: Boolean, onClick: () -> Unit) {
    val surfaceVariant = MaterialTheme.colorScheme.surfaceVariant
    val primary = MaterialTheme.colorScheme.primary
    Box(
        modifier = Modifier
            .aspectRatio(1f)
            .padding(2.dp)
            .clip(RoundedCornerShape(6.dp))
            .background(cellColor(cell, types, surfaceVariant))
            .then(if (inRange) Modifier.border(BorderStroke(2.dp, primary), RoundedCornerShape(6.dp)) else Modifier)
            .then(if (cell != null) Modifier.clickable { onClick() } else Modifier),
        contentAlignment = Alignment.TopStart,
    ) {
        if (cell != null) {
            Text(cell.day.toString(), fontSize = 12.sp, modifier = Modifier.padding(4.dp))
        }
    }
}

private fun cellColor(cell: DayCell?, types: Map<String, LeaveTypeDto>, weekendColor: Color): Color {
    if (cell == null) return Color.Transparent
    val main = cell.records.firstOrNull()
    if (main != null) {
        val base = parseColor(types[main.typ]?.kolor) ?: Color.Gray
        val alpha = when (main.status) {
            "zaakceptowany" -> 0.85f
            "odrzucony" -> 0.15f
            else -> 0.4f
        }
        return base.copy(alpha = alpha)
    }
    return if (cell.weekend || cell.holiday != null) weekendColor.copy(alpha = 0.5f) else Color.Transparent
}

@Composable
private fun DetailsPanel(
    cell: DayCell,
    types: Map<String, LeaveTypeDto>,
    selStart: String?,
    selEnd: String?,
    onApprove: (Int) -> Unit,
    onReject: (Int) -> Unit,
    onDelete: (Int) -> Unit,
    onPdf: (Int) -> Unit,
    onAttachment: (Int) -> Unit,
    onCreate: (String?, String?) -> Unit,
    onManual: (String?, String?) -> Unit,
) {
    val isRange = selStart != null && selEnd != null && selStart != selEnd
    Column(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
        HorizontalDivider()
        Text(
            if (isRange) "Okres $selStart – $selEnd" else "Dzień ${cell.iso}",
            fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 8.dp),
        )
        // §17: dla zaznaczenia (dzień lub okres) — szybkie tworzenie z wypełnionymi datami.
        Row(modifier = Modifier.fillMaxWidth()) {
            TextButton(onClick = { onCreate(selStart, selEnd) }) { Text("Nowy wniosek") }
            TextButton(onClick = { onManual(selStart, selEnd) }) { Text("Dodaj ręcznie") }
        }
        cell.holiday?.let { Text("Święto: $it", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        if (cell.records.isEmpty()) {
            Text("Brak urlopów.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        cell.records.forEach { r ->
            val name = types[r.typ]?.nazwa ?: r.typ
            val range = if (r.dataOd != null && r.dataDo != null && r.dataOd != r.dataDo)
                "${r.dataOd} – ${r.dataDo}" else (r.dataOd ?: "")
            Row(modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween) {
                Text(name, fontWeight = FontWeight.Medium)
                Text(STATUS_LABEL[r.status] ?: r.status, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (range.isNotEmpty()) Text(range, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            r.id?.let { id ->
                Row(modifier = Modifier.fillMaxWidth()) {
                    if (r.status != "zaakceptowany") TextButton(onClick = { onApprove(id) }) { Text("Zaakceptuj") }
                    if (r.status != "odrzucony") TextButton(onClick = { onReject(id) }) { Text("Odrzuć") }
                    if (r.zrodlo == "wniosek") TextButton(onClick = { onPdf(id) }) { Text("PDF") }
                    // §22.10: załącznik dołączony do ręcznie dodanego urlopu (PDF/JPG).
                    if (r.zrodlo == "reczny" && r.maZalacznik) {
                        TextButton(onClick = { onAttachment(id) }) { Text("Załącznik") }
                    }
                    TextButton(onClick = { onDelete(id) }) {
                        Text("Usuń", color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        }
    }
}
