package pl.wnioski.urlopowe.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import pl.wnioski.urlopowe.data.ApplicationRepository
import pl.wnioski.urlopowe.data.FieldDto
import java.time.Year

data class ProfileState(
    val loading: Boolean = true,
    val saving: Boolean = false,
    val error: String? = null,
    val savedMessage: String? = null,
    val fields: List<FieldDto> = emptyList(),
    val values: Map<String, String> = emptyMap(),
)

/** Profil użytkownika: domyślne dane wspólne (imię/nazwisko, stanowisko, pracodawca…) w bazie (§19). */
class ProfileViewModel(
    private val repo: ApplicationRepository,
    private val year: Int = Year.now().value,
) : ViewModel() {

    private val _state = MutableStateFlow(ProfileState())
    val state: StateFlow<ProfileState> = _state.asStateFlow()

    private val values = mutableMapOf<String, String>()

    init { load() }

    private fun load() {
        viewModelScope.launch {
            try {
                // Pola wspólne z rejestru — bez „data" (data sporządzenia jest per-wniosek).
                val fields = repo.registry(year).wspolne.filter { it.name != "data" }
                val saved = runCatching { repo.profile() }.getOrDefault(emptyMap())
                fields.forEach { f -> values[f.name] = saved[f.name] ?: f.domyslna }
                _state.update { it.copy(loading = false, fields = fields, values = values.toMap()) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = "Nie udało się wczytać profilu.") }
            }
        }
    }

    fun setValue(name: String, v: String) {
        values[name] = v
        _state.update { it.copy(values = values.toMap(), savedMessage = null) }
    }

    fun save() {
        _state.update { it.copy(saving = true, error = null, savedMessage = null) }
        viewModelScope.launch {
            try {
                val saved = repo.saveProfile(values.toMap())
                values.clear(); values.putAll(saved)
                _state.update {
                    it.copy(saving = false, values = values.toMap(), savedMessage = "Zapisano profil.")
                }
            } catch (e: Exception) {
                _state.update { it.copy(saving = false, error = "Nie udało się zapisać profilu.") }
            }
        }
    }
}
