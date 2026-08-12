package pl.wnioski.urlopowe.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import pl.wnioski.urlopowe.data.AuthRepository
import pl.wnioski.urlopowe.data.apiErrorDetail

data class AccountState(
    val current: String = "",
    val new: String = "",
    val repeat: String = "",
    val submitting: Boolean = false,
    val error: String? = null,
    val done: Boolean = false,   // hasło zmienione
    val deleteConfirm: Boolean = false,  // §23.4: pierwsze tapnięcie „Usuń konto"
    val deleting: Boolean = false,
    val deleted: Boolean = false,        // konto usunięte → ekran wyloguje/przekieruje
)

/** §23.2: zmiana hasła zalogowanego użytkownika. */
class AccountViewModel(private val auth: AuthRepository) : ViewModel() {

    private val _state = MutableStateFlow(AccountState())
    val state: StateFlow<AccountState> = _state.asStateFlow()

    fun setCurrent(v: String) = _state.update { it.copy(current = v, error = null, done = false) }
    fun setNew(v: String) = _state.update { it.copy(new = v, error = null, done = false) }
    fun setRepeat(v: String) = _state.update { it.copy(repeat = v, error = null, done = false) }

    fun changePassword() {
        val s = _state.value
        if (s.new.isBlank()) { _state.update { it.copy(error = "Podaj nowe hasło.") }; return }
        if (s.new != s.repeat) { _state.update { it.copy(error = "Nowe hasła nie są takie same.") }; return }
        _state.update { it.copy(submitting = true, error = null, done = false) }
        viewModelScope.launch {
            try {
                auth.changePassword(s.current, s.new)
                _state.update { AccountState(done = true) }
            } catch (e: Exception) {
                val msg = apiErrorDetail(e) ?: "Nie udało się zmienić hasła."
                _state.update { it.copy(submitting = false, error = msg) }
            }
        }
    }

    /** §23.4: dwustopniowe usunięcie konta — pierwsze tapnięcie potwierdza, drugie usuwa. */
    fun deleteAccount() {
        if (!_state.value.deleteConfirm) {
            _state.update { it.copy(deleteConfirm = true, error = null) }
            return
        }
        _state.update { it.copy(deleting = true, error = null) }
        viewModelScope.launch {
            try {
                auth.deleteAccount()
                _state.update { it.copy(deleting = false, deleted = true) }
            } catch (e: Exception) {
                val msg = apiErrorDetail(e) ?: "Nie udało się usunąć konta."
                _state.update { it.copy(deleting = false, deleteConfirm = false, error = msg) }
            }
        }
    }
}
