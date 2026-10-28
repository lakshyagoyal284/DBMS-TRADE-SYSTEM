package com.tradingapp.ui

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.tradingapp.data.ApiClient
import com.tradingapp.data.EmailConfig
import com.tradingapp.data.Holding
import com.tradingapp.data.MarketStatus
import com.tradingapp.data.PortfolioPoint
import com.tradingapp.data.Signal
import com.tradingapp.data.Summary
import com.tradingapp.data.Trade
import com.tradingapp.data.WolSender
import com.tradingapp.notifications.SignalNotifier
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.IOException

data class ConnectionState(
    val connected: Boolean = false,
    val checking: Boolean = false,
    val error: String? = null,
)

class AppViewModel(app: Application) : AndroidViewModel(app) {

    private val prefs = app.getSharedPreferences("trading_app", Context.MODE_PRIVATE)

    // Settings
    val serverUrl = MutableStateFlow(prefs.getString("server_url", "http://100.75.238.70:8000") ?: "")
    val pin = MutableStateFlow(prefs.getString("pin", "") ?: "")

    // Wake-on-LAN settings (defaults match the trading PC)
    val wolMac = MutableStateFlow(prefs.getString("wol_mac", "38:A7:46:43:8B:06") ?: "")
    val wolBroadcast = MutableStateFlow(prefs.getString("wol_broadcast", "10.20.4.255") ?: "")
    val wolRelayUrl = MutableStateFlow(prefs.getString("wol_relay_url", "") ?: "")
    private val _wolMessage = MutableStateFlow<String?>(null)
    val wolMessage: StateFlow<String?> = _wolMessage.asStateFlow()

    private var api: ApiClient? = null

    private val _connection = MutableStateFlow(ConnectionState())
    val connection: StateFlow<ConnectionState> = _connection.asStateFlow()

    private val _summary = MutableStateFlow<Summary?>(null)
    val summary: StateFlow<Summary?> = _summary.asStateFlow()

    private val _market = MutableStateFlow<MarketStatus?>(null)
    val market: StateFlow<MarketStatus?> = _market.asStateFlow()

    private val _holdings = MutableStateFlow<List<Holding>>(emptyList())
    val holdings: StateFlow<List<Holding>> = _holdings.asStateFlow()

    private val _trades = MutableStateFlow<List<Trade>>(emptyList())
    val trades: StateFlow<List<Trade>> = _trades.asStateFlow()

    private val _signals = MutableStateFlow<List<Signal>>(emptyList())
    val signals: StateFlow<List<Signal>> = _signals.asStateFlow()

    private val _history = MutableStateFlow<List<PortfolioPoint>>(emptyList())
    val history: StateFlow<List<PortfolioPoint>> = _history.asStateFlow()

    private val _loading = MutableStateFlow(false)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private val _tradingActive = MutableStateFlow(false)
    val tradingActive: StateFlow<Boolean> = _tradingActive.asStateFlow()

    private val _emailConfig = MutableStateFlow<EmailConfig?>(null)
    val emailConfig: StateFlow<EmailConfig?> = _emailConfig.asStateFlow()

    private val _emailSaving = MutableStateFlow(false)
    val emailSaving: StateFlow<Boolean> = _emailSaving.asStateFlow()

    private val _emailMessage = MutableStateFlow<String?>(null)
    val emailMessage: StateFlow<String?> = _emailMessage.asStateFlow()

    private val _lastRefresh = MutableStateFlow<Long>(0)
    val lastRefresh: StateFlow<Long> = _lastRefresh.asStateFlow()

    private var pollJob: Job? = null

    fun saveSettings(url: String, pinValue: String) {
        prefs.edit()
            .putString("server_url", url)
            .putString("pin", pinValue)
            .apply()
        serverUrl.value = url
        pin.value = pinValue
    }

    fun saveWolSettings(mac: String, broadcast: String, relayUrl: String) {
        prefs.edit()
            .putString("wol_mac", mac)
            .putString("wol_broadcast", broadcast)
            .putString("wol_relay_url", relayUrl)
            .apply()
        wolMac.value = mac
        wolBroadcast.value = broadcast
        wolRelayUrl.value = relayUrl
    }

    /** Wake the PC: via the relay if configured, otherwise a direct magic packet. */
    fun wakePc(onDone: (Boolean, String) -> Unit = { _, _ -> }) {
        viewModelScope.launch {
            val mac = wolMac.value.trim()
            val broadcast = wolBroadcast.value.trim()
            val relay = wolRelayUrl.value.trim()

            val (ok, msg) = if (relay.isNotEmpty()) {
                val success = WolSender.callRelay(relay)
                if (success) {
                    true to "✅ Wake request sent via relay. PC should turn on in ~30s."
                } else {
                    false to "❌ Relay unreachable. Check the relay device is on and the URL is right."
                }
            } else if (WolSender.isValidMac(mac) && broadcast.isNotEmpty()) {
                val success = WolSender.sendMagicPacket(broadcast, mac)
                if (success) {
                    true to "✅ Magic packet sent to $broadcast. PC should turn on in ~30s."
                } else {
                    false to "❌ Could not send the packet. Check the broadcast IP and that you're on the same Wi-Fi."
                }
            } else {
                false to "Enter the PC MAC + broadcast IP (or a relay URL) in WoL settings first."
            }
            _wolMessage.value = msg
            onDone(ok, msg)
        }
    }

