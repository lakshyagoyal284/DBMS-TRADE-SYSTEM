package com.tradingapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.tradingapp.data.Summary
import com.tradingapp.ui.AppViewModel
import com.tradingapp.ui.components.PortfolioChart
import com.tradingapp.ui.theme.LossRed
import com.tradingapp.ui.theme.ProfitGreen
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

@Composable
fun DashboardScreen(viewModel: AppViewModel, modifier: Modifier = Modifier) {
    val summary by viewModel.summary.collectAsState()
    val market by viewModel.market.collectAsState()
    val connection by viewModel.connection.collectAsState()
    val loading by viewModel.loading.collectAsState()
    val lastRefresh by viewModel.lastRefresh.collectAsState()
    val tradingActive by viewModel.tradingActive.collectAsState()
    val history by viewModel.history.collectAsState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        // Market status banner
        val open = market?.open == true
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(14.dp))
                .background(if (open) Color(0xFF052E16) else Color(0xFF450A0A))
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                Modifier
                    .size(12.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(if (open) ProfitGreen else LossRed)
            )
            Spacer(Modifier.width(10.dp))
            Column {
                Text(
                    market?.status ?: "Unknown",
                    fontWeight = FontWeight.Bold,
                    color = if (open) ProfitGreen else LossRed,
                )
                Text(
                    "Market ${if (open) "OPEN" else "CLOSED"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        // Trading engine controls
        TradingControls(
            active = tradingActive,
            loading = loading,
            onToggle = { viewModel.toggleTrading(it) },
            onRefresh = { viewModel.refresh() },
            onCycle = { viewModel.runCycle() },
        )

        // Summary cards
        summary?.let { s ->
            MetricCard(
                title = "Total Portfolio Value",
                value = "Rs.${format(s.totalPortfolioValue)}",
                sub = "Returns ${formatPct(s.totalReturnsPct)}",
                accent = if (s.totalReturnsPct >= 0) ProfitGreen else LossRed,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                MetricCard(
                    title = "Total P&L",
                    value = "Rs.${format(s.totalPnl)}",
                    accent = if (s.totalPnl >= 0) ProfitGreen else LossRed,
                    modifier = Modifier.weight(1f),
                )
                MetricCard(
                    title = "Cash",
                    value = "Rs.${format(s.cashBalance)}",
                    accent = MaterialTheme.colorScheme.secondary,
                    modifier = Modifier.weight(1f),
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                MetricCard(
                    title = "Unrealized",
                    value = "Rs.${format(s.unrealizedPnl)}",
                    accent = if (s.unrealizedPnl >= 0) ProfitGreen else LossRed,
                    modifier = Modifier.weight(1f),
                )
                MetricCard(
                    title = "Realized",
                    value = "Rs.${format(s.realizedPnl)}",
                    accent = if (s.realizedPnl >= 0) ProfitGreen else LossRed,
                    modifier = Modifier.weight(1f),
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                MetricCard(
                    title = "Positions",
                    value = "${s.numOpenPositions}",
                    accent = MaterialTheme.colorScheme.secondary,
                    modifier = Modifier.weight(1f),
                )
                MetricCard(
                    title = "Win Rate",
                    value = "${format(s.winRate)}%",
                    accent = MaterialTheme.colorScheme.secondary,
                    modifier = Modifier.weight(1f),
                )
            }
        } ?: Text(
            "Loading portfolio...",
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth(),
        )

        // Portfolio trend sparkline
        history.takeIf { it.size >= 2 }?.let { h ->
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(14.dp))
                    .background(MaterialTheme.colorScheme.surface)
                    .padding(14.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        "Portfolio Trend",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        formatPct(h.last().totalReturnsPct),
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = if (h.last().totalReturnsPct >= 0) ProfitGreen else LossRed,
                    )
                }
                Spacer(Modifier.height(8.dp))
                PortfolioChart(
                    values = h.map { it.totalValue },
                    modifier = Modifier.fillMaxWidth().height(80.dp),
                )
            }
        }

        // Last refresh
        if (lastRefresh > 0) {
            val fmt = DateTimeFormatter.ofPattern("HH:mm:ss")
                .withZone(ZoneId.systemDefault())
            Text(
                "Last updated: ${fmt.format(Instant.ofEpochMilli(lastRefresh))}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.fillMaxWidth(),
                textAlign = TextAlign.Center,
            )
        }

        connection.error?.let { err ->
            Text(
                err,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}



@Composable
private fun TradingControls(
    active: Boolean,
    loading: Boolean,
    onToggle: (Boolean) -> Unit,
    onRefresh: () -> Unit,
    onCycle: () -> Unit,
) {
    Row(
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Button(
            onClick = { onToggle(!active) },
            colors = ButtonDefaults.buttonColors(
                containerColor = if (active) LossRed else ProfitGreen,
            ),
            modifier = Modifier.weight(1f),
        ) {
            Icon(
                if (active) Icons.Filled.Stop else Icons.Filled.PlayArrow,
                contentDescription = null,
            )
            Spacer(Modifier.width(6.dp))
            Text(if (active) "Stop Trading" else "Start Trading", fontWeight = FontWeight.Bold)
        }
        OutlinedButton(
            onClick = onRefresh,
            enabled = !loading,
            modifier = Modifier.weight(0.6f),
        ) {
            if (loading) {
                CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
            } else {
                Icon(Icons.Filled.Refresh, contentDescription = "Refresh")
            }
            Spacer(Modifier.width(4.dp))
            Text("Refresh")
        }
    }
    OutlinedButton(
        onClick = onCycle,
        enabled = !loading,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text("Run Trading Cycle Now")
    }
}

@Composable
fun MetricCard(
    title: String,
    value: String,
    accent: Color,
    modifier: Modifier = Modifier,
    sub: String? = null,
) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surface)
            .padding(14.dp),
    ) {
        Text(
            title.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            value,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = accent,
        )
        sub?.let {
            Spacer(Modifier.height(2.dp))
            Text(
                it,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

fun format(v: Double): String {
    val abs = Math.abs(v)
    return if (abs >= 100_000) String.format("%.2fL", abs / 100_000.0)
    else String.format("%,.0f", v)
}

fun formatPct(v: Double): String = String.format("%+.2f%%", v)
