package pl.wnioski.urlopowe.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Odpowiedzi API. Klucze JSON są polskie/wire (§12) — mapujemy `@SerialName` gdzie snake_case. */

@Serializable
data class TokenResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("token_type") val tokenType: String = "bearer",
)

@Serializable
data class Me(val id: Int, val username: String)

@Serializable
data class RegisterRequest(val username: String, val password: String)

@Serializable
data class HealthResponse(
    val srodowisko: String = "prod",
    val rejestracja: Boolean = false,
    val google: Boolean = false,
)

@Serializable
data class LeaveTypeDto(
    val id: String,
    val nazwa: String,
    val kolor: String,
)

@Serializable
data class TypesResponse(
    val typy: List<LeaveTypeDto> = emptyList(),
)

@Serializable
data class RecordDto(
    val id: Int? = null,
    val typ: String,
    val status: String,
    val zrodlo: String = "wniosek",
    @SerialName("data_od") val dataOd: String? = null,
    @SerialName("data_do") val dataDo: String? = null,
    @SerialName("dni_robocze") val dniRobocze: Double? = null,
    val godziny: Double? = null,
    @SerialName("ma_zalacznik") val maZalacznik: Boolean = false,
    @SerialName("korekta_powod") val korektaPowod: String? = null,
)

@Serializable
data class HolidayDto(
    val data: String,
    val nazwa: String,
)

@Serializable
data class StatusRequest(val status: String)

@Serializable
data class BalanceItemDto(
    val typ: String,
    val etykieta: String,
    val jednostka: String,
    val limit: Double = 0.0,
    val wykorzystano: Double = 0.0,
    val zaplanowano: Double = 0.0,
    val pozostalo: Double = 0.0,
    @SerialName("krotki_termin") val krotkiTermin: Boolean = false,
    val miesiac: Int? = null,
)

@Serializable
data class EntitlementDto(
    val typ: String,
    val aktywny: Boolean = false,
    @SerialName("limit_dni") val limitDni: Double? = null,
    @SerialName("limit_godzin") val limitGodzin: Double? = null,
    @SerialName("bilans_z_przeniesienia") val bilansZPrzeniesienia: Double? = null,
    val uwagi: String = "",
)

@Serializable
data class SettingsResponse(
    val rok: Int,
    val uprawnienia: List<EntitlementDto> = emptyList(),
    val jednozmianowy: Boolean = false,
)

/** Wpis zapisu ustawień roku (PUT /api/ustawienia). Pola null są pomijane (backend bierze domyślne). */
@Serializable
data class EntitlementPatch(
    val aktywny: Boolean? = null,
    @SerialName("limit_dni") val limitDni: String? = null,
    @SerialName("bilans_z_przeniesienia") val bilansZPrzeniesienia: String? = null,
)

// --- Rejestr formularza wniosków (§ dynamiczny formularz) ---

@Serializable
data class FieldOptionDto(val value: String, val label: String)

@Serializable
data class VisibleWhenDto(val pole: String, val wartosc: String)

@Serializable
data class FieldDto(
    val name: String,
    val label: String,
    @SerialName("typ_pola") val typPola: String = "text",
    val placeholder: String = "",
    val hint: String = "",
    val szerokosc: String = "full",
    val domyslna: String = "",
    @SerialName("auto_z_zakresu") val autoZZakresu: Boolean = false,
    val opcje: List<FieldOptionDto> = emptyList(),
    @SerialName("widoczne_gdy") val widoczneGdy: VisibleWhenDto? = null,
)

@Serializable
data class RegistryTypeDto(
    val id: String,
    val nazwa: String,
    @SerialName("zakladka_opis") val zakladkaOpis: String = "",
    val uwaga: String = "",
    val kolor: String = "",
    val aktywny: Boolean = true,
    val generowalny: Boolean = true,
    @SerialName("ma_zalegly") val maZalegly: Boolean = false,
    @SerialName("limit_domyslny") val limitDomyslny: String? = null,
    val pola: List<FieldDto> = emptyList(),
)

@Serializable
data class RegistryDto(
    val wspolne: List<FieldDto> = emptyList(),
    val typy: List<RegistryTypeDto> = emptyList(),
)

@Serializable
data class CreatedApplicationDto(
    val id: Int? = null,
    @SerialName("nazwa_pliku") val nazwaPliku: String = "",
    val typ: String = "",
)

@Serializable
data class CreateApplicationsResponse(
    val wnioski: List<CreatedApplicationDto> = emptyList(),
)

@Serializable
data class WorkingDaysResponse(
    @SerialName("dni_robocze") val dniRobocze: Double = 0.0,
)
