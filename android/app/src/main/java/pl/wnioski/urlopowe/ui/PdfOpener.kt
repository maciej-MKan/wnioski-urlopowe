package pl.wnioski.urlopowe.ui

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.FileProvider
import kotlinx.coroutines.launch
import java.io.File

/** Zapisuje plik (PDF/JPG) do cache i otwiera zewnętrzną przeglądarką (FileProvider). */
object PdfOpener {

    enum class Result { OPENED, NO_VIEWER, ERROR }

    /** Wykrywa typ z pierwszych bajtów (PDF/JPG) — załączniki bywają obrazami, nie tylko PDF. */
    private fun detect(bytes: ByteArray): Pair<String, String> = when {
        bytes.size >= 4 && bytes[0] == 0x25.toByte() && bytes[1] == 0x50.toByte() &&
            bytes[2] == 0x44.toByte() && bytes[3] == 0x46.toByte() -> "pdf" to "application/pdf"
        bytes.size >= 2 && bytes[0] == 0xFF.toByte() && bytes[1] == 0xD8.toByte() -> "jpg" to "image/jpeg"
        else -> "pdf" to "application/pdf"
    }

    fun open(context: Context, bytes: ByteArray, fileName: String): Result = try {
        val (ext, mime) = detect(bytes)
        val dir = File(context.cacheDir, "pdfs").apply { mkdirs() }
        val safe = fileName.ifBlank { "plik" }.substringAfterLast('/').substringAfterLast('\\')
        val base = safe.substringBeforeLast('.', safe)
        val file = File(dir, "$base.$ext")
        file.writeBytes(bytes)
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, mime)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
        Result.OPENED
    } catch (e: ActivityNotFoundException) {
        Result.NO_VIEWER
    } catch (e: Exception) {
        android.util.Log.e("PdfOpener", "open failed", e)
        Result.ERROR
    }
}

/** Zwraca akcję `(id, nazwa)` pobierającą i otwierającą PDF rekordu, z komunikatem Toast. */
@Composable
fun rememberPdfDownloader(fetch: suspend (Int) -> ByteArray): (Int, String) -> Unit {
    val context = LocalContext.current
    val scope = androidx.compose.runtime.rememberCoroutineScope()
    return remember(fetch) {
        { id, name ->
            scope.launch {
                try {
                    val bytes = fetch(id)
                    when (PdfOpener.open(context, bytes, name)) {
                        PdfOpener.Result.OPENED -> Unit
                        PdfOpener.Result.NO_VIEWER ->
                            Toast.makeText(context, "Brak aplikacji do otwarcia pliku.", Toast.LENGTH_LONG).show()
                        PdfOpener.Result.ERROR ->
                            Toast.makeText(context, "Nie udało się otworzyć pliku.", Toast.LENGTH_SHORT).show()
                    }
                } catch (e: Exception) {
                    Toast.makeText(context, "Nie udało się pobrać pliku.", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}
