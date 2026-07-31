package pl.wnioski.urlopowe.data

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import retrofit2.HttpException

/** Wyciąga pole `detail` z odpowiedzi błędu FastAPI (np. walidacja 400) — albo null. */
fun apiErrorDetail(e: Throwable): String? {
    val http = e as? HttpException ?: return null
    val body = http.response()?.errorBody()?.string()?.takeIf { it.isNotBlank() } ?: return null
    return try {
        Json.parseToJsonElement(body).jsonObject["detail"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() }
    } catch (ex: Exception) {
        null
    }
}
