package com.tradingapp

import android.app.Application
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.tradingapp.notifications.NotificationWorker
import com.tradingapp.notifications.SignalNotifier
import java.util.concurrent.TimeUnit

class TradingApp : Application() {

    override fun onCreate() {
        super.onCreate()
        SignalNotifier.ensureChannel(this)

        // Check for new signals/trades in the background (min interval for periodic work
        // is 15 minutes). While the app is open, the 15s poll handles it.
        val request = PeriodicWorkRequestBuilder<NotificationWorker>(15, TimeUnit.MINUTES)
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build()
            )
            .build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "trading_alerts_check",
            ExistingPeriodicWorkPolicy.KEEP,
            request,
        )
    }
}
