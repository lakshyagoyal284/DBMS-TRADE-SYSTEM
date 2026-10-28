package com.tradingapp.notifications

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

/** Background poller — checks the server for new signals/trades every ~15 minutes. */
class NotificationWorker(appContext: Context, params: WorkerParameters) :
    CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        SignalNotifier.checkAndNotify(applicationContext)
        // Always succeed; transient failures are picked up by the next scheduled run.
        return Result.success()
    }
}
