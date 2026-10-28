package com.tradingapp.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Navy = Color(0xFF0F172A)
val SurfaceDark = Color(0xFF1E293B)
val BorderDark = Color(0xFF334155)
val ProfitGreen = Color(0xFF00E676)
val LossRed = Color(0xFFFF5252)
val AccentBlue = Color(0xFF4FC3F7)
val TextPrimary = Color(0xFFE2E8F0)
val TextSecondary = Color(0xFF94A3B8)

private val DarkColors = darkColorScheme(
    primary = ProfitGreen,
    onPrimary = Color(0xFF00310F),
    secondary = AccentBlue,
    onSecondary = Color(0xFF002F43),
    tertiary = Color(0xFFB388FF),
    background = Navy,
    onBackground = TextPrimary,
    surface = SurfaceDark,
    onSurface = TextPrimary,
    surfaceVariant = BorderDark,
    onSurfaceVariant = TextSecondary,
    error = LossRed,
)

@Composable
fun TradingAppTheme(content: @Composable () -> Unit) {
    // The app is always dark - matches the dashboard aesthetic.
    MaterialTheme(
        colorScheme = DarkColors,
        content = content,
    )
}
