package pl.wnioski.urlopowe.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import pl.wnioski.urlopowe.data.ApplicationRepository
import pl.wnioski.urlopowe.data.CreatedApplicationDto
import pl.wnioski.urlopowe.data.FieldDto
import pl.wnioski.urlopowe.data.RegistryDto
import pl.wnioski.urlopowe.data.RegistryTypeDto
import java.time.LocalDate
import java.time.Year

/** Dialog §15: propozycja rozliczenia dni wolnych za święto (sobota) na dany okres. */
data class WeekendPrompt(val maxK: Int, val dniRobocze: Int, val pozostalo: Int, val okres: String)

data class CreateState(
    val loading: Boolean = true,
    val submitting: Boolean = false,
    val error: String? = null,
    val done: Boolean = false,
    val successMessage: String? = null,
    val created: List<CreatedApplicationDto> = emptyList(),
    val types: List<RegistryTypeDto> = emptyList(),
    val common: List<FieldDto> = emptyList(),
    val activeType: String = "",
    val commonValues: Map<String, String> = emptyMap(),
    val fieldValues: Map<String, String> = emptyMap(),
    val visibleFields: List<FieldDto> = emptyList(),
    val weekendPrompt: WeekendPrompt? = null,
)

private val MIESIACE_DOP = listOf(
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
)

class CreateViewModel(
    private val repo: ApplicationRepository,
    private val prefillFrom: String? = null,
    private val prefillTo: String? = null,
    private val year: Int = Year.now().value,
) : ViewModel() {

    private val _state = MutableStateFlow(CreateState())
    val state: StateFlow<CreateState> = _state.asStateFlow()

    private var registry: RegistryDto? = null
    private val commonValues = mutableMapOf<String, String>()
    private val byType = mutableMapOf<String, MutableMap<String, String>>()

    init { load() }

    private fun load() {
        viewModelScope.launch {
            try {
                val reg = repo.registry(year)
                registry = reg
                var types = reg.typy.filter { it.aktywny && it.generowalny }
                if (types.isEmpty()) types = reg.typy

                reg.wspolne.forEach { f -> commonValues[f.name] = f.domyslna }
                // §19: nadpisz danymi z profilu użytkownika (poza „data" — to data sporządzenia).
                val prof = runCatching { repo.profile() }.getOrDefault(emptyMap())
                reg.wspolne.forEach { f ->
                    if (f.name != "data") prof[f.name]?.takeIf { it.isNotBlank() }?.let { commonValues[f.name] = it }
                }
                if (commonValues["data"].isNullOrBlank()) commonValues["data"] = LocalDate.now().toString()

                types.forEach { t ->
                    val m = byType.getOrPut(t.id) { mutableMapOf() }
                    t.pola.forEach { f -> m[f.name] = f.domyslna }
                    if (!prefillFrom.isNullOrBlank() && m.containsKey("data_od")) m["data_od"] = prefillFrom
                    if (!prefillTo.isNullOrBlank() && m.containsKey("data_do")) m["data_do"] = prefillTo
                }
                push(types, types.first().id)
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = "Nie udało się wczytać formularza.") }
            }
        }
    }

    private fun push(types: List<RegistryTypeDto>, active: String) {
        val reg = registry ?: return
        val type = types.firstOrNull { it.id == active } ?: return
        val values = byType[active] ?: emptyMap()
        val visible = type.pola.filter { f ->
            val w = f.widoczneGdy ?: return@filter true
            values[w.pole] == w.wartosc
        }
        _state.update {
            it.copy(
                loading = false, types = types, common = reg.wspolne, activeType = active,
                commonValues = commonValues.toMap(), fieldValues = values.toMap(), visibleFields = visible,
                error = null,
            )
        }
    }

    fun selectType(id: String) = push(_state.value.types, id)

    fun setCommon(name: String, v: String) {
        commonValues[name] = v
        push(_state.value.types, _state.value.activeType)
    }

    fun setField(name: String, v: String) {
        byType.getOrPut(_state.value.activeType) { mutableMapOf() }[name] = v
        push(_state.value.types, _state.value.activeType)
    }

    fun submit() {
        viewModelScope.launch {
            val prompt = computeWeekendPrompt()
            if (prompt != null) {
                _state.update { it.copy(weekendPrompt = prompt) }
            } else {
                doCreate(0)
            }
        }
    }

    fun cancelWeekend() = _state.update { it.copy(weekendPrompt = null) }

    fun confirmWeekend(k: Int) {
        _state.update { it.copy(weekendPrompt = null) }
        viewModelScope.launch { doCreate(k) }
    }

    /** §15/§16.1: policz sugerowaną liczbę dni wolnych za święto dla urlopu wypoczynkowego. */
    private suspend fun computeWeekendPrompt(): WeekendPrompt? {
        if (_state.value.activeType != "wypoczynkowy") return null
        val vals = byType["wypoczynkowy"] ?: return null
        val od = vals["data_od"]; val doo = vals["data_do"]
        if (od.isNullOrBlank() || doo.isNullOrBlank() || doo.length < 7) return null
        return try {
            val rok = doo.substring(0, 4).toInt()
            val miesiac = doo.substring(5, 7).toInt()
            val poz = repo.balance(rok).firstOrNull { it.krotkiTermin && it.miesiac == miesiac }
            val pozostalo = poz?.pozostalo ?: 0.0
            val dniRobocze = repo.workingDays(od, doo)
            val maxK = minOf(pozostalo, dniRobocze).toInt()
            if (maxK <= 0) null
            else WeekendPrompt(maxK, dniRobocze.toInt(), pozostalo.toInt(), "${MIESIACE_DOP[miesiac - 1]} $rok")
        } catch (e: Exception) {
            null  // brak podpowiedzi = zwykły pojedynczy wniosek
        }
    }

    private suspend fun doCreate(weekendDays: Int) {
        _state.update { it.copy(submitting = true, error = null) }
        try {
            val payload = buildMap {
                put("typ", _state.value.activeType)
                commonValues.forEach { (k, v) -> put(k, v) }
                (byType[_state.value.activeType] ?: emptyMap()).forEach { (k, v) -> put(k, v) }
                if (weekendDays > 0) put("dni_za_swieto", weekendDays.toString())
            }
            val resp = repo.create(payload)
            val msg = if (resp.wnioski.size > 1)
                "Dodano 2 wnioski (urlop + dzień wolny za święto)."
            else "Dodano wniosek do kalendarza."
            _state.update {
                it.copy(submitting = false, done = true, successMessage = msg, created = resp.wnioski)
            }
        } catch (e: Exception) {
            _state.update { it.copy(submitting = false, error = "Nie udało się zapisać wniosku.") }
        }
    }
}
