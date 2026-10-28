package com.tradingapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.tradingapp.data.Signal
import com.tradingapp.ui.AppViewModel
import com.tradingapp.ui.theme.AccentBlue
import com.tradingapp.ui.theme.LossRed
import com.tradingapp.ui.theme.ProfitGreen

@Composable
fun SignalsScreen(viewModel: AppViewModel, modifier: Modifier = Modifier) {
    val signals by viewModel.signals.collectAsState()
    val loading by viewModel.loading.collectAsState()

    if (loading && signals.isEmpty()) {
        Column(
            modifier = modifier.fillMaxSize().padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            CircularProgressIndicator()
        }
        return
    }

    if (signals.isEmpty()) {
        Column(
            modifier = modifier.fillMaxSize().padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text("No signals yet", style = MaterialTheme.typography.titleMedium)
            Text(
                "Strategy signals will appear here.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        return
    }

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text(
                "Total: ${signals.size} recent signals",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        items(signals, key = { it.id }) { signal ->
            SignalRow(signal)
        }
    }
}

@Composable
private fun SignalRow(signal: Signal) {
    val typeColor = when (signal.signalType) {
        "BUY" -> ProfitGreen
        "SELL" -> LossRed
        else -> AccentBlue
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surface)
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    signal.signalType,
                    color = typeColor,
                    fontWeight = FontWeight.Black,
                    style = MaterialTheme.typography.labelLarge,
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    signal.symbol.removeSuffix(".NS"),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                )
            }
            Text(
                "Rs.${format(signal.price)} · RSI ${if (signal.rsi.isNaN()) "—" else format(signal.rsi)}" +
                    if (signal.bbPosition.isNotBlank()) " · ${signal.bbPosition} band" else "",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            signal.reason.takeIf { it.isNotBlank() }?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                )
            }
        }
        Text(
            if (signal.executed) "✅" else "⏳",
            style = MaterialTheme.typography.titleMedium,
        )
    }
}
