package pl.wnioski.urlopowe.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import pl.wnioski.urlopowe.data.AppContainer
import pl.wnioski.urlopowe.data.FieldDto
import pl.wnioski.urlopowe.data.FieldOptionDto

private val STATUS_OPCJE = listOf(
    FieldOptionDto("zaakceptowany", "zaakceptowany"),
    FieldOptionDto("do_akceptacji", "do akceptacji"),
)

@Composable
fun ManualScreen(
    container: AppContainer,
    prefillFrom: String?,
    prefillTo: String?,
    onBack: () -> Unit,
    onDone: () -> Unit,
) {
    // Świeży klucz przy każdym wejściu → nowa instancja VM (bez dziedziczenia stanu `done` z
    // poprzedniego dodania — analogicznie do §20.5 w CreateScreen).
    val vmKey = remember { java.util.UUID.randomUUID().toString() }
    val vm: ManualViewModel = viewModel(
        key = vmKey,
        factory = viewModelFactory {
            initializer { ManualViewModel(container.applications, prefillFrom, prefillTo) }
        }
    )
    val state by vm.state.collectAsStateWithLifecycle()

    Column(modifier = Modifier.fillMaxSize().safeDrawingPadding().padding(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            TextButton(onClick = onBack) { Text("‹ Kalendarz") }
            Text("Dodaj ręcznie", style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold, modifier = Modifier.padding(start = 8.dp))
        }

        if (state.loading) LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp))
        state.error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 4.dp))
        }

        if (state.done) {
            Card(modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) {
                Column(modifier = Modifier.fillMaxWidth().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Dodano urlop do kalendarza.", fontWeight = FontWeight.Medium)
                    Button(onClick = onDone, modifier = Modifier.fillMaxWidth()) { Text("Wróć do kalendarza") }
                }
            }
            return@Column
        }

        if (!state.loading) {
            val typOpcje = state.types.map { FieldOptionDto(it.id, it.nazwa) }
            Column(modifier = Modifier.fillMaxWidth().weight(1f).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp)) {

                FormField(FieldDto("typ", "Rodzaj", "select", opcje = typOpcje), state.typ, "") { vm.setTyp(it) }
                FormField(FieldDto("data_od", "Data od", "date"), state.dataOd, "") { vm.setDataOd(it) }
                FormField(FieldDto("data_do", "Data do", "date"), state.dataDo, "") { vm.setDataDo(it) }
                FormField(
                    FieldDto("wymiar", "Wymiar (opieka: godziny)", "text", placeholder = "np. 8"),
                    state.wymiar, "",
                ) { vm.setWymiar(it) }
                FormField(FieldDto("status", "Status", "select", opcje = STATUS_OPCJE), state.status, "") {
                    vm.setStatus(it)
                }
            }

            Button(
                onClick = vm::submit,
                enabled = !state.submitting && state.typ.isNotEmpty(),
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            ) { Text(if (state.submitting) "Dodawanie…" else "Dodaj") }
        }
    }
}
