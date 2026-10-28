package com.tradingapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.tradingapp.ui.AppViewModel
import com.tradingapp.ui.components.PortfolioChart
import com.tradingapp.ui.theme.AccentBlue
import com.tradingapp.ui.theme.LossRed
import com.tradingapp.ui.theme.ProfitGreen

@Composable
fun PerformanceScreen(viewModel: AppViewModel, modifier: Modifier = Modifier) {
    val history by viewModel.history.collectAsState()
    val loading by viewModel.loading.collectAsState()
    var mode by rememberSaveable { mutableIntStateOf(0) } // 0 = value, 1 = returns %

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            "📈 Portfolio Performance",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
        )
        Text(
            if (history.isEmpty()) "No history recorded yet."
            else "Last ${history.size} recorded point${if (history.size == 1) "" else "s"}",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        when {
            loading && history.isEmpty() -> {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center,
                ) {
                    CircularProgressIndicator()
                }
            }
            history.size < 2 -> {
                Text(
                    "Not enough history to draw a chart yet. Portfolio snapshots are " +
                        "recorded as the strategy runs — check back soon.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            else -> {
                val last = history.last()

                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    MetricCard(
                        title = "Portfolio Value",
                        value = "Rs.${format(last.totalValue)}",
                        accent = if (last.totalReturnsPct >= 0) ProfitGreen else LossRed,
                        modifier = Modifier.weight(1f),
                    )
                    MetricCard(
                        title = "Total Returns",
                        value = formatPct(last.totalReturnsPct),
                        accent = if (last.totalReturnsPct >= 0) ProfitGreen else LossRed,
                        modifier = Modifier.weight(1f),
                    )
                }
                MetricCard(
                    title = "Day P&L",
                    value = "Rs.${format(last.dayPnl)}",
                    accent = if (last.dayPnl >= 0) ProfitGreen else LossRed,
                    modifier = Modifier.fillMaxWidth(),
                )

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = mode == 0,
                        onClick = { mode = 0 },
                        label = { Text("Value") },
                    )
                    FilterChip(
                        selected = mode == 1,
                        onClick = { mode = 1 },
                        label = { Text("Returns %") },
                    )
                }

                val values = if (mode == 0) history.map { it.totalValue }
                else history.map { it.totalReturnsPct }
                val chartColor = if (mode == 0) ProfitGreen else AccentBlue

                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(14.dp))
                        .background(MaterialTheme.colorScheme.surface)
                        .padding(14.dp),
                ) {
                    Text(
                        if (mode == 0) "PORTFOLIO VALUE OVER TIME" else "TOTAL RETURNS OVER TIME",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(10.dp))
                    PortfolioChart(
                        values = values,
                        lineColor = chartColor,
                        modifier = Modifier.fillMaxWidth().height(220.dp),
                    )
                    Spacer(Modifier.height(10.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        val fmtVal: (Double) -> String = { v ->
                            if (mode == 0) "Rs.${format(v)}" else formatPct(v)
                        }
                        Text(
                            "Low ${fmtVal(values.min())}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            "High ${fmtVal(values.max())}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}
