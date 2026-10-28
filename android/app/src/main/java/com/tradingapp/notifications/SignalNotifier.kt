package com.tradingapp.notifications

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.tradingapp.MainActivity
import com.tradingapp.R
import com.tradingapp.data.ApiClient
import com.tradingapp.data.Signal
import com.tradingapp.data.Trade
import kotlin.math.abs

/**
 * Fires local notifications when new trading signals or executed trades appear.
 *
 * Works in two ways:
 *  1. In the foreground — AppViewModel calls [process] with freshly fetched data every 15s.
 *  2. In the background — [checkAndNotify] runs from a WorkManager worker and polls the
 *     server directly, so you still get alerts when the app is closed.
 *
 * Both share the same "last seen" IDs in SharedPreferences, so nothing is ever
 * notified twice.
 */
object SignalNotifier {

    private const val CHANNEL_ID = "trading_alerts"
    private const val CHANNEL_NAME = "Trading alerts"
    private const val PREFS = "trading_app"

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_DEFAULT,
            )
            manager.createNotificationChannel(channel)
        }
    }

    /** Polls the server for new signals/trades and notifies about them. No-op if not configured. */
    suspend fun checkAndNotify(context: Context) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val url = prefs.getString("server_url", null)?.takeIf { it.isNotBlank() } ?: return
        val pin = prefs.getString("pin", null)?.takeIf { it.isNotBlank() } ?: return
        try {
            val client = ApiClient(url, pin)
            val signals = client.getSignals(20)
            val trades = client.getTrades(20)
            process(context, signals, trades)
        } catch (_: Exception) {
            // Server unreachable right now — the next scheduled check will catch up.
        }
    }

    /**
     * Compares the latest items against the last-seen IDs and fires notifications for new ones.
     *
     * Synchronized so the in-app 15s poll and the background worker can never both read the
     * same last-seen IDs and fire duplicate notifications.
     */
    @Synchronized
    fun process(context: Context, signals: List<Signal>, trades: List<Trade>) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val lastSignalId = prefs.getLong("last_signal_id", -1L)
        val lastTradeId = prefs.getLong("last_trade_id", -1L)

        val maxSignal = signals.maxOfOrNull { it.id } ?: -1L
        val maxTrade = trades.maxOfOrNull { it.id } ?: -1L

        // First run: just record the baseline so we don't spam old history items.
        if (lastSignalId == -1L || lastTradeId == -1L) {
            prefs.edit()
                .putLong("last_signal_id", maxSignal)
                .putLong("last_trade_id", maxTrade)
                .apply()
            return
        }

        ensureChannel(context)
        // Namespace the notification IDs: signals and trades come from different tables,
        // so e.g. signal #5 and trade #5 must not overwrite each other's notification.
        signals.filter { it.id > lastSignalId }.forEach { notifySignal(context, it) }
        trades.filter { it.id > lastTradeId }.forEach { notifyTrade(context, it) }

        prefs.edit()
            .putLong("last_signal_id", maxSignal)
            .putLong("last_trade_id", maxTrade)
            .apply()
    }

    private fun notifySignal(context: Context, signal: Signal) {
        val symbol = signal.symbol.removeSuffix(".NS")
        val details = buildString {
            if (!signal.rsi.isNaN()) {
                append("RSI ").append(fmt(signal.rsi))
            }
            if (signal.bbPosition.isNotBlank()) {
                if (isNotEmpty()) append(" · ")
                append(signal.bbPosition).append(" band")
            }
            if (signal.executed) {
                if (isNotEmpty()) append(" · ")
                append("Executed ✅")
            }
        }
        notify(context, signal.id * 10 + 1, "${signal.signalType} signal · $symbol", details.ifEmpty { "New signal" })
    }

    private fun notifyTrade(context: Context, trade: Trade) {
        val symbol = trade.symbol.removeSuffix(".NS")
        val text = if (trade.side == "BUY") {
            "Bought ${trade.quantity} @ Rs.${fmt(trade.price)}"
        } else {
            "Sold ${trade.quantity} @ Rs.${fmt(trade.price)} · P&L ${signed(trade.realizedPnl)}"
        }
        notify(context, trade.id * 10 + 2, "${trade.side} $symbol", text)
    }

    private fun notify(context: Context, id: Long, title: String, text: String) {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        val pending = PendingIntent.getActivity(
            context,
            id.toInt(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setContentIntent(pending)
            .build()
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(id.toInt(), notification)
    }

    private fun fmt(v: Double): String =
        if (abs(v) >= 100_000) String.format("%.2fL", v / 100_000.0)
        else String.format("%,.0f", v)

    private fun signed(v: Double): String =
        if (v >= 0) "Rs.${fmt(v)}" else "-Rs.${fmt(abs(v))}"
}
