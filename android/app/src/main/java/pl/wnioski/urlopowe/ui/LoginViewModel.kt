package pl.wnioski.urlopowe.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import pl.wnioski.urlopowe.data.AuthRepository
import retrofit2.HttpException

enum class LoginMode { LOGIN, REGISTER }

data class LoginState(
    val username: String = "",
    val password: String = "",
    val mode: LoginMode = LoginMode.LOGIN,
    val canRegister: Boolean = false,
    val hasGoogle: Boolean = false,
    val loading: Boolean = false,
    val error: String? = null,
    val success: Boolean = false,
)

class LoginViewModel(private val auth: AuthRepository) : ViewModel() {

    private val _state = MutableStateFlow(LoginState())
    val state: StateFlow<LoginState> = _state.asStateFlow()

    init { loadHealth() }

    private fun loadHealth() {
        viewModelScope.launch {
            try {
                val h = auth.health()
                _state.update { it.copy(canRegister = h.rejestracja, hasGoogle = h.google) }
            } catch (e: Exception) {
                // brak health = zostaw domyślne (tylko logowanie hasłem)
            }
        }
    }

    fun onUsername(v: String) = _state.update { it.copy(username = v, error = null) }
    fun onPassword(v: String) = _state.update { it.copy(password = v, error = null) }

    fun toggleMode() = _state.update {
        it.copy(mode = if (it.mode == LoginMode.LOGIN) LoginMode.REGISTER else LoginMode.LOGIN, error = null)
    }

    fun submit() {
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
                _state.update { it.copy(loading = false, error = messageFor(s.mode, e)) }
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
