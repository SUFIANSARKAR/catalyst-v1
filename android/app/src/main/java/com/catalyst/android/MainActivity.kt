package com.catalyst.android

import android.Manifest
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.format.DateFormat
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

class MainActivity : ComponentActivity() {
    private lateinit var prefs: SharedPreferences
    private var connected by mutableStateOf(false)
    private var status by mutableStateOf("Offline")
    private var deviceId by mutableStateOf("")
    private var deviceToken by mutableStateOf("")
    private var apiUrl by mutableStateOf("http://10.0.2.2:8000")
    private var apiToken by mutableStateOf("")
    private var deviceName by mutableStateOf("Catalyst Android")
    private var pollEpoch = 0L

    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences("catalyst", Context.MODE_PRIVATE)
        apiUrl = prefs.getString("apiUrl", apiUrl) ?: apiUrl
        apiToken = prefs.getString("apiToken", "") ?: ""
        deviceName = prefs.getString("deviceName", deviceName) ?: deviceName
        deviceId = prefs.getString("deviceId", "") ?: ""
        deviceToken = prefs.getString("deviceToken", "") ?: ""
        if (Build.VERSION.SDK_INT >= 33) notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)

        setContent {
            MaterialTheme {
                val scroll = rememberScrollState()
                Column(
                    Modifier.fillMaxSize().verticalScroll(scroll).padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text("Catalyst", style = MaterialTheme.typography.headlineMedium)
                    Text("Android companion · authenticated device bridge")
                    OutlinedTextField(apiUrl, { apiUrl = it }, Modifier.fillMaxWidth(), label = { Text("Catalyst API URL") })
                    OutlinedTextField(apiToken, { apiToken = it }, Modifier.fillMaxWidth(), label = { Text("API token (optional for local server)") })
                    OutlinedTextField(deviceName, { deviceName = it }, Modifier.fillMaxWidth(), label = { Text("Device name") })
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { connect() }) { Text(if (connected) "Reconnect" else "Connect") }
                        Button(onClick = { disconnect() }) { Text("Disconnect") }
                    }
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("Status: $status")
                            Text("Device: ${if (deviceId.isBlank()) "not registered" else deviceId.take(12)}")
                            Text("Capabilities: open_url · open_file · show_notification · get_system_info · set_clipboard · get_clipboard")
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                    Text("The companion polls only after authentication and returns an explicit acknowledgement for each command.")
                }
                LaunchedEffect(connected, pollEpoch) {
                    if (connected) {
                        while (connected) {
                            try { heartbeatAndPoll() } catch (e: Exception) { status = "Bridge error: ${e.message ?: "unknown"}" }
                            delay(2500)
                        }
                    }
                }
            }
        }
    }

    private fun connect() {
        prefs.edit().putString("apiUrl", apiUrl.trim().removeSuffix("/")).putString("apiToken", apiToken).putString("deviceName", deviceName).apply()
        status = "Registering…"
        Thread {
            try {
                val payload = JSONObject()
                    .put("name", deviceName)
                    .put("platform", "android")
                    .put("version", Build.VERSION.RELEASE)
                    .put("capabilities", org.json.JSONArray(listOf("open_url", "open_file", "show_notification", "get_system_info", "set_clipboard", "get_clipboard")))
                    .put("metadata", JSONObject().put("manufacturer", Build.MANUFACTURER).put("model", Build.MODEL))
                val response = request("POST", "/api/devices/register", payload)
                val body = JSONObject(response)
                deviceId = body.optString("id", deviceId.ifBlank { UUID.randomUUID().toString() })
                body.optString("device_token", "").takeIf { it.isNotBlank() }?.let { deviceToken = it }
                prefs.edit().putString("deviceId", deviceId).putString("deviceToken", deviceToken).apply()
                runOnUiThread { connected = true; status = "Connected"; pollEpoch++ }
            } catch (e: Exception) {
                runOnUiThread { connected = false; status = "Connection failed: ${e.message ?: "unknown"}" }
            }
        }.start()
    }

    private fun disconnect() { connected = false; status = "Offline" }

    private suspend fun heartbeatAndPoll() = withContext(Dispatchers.IO) {
        if (deviceId.isBlank() || deviceToken.isBlank()) throw IllegalStateException("Device credential missing; reconnect to reprovision")
        request("POST", "/api/devices/$deviceId/heartbeat", JSONObject().put("metadata", JSONObject().put("online", true)))
        val claim = requestRaw("POST", "/api/devices/$deviceId/commands/claim", null)
        if (claim.isBlank()) return@withContext
        val cmd = JSONObject(claim)
        if (cmd.optString("status") == "empty") return@withContext
        val id = cmd.getString("id")
        val action = cmd.getString("action")
        val payload = cmd.optJSONObject("payload") ?: JSONObject()
        try {
            val result = execute(action, payload)
            request("POST", "/api/device-commands/$id/complete", result)
        } catch (e: Exception) {
            requestRaw("POST", "/api/device-commands/$id/fail?error=${Uri.encode(e.message ?: "execution failed")}", null)
        }
    }

    private fun execute(action: String, payload: JSONObject): JSONObject {
        return when (action) {
            "open_url" -> {
                val url = payload.optString("url")
                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                JSONObject().put("ok", true).put("url", url)
            }
            "open_file" -> {
                val path = payload.optString("path")
                val uri = Uri.parse(path)
                startActivity(Intent(Intent.ACTION_VIEW, uri))
                JSONObject().put("ok", true).put("path", path)
            }
            "show_notification" -> {
                val title = payload.optString("title", "Catalyst")
                val body = payload.optString("body", "Catalyst notification")
                Toast.makeText(this, "$title: $body", Toast.LENGTH_LONG).show()
                JSONObject().put("ok", true).put("shown", true)
            }
            "get_system_info" -> JSONObject().put("ok", true).put("platform", "android").put("release", Build.VERSION.RELEASE).put("manufacturer", Build.MANUFACTURER).put("model", Build.MODEL)
            "set_clipboard" -> {
                val text = payload.optString("text")
                val manager = getSystemService(Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
                manager.setPrimaryClip(ClipData.newPlainText("Catalyst", text))
                JSONObject().put("ok", true).put("length", text.length)
            }
            "get_clipboard" -> {
                val manager = getSystemService(Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
                val clip = manager.primaryClip?.getItemAt(0)?.coerceToText(this)?.toString() ?: ""
                JSONObject().put("ok", true).put("text", clip.take(20000))
            }
            else -> throw IllegalArgumentException("Unsupported Android action: $action")
        }
    }

    private fun request(method: String, path: String, body: JSONObject?): String = requestRaw(method, path, body)

    private fun requestRaw(method: String, path: String, body: JSONObject?): String {
        val url = URL(apiUrl.trim().removeSuffix("/") + path)
        val conn = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 10000
            readTimeout = 20000
            setRequestProperty("Accept", "application/json")
            if (apiToken.isNotBlank()) setRequestProperty("Authorization", "Bearer $apiToken")
            if (deviceToken.isNotBlank()) setRequestProperty("X-Catalyst-Device-Token", deviceToken)
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json")
                outputStream.use { it.write(body.toString().toByteArray()) }
            }
        }
        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
        if (code !in 200..299) throw IllegalStateException("HTTP $code: ${text.take(800)}")
        return text
    }
}
