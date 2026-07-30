package pl.wnioski.urlopowe.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import pl.wnioski.urlopowe.data.BalanceItemDto
import pl.wnioski.urlopowe.data.EntitlementPatch
import pl.wnioski.urlopowe.data.RegistryTypeDto
import pl.wnioski.urlopowe.data.SettingsRepository
import java.time.Year

data class BalanceState(
    val year: Int,
    val loading: Boolean = false,
    val saving: Boolean = false,
    val error: String? = null,
    val savedMessage: String? = null,
    val items: List<BalanceItemDto> = emptyList(),
    val types: List<RegistryTypeDto> = emptyList(),   // metadane do formularza ustawień
    val singleShift: Boolean = false,
    // edytowalne wartości uprawnień, klucz = id typu
    val limits: Map<String, String> = emptyMap(),      // limit_dni (typy z pulą)
    val carried: Map<String, String> = emptyMap(),     // bilans_z_przeniesienia (typy z pulą)
    val active: Map<String, Boolean> = emptyMap(),      // aktywny (typy „checkbox")
)

class BalanceViewModel(
    private val repo: SettingsRepository,
    initialYear: Int = Year.now().value,
) : ViewModel() {

    private val _state = MutableStateFlow(BalanceState(year = initialYear))
    val state: StateFlow<BalanceState> = _state.asStateFlow()

    init { load() }

    fun prevYear() { _state.update { it.copy(year = it.year - 1, savedMessage = null) }; load() }
    fun nextYear() { _state.update { it.copy(year = it.year + 1, savedMessage = null) }; load() }

    fun load() {
        val year = _state.value.year
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val items = repo.balance(year)
                val settings = repo.settings(year)
                val types = repo.registry(year).typy
                val byId = settings.uprawnienia.associateBy { it.typ }

                val limits = mutableMapOf<String, String>()
                val carried = mutableMapOf<String, String>()
                val active = mutableMapOf<String, Boolean>()
                types.forEach { t ->
                    val e = byId[t.id]
                    if (t.id != "wolne_za_swieta" && t.generowalny) {
                        if (t.maZalegly) {
                            limits[t.id] = numToText(e?.limitDni)
                            carried[t.id] = numToText(e?.bilansZPrzeniesienia)
                        } else {
                            active[t.id] = e?.aktywny ?: false
                        }
                    }
                }
                _state.update {
                    it.copy(
                        loading = false, items = items, types = types,
                        singleShift = settings.jednozmianowy,
                        limits = limits, carried = carried, active = active,
                    )
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = "Nie udało się wczytać salda.") }
            }
        }
    }

    fun setLimit(typ: String, v: String) =
        _state.update { it.copy(limits = it.limits + (typ to v.filter { c -> c.isDigit() }), savedMessage = null) }

    fun setCarried(typ: String, v: String) =
        _state.update { it.copy(carried = it.carried + (typ to v.filter { c -> c.isDigit() }), savedMessage = null) }

    fun setActive(typ: String, on: Boolean) =
        _state.update { it.copy(active = it.active + (typ to on), savedMessage = null) }

    fun setSingleShift(on: Boolean) =
        _state.update { it.copy(singleShift = on, savedMessage = null) }

    fun save() {
        val s = _state.value
        _state.update { it.copy(saving = true, error = null, savedMessage = null) }
        viewModelScope.launch {
            try {
                val body = buildMap {
                    s.types.forEach { t ->
                        if (t.id == "wolne_za_swieta" || !t.generowalny) return@forEach
                        if (t.maZalegly) {
                            put(t.id, EntitlementPatch(
                                aktywny = true,
                                limitDni = s.limits[t.id]?.ifBlank { null },
                                bilansZPrzeniesienia = s.carried[t.id]?.ifBlank { null },
                            ))
                        } else {
                            put(t.id, EntitlementPatch(aktywny = s.active[t.id] ?: false))
                        }
                    }
                    put("wolne_za_swieta", EntitlementPatch(aktywny = s.singleShift))
                }
                repo.saveSettings(s.year, body)
                _state.update { it.copy(saving = false, savedMessage = "Zapisano ustawienia.") }
                load()  // odśwież saldo i limity po zapisie
            } catch (e: Exception) {
                _state.update { it.copy(saving = false, error = "Nie udało się zapisać ustawień.") }
            }
        }
    }

    private companion object {
        fun numToText(d: Double?): String =
            if (d == null) "" else if (d % 1.0 == 0.0) d.toInt().toString() else d.toString()
    }
}
