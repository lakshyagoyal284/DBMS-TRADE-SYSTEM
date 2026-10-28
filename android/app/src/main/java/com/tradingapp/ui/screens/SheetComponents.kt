package com.tradingapp.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/** A simple label/value row used inside detail bottom sheets. */
@Composable
fun DetailRow(
    label: String,
    value: String,
    valueColor: Color = MaterialTheme.colorScheme.onSurface,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            color = valueColor,
        )
    }
}

/** Formats "2026-08-03T12:34:56.789" / "2026-08-03 12:34:56" into "03 Aug 2026, 12:34 PM". */
fun formatTimestamp(ts: String): String {
    if (ts.isBlank()) return "—"
    val cleaned = ts.replace("T", " ").take(19)
    return try {
        LocalDateTime
            .parse(cleaned, DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))
            .format(DateTimeFormatter.ofPattern("dd MMM yyyy, hh:mm a"))
    } catch (e: Exception) {
        ts
    }
}
