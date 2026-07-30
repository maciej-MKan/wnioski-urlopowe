package pl.wnioski.urlopowe.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import pl.wnioski.urlopowe.data.AppContainer
import pl.wnioski.urlopowe.data.FieldDto
import java.time.LocalDate

@Composable
fun CreateScreen(
    container: AppContainer,
    prefillFrom: String?,
    prefillTo: String?,
    onBack: () -> Unit,
    onDone: () -> Unit,
) {
    val vm: CreateViewModel = viewModel(
        factory = viewModelFactory {
            initializer { CreateViewModel(container.applications, prefillFrom, prefillTo) }
        }
    )
    val state by vm.state.collectAsStateWithLifecycle()
    val downloadPdf = rememberPdfDownloader { id -> container.calendar.pdfBytes(id) }

    Column(modifier = Modifier.fillMaxSize().safeDrawingPadding().padding(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            TextButton(onClick = onBack) { Text("‹ Kalendarz") }
            Text("Nowy wniosek", style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold, modifier = Modifier.padding(start = 8.dp))
        }

        if (state.loading) LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp))
        state.error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 4.dp))
        }

        if (state.done) {
            SuccessBox(state.successMessage ?: "Zapisano.", state.created, onDone) { w ->
                downloadPdf(w.id ?: return@SuccessBox, w.nazwaPliku)
            }
            return@Column
        }

        if (!state.loading) {
            // Wybór typu wniosku
            Row(modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                state.types.forEach { t ->
                    FilterChip(
                        selected = t.id == state.activeType,
                        onClick = { vm.selectType(t.id) },
                        label = { Text(t.nazwa) },
                    )
                }
            }

            Column(modifier = Modifier.fillMaxWidth().weight(1f).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp)) {

                Text("Dane wniosku", fontWeight = FontWeight.Medium)
                state.visibleFields.forEach { f ->
                    FormField(f, state.fieldValues[f.name] ?: "", autoHint(f, state.fieldValues)) { v ->
                        vm.setField(f.name, v)
                    }
                }

                Text("Dane wspólne", fontWeight = FontWeight.Medium, modifier = Modifier.padding(top = 8.dp))
                state.common.forEach { f ->
                    FormField(f, state.commonValues[f.name] ?: "", f.hint) { v -> vm.setCommon(f.name, v) }
                }

                Spacer(Modifier.height(8.dp))
            }

            Button(
                onClick = vm::submit,
                enabled = !state.submitting,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            ) { Text(if (state.submitting) "Zapisywanie…" else "Utwórz wniosek") }
        }
    }

    state.weekendPrompt?.let { prompt ->
        WeekendDialog(prompt, onConfirm = vm::confirmWeekend, onDismiss = vm::cancelWeekend)
    }
}

/** Podpowiedź „N dni kalendarzowych" dla pól auto_z_zakresu z pustą wartością. */
private fun autoHint(field: FieldDto, values: Map<String, String>): String {
    if (!field.autoZZakresu) return field.hint
    if (!(values[field.name] ?: "").isBlank()) return field.hint
    val od = values["data_od"]; val doo = values["data_do"]
    if (od.isNullOrBlank() || doo.isNullOrBlank()) return field.hint
    return try {
        val d = java.time.temporal.ChronoUnit.DAYS.between(LocalDate.parse(od), LocalDate.parse(doo)) + 1
        if (d > 0) "Zakres obejmuje $d dni kalendarzowych." else field.hint
    } catch (e: Exception) { field.hint }
}

@Composable
private fun SuccessBox(
    message: String,
    created: List<pl.wnioski.urlopowe.data.CreatedApplicationDto>,
    onDone: () -> Unit,
    onPdf: (pl.wnioski.urlopowe.data.CreatedApplicationDto) -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(message, fontWeight = FontWeight.Medium)
            created.filter { it.id != null }.forEach { w ->
                androidx.compose.material3.OutlinedButton(
                    onClick = { onPdf(w) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Pobierz PDF" + if (created.size > 1) " — ${w.typ}" else "") }
            }
            Button(onClick = onDone, modifier = Modifier.fillMaxWidth()) { Text("Wróć do kalendarza") }
        }
    }
}

@Composable
private fun WeekendDialog(prompt: WeekendPrompt, onConfirm: (Int) -> Unit, onDismiss: () -> Unit) {
    var text by remember { mutableStateOf("0") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Dzień wolny za święto") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "Twój urlop obejmuje ${prompt.dniRobocze} dni roboczych, a masz jeszcze " +
                        "${prompt.pozostalo} dni wolnych za święto (sobota) do wykorzystania w ${prompt.okres}. " +
                        "Możesz część z nich przeznaczyć na ten okres — powstanie osobny wniosek (nie schodzi z urlopu)."
                )
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it.filter(Char::isDigit) },
                    label = { Text("Liczba dni (0–${prompt.maxK})") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                val k = (text.toIntOrNull() ?: 0).coerceIn(0, prompt.maxK)
                onConfirm(k)
            }) { Text("Utwórz") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Anuluj") } },
    )
}
