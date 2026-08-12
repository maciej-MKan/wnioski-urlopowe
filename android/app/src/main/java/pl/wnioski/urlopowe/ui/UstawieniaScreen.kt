package pl.wnioski.urlopowe.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import pl.wnioski.urlopowe.data.AppContainer
import pl.wnioski.urlopowe.data.RegistryTypeDto

/**
 * Ustawienia (§20.6) — cała konfiguracja w jednym miejscu: profil (dane domyślne wniosków)
 * oraz przysługujące limity na dany rok. Podgląd wykorzystania jest osobno, w Saldzie.
 */
@Composable
fun UstawieniaScreen(container: AppContainer, onBack: () -> Unit) {
    val profileVm: ProfileViewModel = viewModel(
        factory = viewModelFactory { initializer { ProfileViewModel(container.applications) } }
    )
    val settingsVm: BalanceViewModel = viewModel(
        factory = viewModelFactory { initializer { BalanceViewModel(container.settings) } }
    )
    val accountVm: AccountViewModel = viewModel(
        factory = viewModelFactory { initializer { AccountViewModel(container.auth) } }
    )
    val profile by profileVm.state.collectAsStateWithLifecycle()
    val settings by settingsVm.state.collectAsStateWithLifecycle()
    val account by accountVm.state.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { settingsVm.load() }

    Column(modifier = Modifier.fillMaxSize().safeDrawingPadding().padding(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            TextButton(onClick = onBack) { Text("‹ Kalendarz") }
            Text("Ustawienia", style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold, modifier = Modifier.padding(start = 8.dp))
        }

        if (profile.loading || settings.loading) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp))
        }

        Column(
            modifier = Modifier.fillMaxWidth().verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            ProfileSection(profileVm, profile)
            HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
            SettingsSection(settingsVm, settings)
            HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))
            AccountSection(accountVm, account)
        }
    }
}

/** §23.2: zmiana hasła. */
@Composable
private fun AccountSection(vm: AccountViewModel, state: AccountState) {
    Text("Konto", fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 4.dp))
    Text("Zmiana hasła", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    OutlinedTextField(
        value = state.current, onValueChange = vm::setCurrent,
        label = { Text("Obecne hasło") }, singleLine = true,
        visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
            keyboardType = androidx.compose.ui.text.input.KeyboardType.Password),
        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
    )
    OutlinedTextField(
        value = state.new, onValueChange = vm::setNew,
        label = { Text("Nowe hasło") }, singleLine = true,
        visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
            keyboardType = androidx.compose.ui.text.input.KeyboardType.Password),
        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
    )
    OutlinedTextField(
        value = state.repeat, onValueChange = vm::setRepeat,
        label = { Text("Powtórz nowe hasło") }, singleLine = true,
        visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
            keyboardType = androidx.compose.ui.text.input.KeyboardType.Password),
        modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
    )
    state.error?.let {
        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 4.dp))
    }
    if (state.done) {
        Text("Hasło zmienione.", color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 4.dp))
    }
    Button(onClick = vm::changePassword, enabled = !state.submitting,
        modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) {
        Text(if (state.submitting) "Zapisywanie…" else "Zmień hasło")
    }
}

@Composable
private fun ProfileSection(vm: ProfileViewModel, state: ProfileState) {
    Text("Mój profil", fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 4.dp))
    Text(
        "Domyślne dane wstawiane do wniosków.",
        fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    state.error?.let {
        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 4.dp))
    }
    if (!state.loading) {
        state.fields.forEach { f ->
            FormField(f, state.values[f.name] ?: "", f.hint) { v -> vm.setValue(f.name, v) }
        }
        Button(onClick = vm::save, enabled = !state.saving, modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) {
            Text(if (state.saving) "Zapisywanie…" else "Zapisz profil")
        }
        state.savedMessage?.let {
            Text(it, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 4.dp))
        }
    }
}

@Composable
private fun SettingsSection(vm: BalanceViewModel, state: BalanceState) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Text("Przysługujące limity", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
        TextButton(onClick = vm::prevYear) { Text("‹") }
        Text(state.year.toString(), fontWeight = FontWeight.Bold)
        TextButton(onClick = vm::nextYear) { Text("›") }
    }
    state.error?.let {
        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(vertical = 4.dp))
    }

    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "System jednozmianowy pon–pt (dolicz dni wolne za święta w sobotę)",
                modifier = Modifier.weight(1f),
            )
            Switch(checked = state.singleShift, onCheckedChange = vm::setSingleShift)
        }
    }

    state.types.forEach { t ->
        if (t.id == "wolne_za_swieta" || !t.generowalny) return@forEach
        if (t.maZalegly) PoolTypeCard(t, state, vm) else CheckboxTypeCard(t, state, vm)
    }

    Button(onClick = vm::save, enabled = !state.saving, modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) {
        Text(if (state.saving) "Zapisywanie…" else "Zapisz limity")
    }
    state.savedMessage?.let {
        Text(it, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 4.dp))
    }
}

@Composable
private fun PoolTypeCard(t: RegistryTypeDto, state: BalanceState, vm: BalanceViewModel) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(t.nazwa, fontWeight = FontWeight.Medium)
            OutlinedTextField(
                value = state.limits[t.id] ?: "",
                onValueChange = { vm.setLimit(t.id, it) },
                label = { Text("Dni przysługujące w roku") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = state.carried[t.id] ?: "",
                onValueChange = { vm.setCarried(t.id, it) },
                label = { Text("Zaległy z poprzedniego roku (dni)") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun CheckboxTypeCard(t: RegistryTypeDto, state: BalanceState, vm: BalanceViewModel) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(t.nazwa, fontWeight = FontWeight.Medium)
                t.limitDomyslny?.takeIf { it.isNotBlank() }?.let {
                    Text("Przysługuje: $it", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Switch(checked = state.active[t.id] ?: false, onCheckedChange = { vm.setActive(t.id, it) })
        }
    }
}
