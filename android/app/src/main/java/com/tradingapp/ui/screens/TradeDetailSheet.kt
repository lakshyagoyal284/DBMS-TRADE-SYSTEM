package com.tradingapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.tradingapp.data.Trade
import com.tradingapp.ui.theme.LossRed
import com.tradingapp.ui.theme.ProfitGreen

/** Bottom sheet with the full details of a single trade. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TradeDetailSheet(trade: Trade, onDismiss: () -> Unit) {
    val isBuy = trade.side == "BUY"
    val sideColor = if (isBuy) ProfitGreen else LossRed

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .padding(bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            // Header: side badge + symbol
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(sideColor.copy(alpha = 0.15f))
                        .padding(horizontal = 12.dp, vertical = 6.dp),
                ) {
                    Text(
                        trade.side,
                        color = sideColor,
                        fontWeight = FontWeight.Black,
                        style = MaterialTheme.typography.labelLarge,
                    )
                }
                Spacer(Modifier.width(12.dp))
                Column {
                    Text(
                        trade.symbol.removeSuffix(".NS"),
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        "Trade #${trade.id}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)

            DetailRow("Quantity", "${trade.quantity} shares")
            DetailRow("Price", "Rs.${format(trade.price)}")
            DetailRow("Trade Value", "Rs.${format(trade.tradeValue)}")
            if (!isBuy) {
                val pnlColor = if (trade.realizedPnl >= 0) ProfitGreen else LossRed
                DetailRow(
                    "Realized P&L",
                    "Rs.${format(trade.realizedPnl)}  (${formatPct(trade.realizedPnlPct)})",
                    valueColor = pnlColor,
                )
            }
            DetailRow("Timestamp", formatTimestamp(trade.timestamp))

            HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)

            if (trade.reason.isNotBlank()) {
                Text(
                    "REASON",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(10.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f))
                        .padding(12.dp),
                ) {
                    Text(
                        trade.reason,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                }
            } else {
                Text(
                    "No entry reason recorded for this trade.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}


