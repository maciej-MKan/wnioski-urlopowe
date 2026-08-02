package pl.wnioski.urlopowe.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TimePicker
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberTimePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import pl.wnioski.urlopowe.data.FieldDto
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/** Etykieta pola z czerwoną gwiazdką dla pól wymaganych (§22.2). */
@Composable
private fun FieldLabel(field: FieldDto) {
    if (field.wymagane) {
        Text(buildAnnotatedString {
            append(field.label)
            withStyle(SpanStyle(color = Color(0xFFD0453B))) { append(" *") }
        })
    } else {
        Text(field.label)
    }
}

/** Renderuje pojedyncze pole rejestru zależnie od `typ_pola`. */
@Composable
fun FormField(field: FieldDto, value: String, hint: String, onChange: (String) -> Unit) {
    when (field.typPola) {
        "textarea" -> LabeledTextField(field, value, onChange, hint, singleLine = false, minLines = 3)
        "number" -> LabeledTextField(field, value, onChange, hint, keyboard = KeyboardType.Number)
        "select" -> SelectField(field, value, onChange, hint)
        "date" -> DateField(field, value, onChange, hint)
        "time" -> TimeField(field, value, onChange, hint)
        else -> LabeledTextField(field, value, onChange, hint)
    }
}

@Composable
private fun LabeledTextField(
    field: FieldDto,
    value: String,
    onChange: (String) -> Unit,
    hint: String,
    singleLine: Boolean = true,
    minLines: Int = 1,
    keyboard: KeyboardType = KeyboardType.Text,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { FieldLabel(field) },
        placeholder = { if (field.placeholder.isNotEmpty()) Text(field.placeholder) },
        supportingText = { if (hint.isNotEmpty()) Text(hint) },
        singleLine = singleLine,
        minLines = minLines,
        keyboardOptions = KeyboardOptions(keyboardType = keyboard),
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun SelectField(field: FieldDto, value: String, onChange: (String) -> Unit, hint: String) {
    var expanded by remember { mutableStateOf(false) }
    val current = field.opcje.firstOrNull { it.value == value }?.label ?: value
    Box(modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = current,
            onValueChange = {},
            readOnly = true,
            label = { FieldLabel(field) },
            supportingText = { if (hint.isNotEmpty()) Text(hint) },
            modifier = Modifier.fillMaxWidth(),
        )
        Box(modifier = Modifier.matchParentSize().androidClickable { expanded = true })
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            field.opcje.forEach { opt ->
                DropdownMenuItem(
                    text = { Text(opt.label) },
                    onClick = { onChange(opt.value); expanded = false },
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DateField(field: FieldDto, value: String, onChange: (String) -> Unit, hint: String) {
    var open by remember { mutableStateOf(false) }
    Box(modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = value,
            onValueChange = {},
            readOnly = true,
            label = { FieldLabel(field) },
            placeholder = { Text("RRRR-MM-DD") },
            supportingText = { if (hint.isNotEmpty()) Text(hint) },
            modifier = Modifier.fillMaxWidth(),
        )
        // Przezroczysta nakładka przechwytująca kliknięcie (pole readOnly nie klika się samo).
        Box(modifier = Modifier
            .matchParentSize()
            .androidClickable { open = true })
    }
    if (open) {
        val initial = parseDateMillis(value)
        val dpState = rememberDatePickerState(initialSelectedDateMillis = initial)
        DatePickerDialog(
            onDismissRequest = { open = false },
            confirmButton = {
                TextButton(onClick = {
                    dpState.selectedDateMillis?.let { onChange(millisToIso(it)) }
                    open = false
                }) { Text("OK") }
            },
            dismissButton = { TextButton(onClick = { open = false }) { Text("Anuluj") } },
        ) { DatePicker(state = dpState) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TimeField(field: FieldDto, value: String, onChange: (String) -> Unit, hint: String) {
    var open by remember { mutableStateOf(false) }
    Box(modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = value,
            onValueChange = {},
            readOnly = true,
            label = { FieldLabel(field) },
            placeholder = { Text("GG:MM") },
            supportingText = { if (hint.isNotEmpty()) Text(hint) },
            modifier = Modifier.fillMaxWidth(),
        )
        Box(modifier = Modifier
            .matchParentSize()
            .androidClickable { open = true })
    }
    if (open) {
        val t = parseTime(value)
        val tpState = rememberTimePickerState(initialHour = t.hour, initialMinute = t.minute, is24Hour = true)
        DatePickerDialog(  // reużyty kontener dialogu (przyciski + tło)
            onDismissRequest = { open = false },
            confirmButton = {
                TextButton(onClick = {
                    onChange("%02d:%02d".format(tpState.hour, tpState.minute))
                    open = false
                }) { Text("OK") }
            },
            dismissButton = { TextButton(onClick = { open = false }) { Text("Anuluj") } },
        ) {
            Box(modifier = Modifier.fillMaxWidth().padding(16.dp), contentAlignment = androidx.compose.ui.Alignment.Center) {
                TimePicker(state = tpState)
            }
        }
    }
}

// --- pomocnicze ---

private fun Modifier.androidClickable(onClick: () -> Unit): Modifier =
    this.clickable(
        interactionSource = MutableInteractionSource(),
        indication = null,
        onClick = onClick,
    )

private val ISO: DateTimeFormatter = DateTimeFormatter.ISO_LOCAL_DATE

private fun parseDateMillis(v: String): Long? = try {
    if (v.isBlank()) null
    else LocalDate.parse(v, ISO).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()
} catch (e: Exception) { null }

private fun millisToIso(millis: Long): String =
    Instant.ofEpochMilli(millis).atZone(ZoneOffset.UTC).toLocalDate().format(ISO)

private fun parseTime(v: String): LocalTime = try {
    if (v.isBlank()) LocalTime.of(8, 0) else LocalTime.parse(v)
} catch (e: Exception) { LocalTime.of(8, 0) }
