package pl.wnioski.urlopowe.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import pl.wnioski.urlopowe.data.ApiContract
import pl.wnioski.urlopowe.data.AuthRepository
import pl.wnioski.urlopowe.data.ServerUrlStore
import pl.wnioski.urlopowe.data.normalizeServerUrl
import retrofit2.HttpException

enum class LoginMode { LOGIN, REGISTER }

/** Krok logowania: konfiguracja adresu serwera vs właściwy formularz logowania. */
enum class LoginStep { SERVER, CREDENTIALS }

data class LoginState(
    val step: LoginStep = LoginStep.SERVER,
    val serverUrl: String = "",
    val connected: Boolean = false,
    val username: String = "",
    val password: String = "",
    val mode: LoginMode = LoginMode.LOGIN,
    val canRegister: Boolean = false,
    val hasGoogle: Boolean = false,
    val loading: Boolean = false,
    val error: String? = null,
    val success: Boolean = false,
    /** Czy wersja API serwera jest zgodna z klientem. `false` → logowanie zablokowane. */
    val compatible: Boolean = true,
    /** Tryb bez logowania bez konta — pokaż wyłącznie zakładanie jedynego konta. */
    val setup: Boolean = false,
)

class LoginViewModel(
    private val auth: AuthRepository,
    private val serverUrl: ServerUrlStore,
) : ViewModel() {

    private val _state = MutableStateFlow(LoginState())
    val state: StateFlow<LoginState> = _state.asStateFlow()

    init {
        // Adres zapisany → od razu formularz logowania (sprawdź serwer w tle); brak → ekran serwera.
        val saved = serverUrl.get()
        if (saved != null) {
            _state.update { it.copy(serverUrl = saved, step = LoginStep.CREDENTIALS) }
            loadHealth()
        }
    }

    /**
     * Odpytuje serwer (health). Sukces → przechodzi do formularza logowania i odsłania rejestrację/Google.
     * Porażka → wraca na ekran serwera z komunikatem (adres niezapisany lub nie można się połączyć).
     */
    private fun loadHealth() {
        viewModelScope.launch {
            try {
                val h = auth.health()
                val compat = ApiContract.check(h.apiVersion)
                val ok = compat is ApiContract.Compatibility.Ok
                _state.update {
                    it.copy(
                        canRegister = h.rejestracja, hasGoogle = h.google, connected = true,
                        loading = false, step = LoginStep.CREDENTIALS,
                        compatible = ok,
                        error = ApiContract.message(compat),
                        // Tryb bez logowania: jedyne konto → wejdź od razu; brak konta → tylko setup.
                        success = if (ok && h.bezLogowania) true else it.success,
                        setup = ok && h.wymagaKonta,
                        mode = if (ok && h.wymagaKonta) LoginMode.REGISTER else it.mode,
                    )
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(
                        loading = false, connected = false, step = LoginStep.SERVER,
                        compatible = true, setup = false, // to problem połączenia, nie wersji
                        error = "Nie udało się połączyć z serwerem pod tym adresem.",
                    )
                }
            }
        }
    }

    fun onServerUrl(v: String) = _state.update { it.copy(serverUrl = v, connected = false, error = null) }
    fun onUsername(v: String) = _state.update { it.copy(username = v, error = null) }
    fun onPassword(v: String) = _state.update { it.copy(password = v, error = null) }

    /** Ręczne otwarcie ekranu adresu serwera („Zmień serwer"). */
    fun showServerSetup() = _state.update { it.copy(step = LoginStep.SERVER, error = null) }

    /** Normalizuje i zapisuje adres serwera. Zwraca `false` (i ustawia błąd) gdy adres niepoprawny. */
    fun persistServerUrl(): Boolean {
        val norm = normalizeServerUrl(_state.value.serverUrl)
        if (norm == null) {
            _state.update { it.copy(error = "Podaj poprawny adres serwera (np. https://twoj-serwer).") }
            return false
        }
        serverUrl.set(norm)
        _state.update { it.copy(serverUrl = norm) }
        return true
    }

    /** „Połącz": zapisuje adres i odpytuje serwer; po sukcesie przechodzi do formularza logowania. */
    fun connect() {
        if (!persistServerUrl()) return
        _state.update { it.copy(loading = true, error = null) }
        loadHealth()
    }

    fun toggleMode() = _state.update {
        it.copy(mode = if (it.mode == LoginMode.LOGIN) LoginMode.REGISTER else LoginMode.LOGIN, error = null)
    }

    fun submit() {
        if (!_state.value.compatible) return // niezgodna wersja API — logowanie zablokowane
        if (!persistServerUrl()) return
        val s = _state.value
        if (s.username.isBlank() || s.password.isBlank()) {
            _state.update { it.copy(error = "Podaj login i hasło.") }
            return
        }
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                if (s.mode == LoginMode.REGISTER) auth.register(s.username, s.password)
                else auth.login(s.username, s.password)
                _state.update { it.copy(loading = false, success = true) }
            } catch (e: Exception) {
                if (e is HttpException) {
                    // Serwer odpowiedział (np. złe hasło / zajęty login) — zostań na formularzu.
                    _state.update { it.copy(loading = false, error = messageFor(s.mode, e)) }
                } else {
                    // Brak połączenia — pokaż ekran adresu serwera.
                    _state.update {
                        it.copy(
                            loading = false, connected = false, step = LoginStep.SERVER,
                            error = "Nie udało się połączyć z serwerem pod tym adresem.",
                        )
                    }
                }
            }
        }
    }

    private fun messageFor(mode: LoginMode, e: Exception): String {
        val code = (e as? HttpException)?.code()
        return when {
            mode == LoginMode.REGISTER && code == 409 -> "Nazwa użytkownika jest już zajęta."
            mode == LoginMode.REGISTER && code == 400 -> "Nieprawidłowy login lub hasło."
            mode == LoginMode.REGISTER && code == 403 -> "Rejestracja jest wyłączona."
            mode == LoginMode.REGISTER -> "Nie udało się założyć konta (brak połączenia?)."
            else -> "Nie udało się zalogować (zły login/hasło lub brak połączenia)."
        }
    }
}
