package com.tradingapp.data

import org.json.JSONObject

data class Summary(
    val cashBalance: Double,
    val initialCapital: Double,
    val investedValue: Double,
    val currentHoldingsValue: Double,
    val totalPortfolioValue: Double,
    val unrealizedPnl: Double,
    val realizedPnl: Double,
    val totalPnl: Double,
    val totalReturnsPct: Double,
    val totalTrades: Int,
    val winningTrades: Int,
    val losingTrades: Int,
    val winRate: Double,
    val totalBoughtShares: Int,
    val totalSoldShares: Int,
    val heldShares: Int,
    val numOpenPositions: Int,
) {
    companion object {
        fun fromJson(o: JSONObject): Summary {
            fun d(key: String) = o.optDouble(key, 0.0)
            fun i(key: String) = o.optInt(key, 0)
            return Summary(
                cashBalance = d("cash_balance"),
                initialCapital = d("initial_capital"),
                investedValue = d("invested_value"),
                currentHoldingsValue = d("current_holdings_value"),
                totalPortfolioValue = d("total_portfolio_value"),
                unrealizedPnl = d("unrealized_pnl"),
                realizedPnl = d("realized_pnl"),
                totalPnl = d("total_pnl"),
                totalReturnsPct = d("total_returns_pct"),
                totalTrades = i("total_trades"),
                winningTrades = i("winning_trades"),
                losingTrades = i("losing_trades"),
                winRate = d("win_rate"),
                totalBoughtShares = i("total_bought_shares"),
                totalSoldShares = i("total_sold_shares"),
                heldShares = i("held_shares"),
                numOpenPositions = i("num_open_positions"),
            )
        }
    }
}

data class Holding(
    val symbol: String,
    val quantity: Int,
    val avgBuyPrice: Double,
    val currentPrice: Double,
    val buyValue: Double,
    val currentValue: Double,
    val unrealizedPnl: Double,
    val unrealizedPnlPct: Double,
    val entryDate: String,
    val entryRsi: Double? = null,
    val strategy: String = "",
    val stopLossPct: Double? = null,
    val takeProfitPct: Double? = null,
    val stopLossPrice: Double? = null,
    val takeProfitPrice: Double? = null,
) {
    companion object {
        fun fromJson(o: JSONObject): Holding = Holding(
            symbol = o.optString("symbol"),
            quantity = o.optInt("quantity"),
            avgBuyPrice = o.optDouble("avg_buy_price"),
            currentPrice = o.optDouble("current_price"),
            buyValue = o.optDouble("buy_value"),
            currentValue = o.optDouble("current_value"),
            unrealizedPnl = o.optDouble("unrealized_pnl"),
            unrealizedPnlPct = o.optDouble("unrealized_pnl_pct"),
            entryDate = o.optString("entry_date", ""),
            entryRsi = o.optDouble("entry_rsi", Double.NaN).takeIf { !it.isNaN() },
            strategy = o.optString("strategy", ""),
            stopLossPct = o.optDouble("stop_loss_pct", 0.0).takeIf { it > 0 },
            takeProfitPct = o.optDouble("take_profit_pct", 0.0).takeIf { it > 0 },
            stopLossPrice = o.optDouble("stop_loss_price", 0.0).takeIf { it > 0 },
            takeProfitPrice = o.optDouble("take_profit_price", 0.0).takeIf { it > 0 },
        )
    }
}

data class Trade(
    val id: Long,
    val symbol: String,
    val side: String,
    val quantity: Int,
    val price: Double,
    val tradeValue: Double,
    val realizedPnl: Double,
    val realizedPnlPct: Double,
    val timestamp: String,
    val reason: String,
) {
    companion object {
        fun fromJson(o: JSONObject): Trade = Trade(
            id = o.optLong("id"),
            symbol = o.optString("symbol"),
            side = o.optString("side"),
            quantity = o.optInt("quantity"),
            price = o.optDouble("price"),
            tradeValue = o.optDouble("trade_value"),
            realizedPnl = o.optDouble("realized_pnl"),
            realizedPnlPct = o.optDouble("realized_pnl_pct"),
            timestamp = o.optString("timestamp", ""),
            reason = o.optString("reason", ""),
        )
    }
}

data class Signal(
    val id: Long,
    val symbol: String,
    val signalType: String,
    val strength: Double,
    val price: Double,
    val rsi: Double,
    val bbPosition: String,
    val reason: String,
    val timestamp: String,
    val executed: Boolean,
) {
    companion object {
        fun fromJson(o: JSONObject): Signal = Signal(
            id = o.optLong("id"),
            symbol = o.optString("symbol"),
            signalType = o.optString("signal_type"),
            strength = o.optDouble("strength"),
            price = o.optDouble("price"),
            rsi = o.optDouble("rsi", Double.NaN),
            bbPosition = o.optString("bb_position", ""),
            reason = o.optString("reason", ""),
            timestamp = o.optString("timestamp", ""),
            executed = o.optInt("executed") == 1,
        )
    }
}

data class PortfolioPoint(
    val totalValue: Double,
    val totalReturnsPct: Double,
    val dayPnl: Double,
    val timestamp: String,
) {
    companion object {
        fun fromJson(o: JSONObject): PortfolioPoint = PortfolioPoint(
            totalValue = o.optDouble("total_value"),
            totalReturnsPct = o.optDouble("total_returns_pct"),
            dayPnl = o.optDouble("day_pnl"),
            timestamp = o.optString("timestamp", ""),
        )
    }
}

data class MarketStatus(
    val status: String,
    val open: Boolean,
)

data class Health(
    val status: String,
    val tradingActive: Boolean,
)

data class EmailConfig(
    val enabled: Boolean = false,
    val smtpServer: String = "smtp.gmail.com",
    val smtpPort: Int = 587,
    val sender: String = "",
    val password: String = "",
    val recipient: String = "",
)


