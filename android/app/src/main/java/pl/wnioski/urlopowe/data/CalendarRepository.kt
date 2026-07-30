package pl.wnioski.urlopowe.data

/** Dane do kalendarza: rekordy roku, metadane typów (id → nazwa/kolor), święta (data → nazwa). */
class CalendarRepository(private val api: ApiService) {

    suspend fun records(year: Int): List<RecordDto> = api.records(year)

    suspend fun types(): Map<String, LeaveTypeDto> = api.types().typy.associateBy { it.id }

    suspend fun holidays(year: Int): Map<String, String> =
        api.holidays(year).associate { it.data to it.nazwa }

    suspend fun setStatus(id: Int, status: String) {
        api.setStatus(id, StatusRequest(status))
    }

    suspend fun delete(id: Int) = api.delete(id)

    suspend fun pdfBytes(id: Int): ByteArray =
        kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) { api.pdf(id).bytes() }
}
