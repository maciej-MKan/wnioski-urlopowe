package pl.wnioski.urlopowe.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import pl.wnioski.urlopowe.data.ApplicationRepository
import pl.wnioski.urlopowe.data.RegistryTypeDto
import java.time.Year

data class ManualState(
    val loading: Boolean = true,
    val submitting: Boolean = false,
    val error: String? = null,
    val done: Boolean = false,
    val types: List<RegistryTypeDto> = emptyList(),
    val typ: String = "",
    val dataOd: String = "",
    val dataDo: String = "",
    val wymiar: String = "",
    val status: String = "zaakceptowany",
)

/** Ręczne dodanie urlopu (§16.2) — bez PDF, dowolny typ przysługujący w roku, wybór statusu. */
class ManualViewModel(
    private val repo: ApplicationRepository,
    prefillFrom: String? = null,
    prefillTo: String? = null,
    private val year: Int = Year.now().value,
) : ViewModel() {

    private val _state = MutableStateFlow(
        ManualState(dataOd = prefillFrom.orEmpty(), dataDo = prefillTo.orEmpty())
    )
    val state: StateFlow<ManualState> = _state.asStateFlow()

    init { load() }

    private fun load() {
        viewModelScope.launch {
            try {
                val types = repo.registry(year).typy.filter { it.aktywny }
                _state.update {
                    it.copy(loading = false, types = types, typ = types.firstOrNull()?.id ?: "")
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = "Nie udało się wczytać typów.") }
            }
        }
    }

    fun setTyp(v: String) = _state.update { it.copy(typ = v) }
    fun setDataOd(v: String) = _state.update { it.copy(dataOd = v) }
    fun setDataDo(v: String) = _state.update { it.copy(dataDo = v) }
    fun setWymiar(v: String) = _state.update { it.copy(wymiar = v) }
    fun setStatus(v: String) = _state.update { it.copy(status = v) }

    fun submit() {
        val s = _state.value
        _state.update { it.copy(submitting = true, error = null) }
        viewModelScope.launch {
            try {
                val payload = buildMap {
                    put("typ", s.typ)
                    put("status", s.status)
                    put("data_od", s.dataOd)
                    put("data_do", s.dataDo)
                    if (s.wymiar.isNotBlank()) {
                        put("wymiar", s.wymiar)
                        if (s.typ == "opieka") put("forma", "godziny")
                    }
                }
                repo.createManual(payload)
                _state.update { it.copy(submitting = false, done = true) }
            } catch (e: Exception) {
                _state.update { it.copy(submitting = false, error = "Nie udało się dodać urlopu.") }
            }
        }
    }
}
