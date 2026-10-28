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
import com.tradingapp.data.Holding
import com.tradingapp.ui.AppViewModel
import com.tradingapp.ui.components.SymbolSearchField
import com.tradingapp.ui.theme.LossRed
import com.tradingapp.ui.theme.ProfitGreen

@Composable
fun HoldingsScreen(viewModel: AppViewModel, modifier: Modifier = Modifier) {
    val holdings by viewModel.holdings.collectAsState()
    val loading by viewModel.loading.collectAsState()
    var query by rememberSaveable { mutableStateOf("") }
    var selectedHolding by remember { mutableStateOf<Holding?>(null) }

    if (loading && holdings.isEmpty()) {
        Column(
            modifier = modifier.fillMaxSize().padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            CircularProgressIndicator()
        }
        return
    }

    if (holdings.isEmpty()) {
        Column(
            modifier = modifier.fillMaxSize().padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                "No open positions",
                style = MaterialTheme.typography.titleMedium,
            )
            Spacer(Modifier.width(0.dp))
            Text(
                "Holdings will appear here when the strategy opens trades.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        return
    }

    val filtered = remember(holdings, query) {
        val q = query.trim()
        if (q.isEmpty()) holdings
        else holdings.filter { it.symbol.contains(q, ignoreCase = true) }
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
            Text(
                if (query.isBlank()) "Total: ${holdings.size} positions"
                else "Showing ${filtered.size} of ${holdings.size} positions",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (filtered.isEmpty()) {
            item {
                Text(
                    "No positions match \"${query.trim()}\"",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth().padding(vertical = 24.dp),
                )
            }
        } else {
            items(filtered, key = { it.symbol }) { holding ->
                HoldingRow(holding, onClick = { selectedHolding = holding })
            }
        }
    }

    selectedHolding?.let { holding ->
        HoldingDetailSheet(holding = holding, onDismiss = { selectedHolding = null })
    }
}

@Composable
private fun HoldingRow(holding: Holding, onClick: () -> Unit) {
    val pnl = holding.unrealizedPnl
    val pnlColor = if (pnl >= 0) ProfitGreen else LossRed

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .clickable(onClick = onClick)
            .background(MaterialTheme.colorScheme.surface)
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                holding.symbol.removeSuffix(".NS"),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            Text(
                "Qty ${holding.quantity} @ Rs.${format(holding.avgBuyPrice)}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                "Current Rs.${format(holding.currentPrice)}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(
                "Rs.${format(holding.unrealizedPnl)}",
                color = pnlColor,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                "${formatPct(holding.unrealizedPnlPct)}",
                color = pnlColor,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}
