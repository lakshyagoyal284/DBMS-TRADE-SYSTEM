package com.tradingapp.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.tradingapp.ui.theme.Navy
import com.tradingapp.ui.theme.ProfitGreen

/**
 * A dependency-free line chart drawn with Compose Canvas.
 * Shows a smooth-ish polyline with a gradient fill, grid lines and a marker
 * on the latest point. Renders an empty state when there is not enough data.
 */
@Composable
fun PortfolioChart(
    values: List<Double>,
    modifier: Modifier = Modifier,
    lineColor: Color = ProfitGreen,
) {
    if (values.size < 2) {
        Box(modifier, contentAlignment = Alignment.Center) {
            Text(
                "Not enough data yet",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
        }
        return
    }

    val min = values.min()
    val max = values.max()
    val range = if (max - min > 0) max - min else 1.0
    val gridColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f)

    Canvas(modifier = modifier) {
        val pad = 12.dp.toPx()
        val w = size.width - pad * 2
        val h = size.height - pad * 2
        val stepX = if (values.size > 1) w / (values.size - 1) else 0f
        fun yOf(v: Double) = (pad + h - ((v - min) / range) * h).toFloat()

        // Horizontal grid lines
        for (i in 0..3) {
            val y = pad + h * i / 3f
            drawLine(gridColor, Offset(pad, y), Offset(pad + w, y), strokeWidth = 1f)
        }

        // The data line
        val line = Path()
        values.forEachIndexed { i, v ->
            val x = pad + stepX * i
            val y = yOf(v)
            if (i == 0) line.moveTo(x, y) else line.lineTo(x, y)
        }

        // Gradient fill under the line
        val fill = Path().apply {
            addPath(line)
            lineTo(pad + w, pad + h)
            lineTo(pad, pad + h)
            close()
        }
        drawPath(
            fill,
            Brush.verticalGradient(
                listOf(lineColor.copy(alpha = 0.30f), lineColor.copy(alpha = 0f)),
            ),
        )

        drawPath(
            line,
            color = lineColor,
            style = Stroke(
                width = 2.5.dp.toPx(),
                cap = StrokeCap.Round,
                join = StrokeJoin.Round,
            ),
        )

        // Marker on the latest point
        val lastY = yOf(values.last())
        drawCircle(lineColor, radius = 4.5.dp.toPx(), center = Offset(pad + w, lastY))
        drawCircle(Navy, radius = 1.8.dp.toPx(), center = Offset(pad + w, lastY))
    }
}
