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
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import pl.wnioski.urlopowe.data.AppContainer
import pl.wnioski.urlopowe.data.BalanceItemDto

/** Formatuje liczbę bez zbędnego „.0" dla całkowitych. */
private fun fmt(d: Double): String =
    if (d % 1.0 == 0.0) d.toInt().toString() else d.toString().trimEnd('0').trimEnd('.')

/**
 * Saldo — tylko podgląd bilansu wykorzystania (§20.6). Konfiguracja limitów/profilu jest w Ustawieniach.
 * Współdzieli `BalanceViewModel`, ale renderuje wyłącznie karty salda (bez sekcji edycji).
 */
@Composable
fun SaldoScreen(container: AppContainer, initialYear: Int, onBack: () -> Unit) {
    val vm: BalanceViewModel = viewModel(
        factory = viewModelFactory { initializer { BalanceViewModel(container.settings, initialYear) } }
    )
    val state by vm.state.collectAsStateWithLifecycle()
    // Po powrocie na ekran (np. po dodaniu urlopu) przeładuj saldo — VM jest w zakresie Activity,
    // więc `init { load() }` nie odpala się ponownie (§20.3).
    LaunchedEffect(Unit) { vm.load() }

    Column(modifier = Modifier.fillMaxSize().safeDrawingPadding().padding(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            TextButton(onClick = onBack) { Text("‹ Kalendarz") }
            Text(
                "Saldo",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f).padding(start = 8.dp),
            )
            TextButton(onClick = vm::prevYear) { Text("‹") }
            Text(state.year.toString(), fontWeight = FontWeight.Bold)
            TextButton(onClick = vm::nextYear) { Text("›") }
        }

        if (state.loading) LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp))
        state.error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 4.dp))
        }

        Column(
            modifier = Modifier.fillMaxWidth().verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("Bilans wykorzystania", fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 8.dp))
            if (!state.loading && state.items.isEmpty()) {
                Text("Brak danych salda dla roku ${state.year}.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            state.items.forEach { item -> BalanceCard(item) }
        }
    }
}

@Composable
private fun BalanceCard(item: BalanceItemDto) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
            Text(item.etykieta, fontWeight = FontWeight.Medium)
            Row(modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                Metric("Limit", item.limit, item.jednostka, Modifier.weight(1f))
                Metric("Wykorzystano", item.wykorzystano, item.jednostka, Modifier.weight(1f))
                Metric("Zaplanowano", item.zaplanowano, item.jednostka, Modifier.weight(1f))
                Metric("Pozostało", item.pozostalo, item.jednostka, Modifier.weight(1f), highlight = true)
            }
        }
    }
}

@Composable
private fun Metric(label: String, value: Double, unit: String, modifier: Modifier, highlight: Boolean = false) {
    Column(modifier = modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(label, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        Text(
            fmt(value),
            fontWeight = if (highlight) FontWeight.Bold else FontWeight.Normal,
            color = if (highlight) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
        )
        Text(unit, fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
