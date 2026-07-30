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

/** Zapisuje PDF do cache i otwiera zewnętrzną przeglądarką (FileProvider). */
object PdfOpener {

    enum class Result { OPENED, NO_VIEWER, ERROR }

    fun open(context: Context, bytes: ByteArray, fileName: String): Result = try {
        val dir = File(context.cacheDir, "pdfs").apply { mkdirs() }
        val safe = fileName.ifBlank { "wniosek.pdf" }.substringAfterLast('/').substringAfterLast('\\')
        val file = File(dir, if (safe.endsWith(".pdf", ignoreCase = true)) safe else "$safe.pdf")
        file.writeBytes(bytes)
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/pdf")
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
                            Toast.makeText(context, "Brak aplikacji do otwierania PDF.", Toast.LENGTH_LONG).show()
                        PdfOpener.Result.ERROR ->
                            Toast.makeText(context, "Nie udało się otworzyć PDF.", Toast.LENGTH_SHORT).show()
                    }
                } catch (e: Exception) {
                    Toast.makeText(context, "Nie udało się pobrać PDF.", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}
