package pl.wnioski.urlopowe.ui

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import pl.wnioski.urlopowe.BuildConfig
import pl.wnioski.urlopowe.data.AppContainer

@Composable
fun LoginScreen(container: AppContainer, onLoggedIn: () -> Unit) {
    val vm: LoginViewModel = viewModel(
        factory = viewModelFactory { initializer { LoginViewModel(container.auth) } }
    )
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current

    LaunchedEffect(state.success) { if (state.success) onLoggedIn() }

    val isRegister = state.mode == LoginMode.REGISTER

    Column(
        modifier = Modifier.fillMaxSize().safeDrawingPadding().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Wnioski urlopowe", style = MaterialTheme.typography.headlineMedium)
        Text(if (isRegister) "Załóż konto" else "Zaloguj się", style = MaterialTheme.typography.bodyMedium)

        OutlinedTextField(
            value = state.username,
            onValueChange = vm::onUsername,
            label = { Text("Użytkownik") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(top = 20.dp),
        )
        OutlinedTextField(
            value = state.password,
            onValueChange = vm::onPassword,
            label = { Text("Hasło") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        )
        state.error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 10.dp))
        }
        Button(
            onClick = vm::submit,
            enabled = !state.loading,
            modifier = Modifier.fillMaxWidth().padding(top = 20.dp),
        ) {
            if (state.loading) CircularProgressIndicator(modifier = Modifier.padding(end = 8.dp))
            Text(if (isRegister) "Załóż konto" else "Zaloguj")
        }

        if (state.canRegister) {
            TextButton(onClick = vm::toggleMode, modifier = Modifier.padding(top = 4.dp)) {
                Text(if (isRegister) "Masz już konto? Zaloguj się" else "Nie masz konta? Załóż konto")
            }
        }

        if (state.hasGoogle) {
            OutlinedButton(
                onClick = { startGoogleLogin(context) },
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            ) { Text("Zaloguj przez Google") }
        }
    }
}

/** Otwiera flow Google w przeglądarce; backend wróci deep linkiem `pl.wnioski.urlopowe://auth#token=...`. */
private fun startGoogleLogin(context: android.content.Context) {
    val url = BuildConfig.BASE_URL.trimEnd('/') + "/api/auth/google/login?native=1"
    try {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    } catch (e: Exception) {
        Toast.makeText(context, "Nie udało się otworzyć logowania Google.", Toast.LENGTH_SHORT).show()
    }
}