    fun connect() {
        val url = serverUrl.value
        val token = pin.value
        if (url.isBlank() || token.isBlank()) {
            _connection.value = ConnectionState(error = "Enter the server URL and PIN first")
            return
        }
        _connection.value = ConnectionState(checking = true)
        val client = ApiClient(url, token)
        viewModelScope.launch {
            try {
                val health = withContext(Dispatchers.IO) { client.health() }
                api = client
                _tradingActive.value = health.tradingActive
                _connection.value = ConnectionState(connected = true)
                startPolling()
                refresh()
                loadEmailConfig()
            } catch (e: Exception) {
                _connection.value = ConnectionState(error = friendlyError(e))
            }
        }
    }

    fun disconnect() {
        pollJob?.cancel()
        pollJob = null
        api = null
        _connection.value = ConnectionState()
    }

    private fun startPolling() {
        pollJob?.cancel()
        pollJob = viewModelScope.launch {
            while (isActive) {
                delay(15_000)
                refresh(silent = true)
            }
        }
    }

    fun refresh(silent: Boolean = false) {
        val client = api ?: return
        if (!silent) _loading.value = true
        viewModelScope.launch {
            try {
                val results = withContext(Dispatchers.IO) {
                    data class Batch(
                        val summary: Summary,
                        val market: MarketStatus,
                        val holdings: List<Holding>,
                        val trades: List<Trade>,
                        val signals: List<Signal>,
                        val history: List<PortfolioPoint>,
                    )
                    // trading_active lives in the health endpoint, so refresh it too
                    val health = client.health()
                    _tradingActive.value = health.tradingActive
                    val s = client.getSummary()
                    val m = client.getMarket()
                    val h = client.getHoldings()
                    val t = client.getTrades(100)
                    val g = client.getSignals(100)
                    val p = client.getPortfolioHistory(120)
                    // Notify about any new signals/trades that arrived since the last refresh.
                    SignalNotifier.process(getApplication(), g, t)
                    Batch(s, m, h, t, g, p)
                }
                _summary.value = results.summary
                _market.value = results.market
                _holdings.value = results.holdings
                _trades.value = results.trades
                _signals.value = results.signals
                _history.value = results.history
                _lastRefresh.value = System.currentTimeMillis()
                _connection.value = _connection.value.copy(connected = true, error = null)
            } catch (e: Exception) {
                _connection.value = _connection.value.copy(error = friendlyError(e))
            } finally {
                _loading.value = false
            }
        }
    }

    fun toggleTrading(active: Boolean, onDone: (Boolean) -> Unit = {}) {
        val client = api ?: return
        viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) {
                    if (active) client.startTrading() else client.stopTrading()
                }
                _tradingActive.value = active
                refresh(silent = true)
                onDone(true)
            } catch (e: Exception) {
                _connection.value = _connection.value.copy(error = friendlyError(e))
                onDone(false)
            }
        }
    }

    fun loadEmailConfig() {
        val client = api ?: return
        viewModelScope.launch {
            try {
                val cfg = withContext(Dispatchers.IO) { client.getEmailConfig() }
                _emailConfig.value = cfg
            } catch (e: Exception) {
                _emailMessage.value = friendlyError(e)
            }
        }
    }

    fun saveEmailConfig(cfg: EmailConfig, onDone: (Boolean, String?) -> Unit = { _, _ -> }) {
        val client = api ?: return
        _emailSaving.value = true
        viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) {
                    // Save email_enabled LAST so a partial save never enables a half-configured setup.
                    client.updateConfig("email_smtp_server", cfg.smtpServer)
                    client.updateConfig("email_smtp_port", cfg.smtpPort.toString())
                    client.updateConfig("email_sender", cfg.sender)
                    client.updateConfig("email_password", cfg.password)
                    client.updateConfig("email_recipient", cfg.recipient)
                    client.updateConfig("email_enabled", if (cfg.enabled) "true" else "false")
                }
                _emailConfig.value = cfg
                _emailMessage.value = "✅ Email settings saved"
                onDone(true, null)
            } catch (e: Exception) {
                _emailMessage.value = friendlyError(e)
                onDone(false, e.message)
            } finally {
                _emailSaving.value = false
            }
        }
    }

    fun testEmail(onDone: (Boolean, String?) -> Unit = { _, _ -> }) {
        val client = api ?: return
        _emailSaving.value = true
        viewModelScope.launch {
            try {
                val msg = withContext(Dispatchers.IO) { client.testEmail() }
                _emailMessage.value = msg
                onDone(true, msg)
            } catch (e: Exception) {
                _emailMessage.value = friendlyError(e)
                onDone(false, e.message)
            } finally {
                _emailSaving.value = false
            }
        }
    }

    fun runCycle(onDone: (Boolean) -> Unit = {}) {
        val client = api ?: return
        viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) { client.runCycle() }
                refresh(silent = true)
                onDone(true)
            } catch (e: Exception) {
                _connection.value = _connection.value.copy(error = friendlyError(e))
                onDone(false)
            }
        }
    }

    private fun friendlyError(e: Exception): String {
        return when (e) {
            is IOException -> "Cannot reach the server. Check that the PC is on, the API is running, and Tailscale is connected."
            else -> "Error: ${e.message ?: e.javaClass.simpleName}"
        }
    }
}
