package com.tradingapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.tradingapp.data.Trade
import com.tradingapp.ui.AppViewModel
import com.tradingapp.ui.components.SymbolSearchField
import com.tradingapp.ui.theme.LossRed
import com.tradingapp.ui.theme.ProfitGreen

@Composable
fun TradesScreen(viewModel: AppViewModel, modifier: Modifier = Modifier) {
    val trades by viewModel.trades.collectAsState()
    val loading by viewModel.loading.collectAsState()
    var query by rememberSaveable { mutableStateOf("") }
    var sideFilter by rememberSaveable { mutableStateOf("ALL") }

    if (loading && trades.isEmpty()) {
        Column(
            modifier = modifier.fillMaxSize().padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            CircularProgressIndicator()
        }
        return
    }

    var selectedTrade by remember { mutableStateOf<Trade?>(null) }

    if (trades.isEmpty()) {
        Column(
            modifier = modifier.fillMaxSize().padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text("No trades yet", style = MaterialTheme.typography.titleMedium)
            Text(
                "Trade history will appear here.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        return
    }

    val filtered = remember(trades, query, sideFilter) {
        val q = query.trim()
        trades.filter { t ->
            (q.isEmpty() || t.symbol.contains(q, ignoreCase = true)) &&
                (sideFilter == "ALL" || t.side == sideFilter)
        }
    }

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            SymbolSearchField(
                query = query,
                onQueryChange = { query = it },
            )
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = sideFilter == "ALL",
                    onClick = { sideFilter = "ALL" },
                    label = { Text("All") },
                )
                FilterChip(
                    selected = sideFilter == "BUY",
                    onClick = { sideFilter = "BUY" },
                    label = { Text("BUY") },
                )
                FilterChip(
                    selected = sideFilter == "SELL",
                    onClick = { sideFilter = "SELL" },
                    label = { Text("SELL") },
                )
            }
        }
        item {
            Text(
                if (query.isBlank() && sideFilter == "ALL") "Total: ${trades.size} trades"
                else "Showing ${filtered.size} of ${trades.size} trades",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (filtered.isEmpty()) {
            item {
                Text(
                    "No trades match your search",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth().padding(vertical = 24.dp),
                )
            }
        } else {
            items(filtered, key = { it.id }) { trade ->
                TradeRow(trade, onClick = { selectedTrade = trade })
            }
        }
    }

    selectedTrade?.let { trade ->
        TradeDetailSheet(trade = trade, onDismiss = { selectedTrade = null })
    }
}

@Composable
private fun TradeRow(trade: Trade, onClick: () -> Unit) {
    val isBuy = trade.side == "BUY"
    val sideColor = if (isBuy) ProfitGreen else LossRed

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .clickable(onClick = onClick)
            .background(MaterialTheme.colorScheme.surface)
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            if (isBuy) "BUY" else "SELL",
            color = sideColor,
            fontWeight = FontWeight.Black,
            style = MaterialTheme.typography.labelLarge,
            modifier = Modifier.width(48.dp),
        )
        Column(Modifier.weight(1f)) {
            Text(
                trade.symbol.removeSuffix(".NS"),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
            )
            Text(
                "${trade.quantity} @ Rs.${format(trade.price)}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            trade.reason.takeIf { it.isNotBlank() }?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                )
            }
        }
        if (!isBuy) {
            val pnl = trade.realizedPnl
            val color = if (pnl >= 0) ProfitGreen else LossRed
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    "Rs.${format(pnl)}",
                    color = color,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    formatPct(trade.realizedPnlPct),
                    color = color,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}
