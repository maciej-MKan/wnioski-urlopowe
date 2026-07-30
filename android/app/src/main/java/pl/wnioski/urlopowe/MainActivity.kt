package pl.wnioski.urlopowe

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.runtime.remember
import pl.wnioski.urlopowe.data.AppContainer
import pl.wnioski.urlopowe.ui.BalanceScreen
import pl.wnioski.urlopowe.ui.CalendarScreen
import pl.wnioski.urlopowe.ui.CreateScreen
import pl.wnioski.urlopowe.ui.LoginScreen
import pl.wnioski.urlopowe.ui.ManualScreen
import pl.wnioski.urlopowe.ui.ProfileScreen

class MainActivity : ComponentActivity() {
    // Token przyniesiony deep linkiem z logowania Google (odczytany przez App).
    private var pendingToken by mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        pendingToken = tokenFromIntent(intent)
        val container = AppContainer(applicationContext)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    App(container, pendingToken) { pendingToken = null }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        tokenFromIntent(intent)?.let { pendingToken = it }
    }

    /** Wyłuskuje token z `pl.wnioski.urlopowe://auth#token=...` (fragment nie idzie na serwer). */
    private fun tokenFromIntent(intent: Intent?): String? {
        val data: Uri = intent?.takeIf { it.action == Intent.ACTION_VIEW }?.data ?: return null
        if (data.scheme != "pl.wnioski.urlopowe") return null
        val fragment = data.fragment ?: return null
        return fragment.split('&')
            .firstOrNull { it.startsWith("token=") }
            ?.removePrefix("token=")
            ?.takeIf { it.isNotBlank() }
    }
}

/** Prosty stan nawigacji (bez lib Navigation — 3 ekrany). */
private sealed interface Nav {
    data object Calendar : Nav
    data class Balance(val year: Int) : Nav
    data class Create(val from: String?, val to: String?) : Nav
    data class Manual(val from: String?, val to: String?) : Nav
    data object Profile : Nav
}

@Composable
fun App(container: AppContainer, pendingToken: String? = null, onTokenConsumed: () -> Unit = {}) {
    var loggedIn by rememberSaveable { mutableStateOf(container.auth.isLoggedIn()) }
    var nav by remember { mutableStateOf<Nav>(Nav.Calendar) }

    // Deep link z logowania Google — zapisz token i wejdź do aplikacji.
    LaunchedEffect(pendingToken) {
        if (pendingToken != null) {
            container.auth.acceptToken(pendingToken)
            nav = Nav.Calendar
            loggedIn = true
            onTokenConsumed()
        }
    }

    if (!loggedIn) {
        LoginScreen(container, onLoggedIn = { loggedIn = true })
        return
    }
    when (val n = nav) {
        Nav.Calendar -> CalendarScreen(
            container,
            onLogout = { container.auth.logout(); nav = Nav.Calendar; loggedIn = false },
            onOpenBalance = { nav = Nav.Balance(it) },
            onCreate = { from, to -> nav = Nav.Create(from, to) },
            onManual = { from, to -> nav = Nav.Manual(from, to) },
            onProfile = { nav = Nav.Profile },
        )
        is Nav.Balance -> BalanceScreen(container, initialYear = n.year, onBack = { nav = Nav.Calendar })
        is Nav.Create -> CreateScreen(
            container, prefillFrom = n.from, prefillTo = n.to,
            onBack = { nav = Nav.Calendar }, onDone = { nav = Nav.Calendar },
        )
        is Nav.Manual -> ManualScreen(
            container, prefillFrom = n.from, prefillTo = n.to,
            onBack = { nav = Nav.Calendar }, onDone = { nav = Nav.Calendar },
        )
        Nav.Profile -> ProfileScreen(container, onBack = { nav = Nav.Calendar })
    }
}
