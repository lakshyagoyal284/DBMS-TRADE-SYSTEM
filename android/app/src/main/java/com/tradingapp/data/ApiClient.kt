package com.tradingapp.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Thin OkHttp wrapper around the Python FastAPI backend.
 * All calls carry the Authorization: Bearer <PIN> header.
 */
class ApiClient(private val baseUrl: String, private val pin: String) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    private val jsonMedia = "application/json; charset=utf-8".toMediaType()

    private fun url(path: String): String {
        val cleanBase = baseUrl.trimEnd('/')
        return "$cleanBase/$path"
    }

    private fun authBuilder(path: String): Request.Builder =
        Request.Builder()
            .url(url(path))
            .header("Authorization", "Bearer $pin")

    private suspend fun execute(request: Request): String = withContext(Dispatchers.IO) {
        client.newCall(request).execute().use { resp ->
            val body = resp.body?.string() ?: ""
            if (!resp.isSuccessful) {
                throw IOException("HTTP ${resp.code}: ${body.take(200)}")
            }
            body
        }
    }

    suspend fun health(): Health {
        val body = execute(authBuilder("api/health").get().build())
        val o = JSONObject(body)
        return Health(o.optString("status"), o.optBoolean("trading_active"))
    }

    suspend fun getSummary(): Summary {
        val body = execute(authBuilder("api/summary").get().build())
        return Summary.fromJson(JSONObject(body))
    }

    suspend fun getMarket(): MarketStatus {
        val body = execute(authBuilder("api/market").get().build())
        val o = JSONObject(body)
        return MarketStatus(o.optString("status"), o.optBoolean("open"))
    }

    suspend fun getHoldings(): List<Holding> {
        val body = execute(authBuilder("api/holdings").get().build())
        val arr = JSONArray(body)
        return List(arr.length()) { Holding.fromJson(arr.getJSONObject(it)) }
    }

    suspend fun getTrades(limit: Int = 100): List<Trade> {
        val body = execute(authBuilder("api/trades?limit=$limit").get().build())
        val arr = JSONArray(body)
        return List(arr.length()) { Trade.fromJson(arr.getJSONObject(it)) }
    }

    suspend fun getSignals(limit: Int = 100): List<Signal> {
        val body = execute(authBuilder("api/signals?limit=$limit").get().build())
        val arr = JSONArray(body)
        return List(arr.length()) { Signal.fromJson(arr.getJSONObject(it)) }
    }

    suspend fun getPortfolioHistory(limit: Int = 120): List<PortfolioPoint> {
        val body = execute(authBuilder("api/portfolio-history?limit=$limit").get().build())
        val arr = JSONArray(body)
        return List(arr.length()) { PortfolioPoint.fromJson(arr.getJSONObject(it)) }
    }

    suspend fun getEmailConfig(): EmailConfig {
        val body = execute(authBuilder("api/config").get().build())
        val o = JSONObject(body)
        return EmailConfig(
            enabled = o.optString("email_enabled") == "true",
            smtpServer = o.optString("email_smtp_server").ifBlank { "smtp.gmail.com" },
            smtpPort = o.optString("email_smtp_port").toIntOrNull() ?: 587,
            sender = o.optString("email_sender"),
            password = o.optString("email_password"),
            recipient = o.optString("email_recipient"),
        )
    }

    suspend fun updateConfig(key: String, value: String) {
        val json = JSONObject().put("key", key).put("value", value).toString()
        execute(authBuilder("api/config").post(json.toRequestBody(jsonMedia)).build())
    }

    suspend fun testEmail(): String {
        val body = execute(authBuilder("api/email/test").post("{}".toRequestBody(jsonMedia)).build())
        return JSONObject(body).optString("message", "Test email sent")
    }

    suspend fun startTrading() {
        execute(authBuilder("api/trading/start").post("{}".toRequestBody(jsonMedia)).build())
    }

    suspend fun stopTrading() {
        execute(authBuilder("api/trading/stop").post("{}".toRequestBody(jsonMedia)).build())
    }

    suspend fun runCycle() {
        execute(authBuilder("api/trading/cycle").post("{}".toRequestBody(jsonMedia)).build())
    }
}
