package com.tradingapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.tradingapp.data.Holding
import com.tradingapp.ui.theme.AccentBlue
import com.tradingapp.ui.theme.LossRed
import com.tradingapp.ui.theme.ProfitGreen

/** Bottom sheet with the full details of an open position, including the bot's exit plan. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HoldingDetailSheet(holding: Holding, onDismiss: () -> Unit) {
    val pnl = holding.unrealizedPnl
    val pnlColor = if (pnl >= 0) ProfitGreen else LossRed

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .padding(bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            // Header: symbol + live P&L
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(
                        holding.symbol.removeSuffix(".NS"),
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        strategyLabel(holding.strategy),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        "Rs.${format(holding.unrealizedPnl)}",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        color = pnlColor,
                    )
                    Text(
                        formatPct(holding.unrealizedPnlPct),
                        style = MaterialTheme.typography.bodyMedium,
                        color = pnlColor,
                    )
                }
            }

            HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)

            DetailRow("Quantity", "${holding.quantity} shares")
            DetailRow("Avg Buy Price", "Rs.${format(holding.avgBuyPrice)}")
            DetailRow("Current Price", "Rs.${format(holding.currentPrice)}")
            DetailRow("Buy Value", "Rs.${format(holding.buyValue)}")
            DetailRow("Current Value", "Rs.${format(holding.currentValue)}")
            DetailRow("Unrealized P&L", "Rs.${format(holding.unrealizedPnl)}", valueColor = pnlColor)
            DetailRow("Entry Date", formatTimestamp(holding.entryDate))
            holding.entryRsi?.let { DetailRow("Entry RSI", format(it)) }

            HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)

            Text(
                "BOT'S EXIT PLAN",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            holding.stopLossPrice?.let { sl ->
                PlanItem(
                    emoji = "🔴",
                    title = "Stop Loss",
                    detail = "Sell if the price drops to Rs.${format(sl)} " +
                        "(${pctPlain(holding.stopLossPct)}% below entry).",
                    accent = LossRed,
                )
            }
            holding.takeProfitPrice?.let { tp ->
                PlanItem(
                    emoji = "🟢",
                    title = "Take Profit",
                    detail = "Sell if the price reaches Rs.${format(tp)} " +
                        "(${pctPlain(holding.takeProfitPct)}% above entry).",
                    accent = ProfitGreen,
                )
            }
            PlanItem(
                emoji = "📊",
                title = "RSI Exit",
                detail = "Exit when RSI crosses back above 50" +
                    (holding.entryRsi?.let { " (entered at ${format(it)})" } ?: "") +
                    " — mean reversion complete.",
                accent = AccentBlue,
            )
            PlanItem(
                emoji = "📈",
                title = "Trailing Stop",
                detail = "After a 3%+ gain, the bot trails a 2% stop to lock in profits if the price reverses.",
                accent = AccentBlue,
            )
        }
    }
}

@Composable
private fun PlanItem(emoji: String, title: String, detail: String, accent: Color) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(accent.copy(alpha = 0.10f))
            .padding(12.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Text(emoji, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.width(8.dp))
        Column(Modifier.weight(1f)) {
            Text(
                title,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Bold,
                color = accent,
            )
            Spacer(Modifier.height(2.dp))
            Text(
                detail,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }
    }
}

private fun strategyLabel(s: String): String = when (s.uppercase()) {
    "RSI_BB" -> "RSI + Bollinger Bands · Mean Reversion"
    "RSI" -> "RSI Mean Reversion"
    "BB" -> "Bollinger Bands"
    else -> if (s.isBlank()) "RSI + Bollinger Bands · Mean Reversion" else s
}

private fun pctPlain(v: Double?): String = String.format("%.1f", v ?: 0.0)
