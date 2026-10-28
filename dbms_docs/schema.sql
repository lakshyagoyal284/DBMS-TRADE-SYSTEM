-- ============================================================================
--  PROJECT   : Automated Stock Trading System (Paper Trading Engine)
--  FILE      : schema.sql  —  Normalized relational schema (SQLite dialect)
--  PURPOSE   : DBMS project submission — DDL for all tables, indexes,
--              views, triggers and seed data.
--  NOTES     : - SQLite 3.31+ recommended (generated columns).
--              - PRAGMA foreign_keys must be enabled per connection.
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- 1. TABLES (3NF)
-- ---------------------------------------------------------------------------

-- 1.1 STRATEGY : lookup of trading strategies (was a string column before)
CREATE TABLE strategy (
    strategy_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,          -- e.g. 'RSI_BB'
    description     TEXT    NOT NULL DEFAULT ''
);

-- 1.2 STOCK : master table of securities
--     (Fixes legacy design where the watchlist was a comma-separated string)
CREATE TABLE stock (
    stock_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT    NOT NULL UNIQUE,          -- e.g. 'RELIANCE.NS'
    company_name    TEXT    NOT NULL DEFAULT '',
    exchange        TEXT    NOT NULL DEFAULT 'NSE',
    sector          TEXT,                             -- nullable on purpose
    is_active       INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1))
);

-- 1.3 WATCHLIST : stocks the engine monitors (1NF replacement for CSV blob)
CREATE TABLE watchlist (
    stock_id        INTEGER PRIMARY KEY
                    REFERENCES stock (stock_id)
                    ON DELETE CASCADE,
    added_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    is_active       INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1))
);

-- 1.4 CONFIG : engine parameters (key-value store; see documentation §3.4)
CREATE TABLE config (
    config_key      TEXT    PRIMARY KEY,
    config_value    TEXT    NOT NULL
);

-- 1.5 SIGNAL : strategy outputs (buy/sell/exit recommendations)
CREATE TABLE signal (
    signal_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id        INTEGER NOT NULL
                    REFERENCES stock (stock_id)
                    ON DELETE CASCADE,
    signal_type     TEXT    NOT NULL
                    CHECK (signal_type IN ('BUY', 'SELL', 'EXIT')),
    strength        REAL    NOT NULL DEFAULT 0.0
                    CHECK (strength BETWEEN 0.0 AND 100.0),
    price           REAL    NOT NULL
                    CHECK (price > 0),
    rsi             REAL
                    CHECK (rsi IS NULL OR rsi BETWEEN 0 AND 100),
    bb_position     REAL,                             -- % within Bollinger Bands
    volume_ratio    REAL
                    CHECK (volume_ratio IS NULL OR volume_ratio >= 0),
    reason          TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    executed        INTEGER NOT NULL DEFAULT 0          -- maintained by trigger
                    CHECK (executed IN (0, 1))
);

-- 1.6 TRADE : executed buy/sell transactions
CREATE TABLE trade (
    trade_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id        INTEGER NOT NULL
                    REFERENCES stock (stock_id)
                    ON DELETE RESTRICT,
    signal_id       INTEGER
                    REFERENCES signal (signal_id)
                    ON DELETE SET NULL,               -- optional link
    side            TEXT    NOT NULL
                    CHECK (side IN ('BUY', 'SELL')),
    quantity        INTEGER NOT NULL
                    CHECK (quantity > 0),
    price           REAL    NOT NULL
                    CHECK (price > 0),
    trade_value     REAL    GENERATED ALWAYS AS (quantity * price) STORED,
    slippage        REAL    NOT NULL DEFAULT 0.0
                    CHECK (slippage >= 0),
    realized_pnl     REAL   NOT NULL DEFAULT 0.0,      -- only meaningful on SELL
    realized_pnl_pct REAL   NOT NULL DEFAULT 0.0,
    reason          TEXT    NOT NULL DEFAULT '',
    executed_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 1.7 HOLDING : one row per currently open position
--     (P&L columns removed — computed in views; see normalization walkthrough)
CREATE TABLE holding (
    stock_id        INTEGER PRIMARY KEY
                    REFERENCES stock (stock_id)
                    ON DELETE CASCADE,
    quantity        INTEGER NOT NULL
                    CHECK (quantity > 0),
    avg_buy_price   REAL    NOT NULL
                    CHECK (avg_buy_price > 0),
    current_price   REAL    NOT NULL DEFAULT 0.0,     -- live cache, see docs §3.5
    entry_date      TEXT    NOT NULL,
    strategy_id     INTEGER
                    REFERENCES strategy (strategy_id)
                    ON DELETE SET NULL,
    entry_rsi       REAL
                    CHECK (entry_rsi IS NULL OR entry_rsi BETWEEN 0 AND 100),
    last_updated    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 1.8 PRICE_SNAPSHOT : time series of market prices
CREATE TABLE price_snapshot (
    snapshot_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id        INTEGER NOT NULL
                    REFERENCES stock (stock_id)
                    ON DELETE CASCADE,
    price           REAL    NOT NULL
                    CHECK (price > 0),
    high            REAL,
    low             REAL,
    volume          INTEGER
                    CHECK (volume IS NULL OR volume >= 0),
    rsi             REAL
                    CHECK (rsi IS NULL OR rsi BETWEEN 0 AND 100),
    captured_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 1.9 PORTFOLIO_HISTORY : periodic portfolio value snapshots
--     (unrealized_pnl / total_pnl removed — derived in a view)
CREATE TABLE portfolio_history (
    history_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at     TEXT    NOT NULL,
    total_value     REAL    NOT NULL,
    cash_balance    REAL    NOT NULL,
    invested_value  REAL    NOT NULL,
    realized_pnl    REAL    NOT NULL DEFAULT 0.0,
    day_pnl         REAL    NOT NULL DEFAULT 0.0,
    CHECK (cash_balance >= 0)
);

-- 1.10 PRICE_ALERT : last notified price per stock (deduplication state)
CREATE TABLE price_alert (
    stock_id            INTEGER PRIMARY KEY
                        REFERENCES stock (stock_id)
                        ON DELETE CASCADE,
    last_notified_price REAL    NOT NULL,
    last_notified_at    TEXT    NOT NULL
);

-- ---------------------------------------------------------------------------
-- 2. INDEXES (query paths used by the application)
-- ---------------------------------------------------------------------------

CREATE INDEX idx_signal_stock_time    ON signal (stock_id, created_at DESC);
CREATE INDEX idx_signal_executed      ON signal (executed) WHERE executed = 0;
CREATE INDEX idx_trade_stock_time     ON trade  (stock_id, executed_at DESC);
CREATE INDEX idx_trade_side           ON trade  (side, executed_at DESC);
CREATE INDEX idx_price_snapshot_stock ON price_snapshot (stock_id, captured_at DESC);
CREATE INDEX idx_watchlist_active     ON watchlist (is_active) WHERE is_active = 1;

-- ---------------------------------------------------------------------------
-- 3. VIEWS (derived data instead of stored/redundant columns)
-- ---------------------------------------------------------------------------

-- 3.1 Live P&L per holding (replaces stored unrealized_pnl columns)
CREATE VIEW vw_holding_pnl AS
SELECT  h.stock_id,
        s.symbol,
        h.quantity,
        h.avg_buy_price,
        h.current_price,
        h.current_price * h.quantity                       AS market_value,
        (h.current_price - h.avg_buy_price) * h.quantity   AS unrealized_pnl,
        CASE WHEN h.avg_buy_price > 0 THEN
             ROUND((h.current_price - h.avg_buy_price)
                   / h.avg_buy_price * 100.0, 2)
        END                                                AS unrealized_pnl_pct,
        h.entry_date,
        st.name                                            AS strategy_name
FROM holding h
JOIN stock s    ON s.stock_id = h.stock_id
LEFT JOIN strategy st ON st.strategy_id = h.strategy_id;

-- 3.2 Latest signal per stock (the app's join + subquery, now reusable)
CREATE VIEW vw_latest_signal AS
SELECT si.*
FROM signal si
JOIN (SELECT stock_id, MAX(created_at) AS max_ts
      FROM signal GROUP BY stock_id) latest
  ON si.stock_id = latest.stock_id
 AND si.created_at = latest.max_ts
ORDER BY si.created_at DESC;

-- 3.3 Portfolio history with derived unrealized/total P&L
CREATE VIEW vw_portfolio_history AS
SELECT  history_id,
        snapshot_at,
        total_value,
        cash_balance,
        invested_value,
        realized_pnl,
        total_value - cash_balance - invested_value        AS unrealized_pnl,
        (total_value - cash_balance - invested_value)
            + realized_pnl                                 AS total_pnl,
        day_pnl
FROM portfolio_history;

-- 3.4 Active watchlist with stock details
CREATE VIEW vw_watchlist AS
SELECT  s.stock_id,
        s.symbol,
        s.company_name,
        s.sector,
        w.added_at
FROM watchlist w
JOIN stock s ON s.stock_id = w.stock_id
WHERE w.is_active = 1 AND s.is_active = 1
ORDER BY s.symbol;

-- 3.5 Aggregate trade performance (dashboard summary query)
CREATE VIEW vw_trade_performance AS
SELECT  COUNT(*)                                                    AS total_trades,
        SUM(CASE WHEN side = 'SELL' THEN 1 ELSE 0 END)              AS sell_trades,
        SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END)           AS winning_trades,
        SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END)           AS losing_trades,
        ROUND(COALESCE(SUM(CASE WHEN realized_pnl > 0
                                 THEN realized_pnl END), 0), 2)     AS gross_profit,
        ROUND(COALESCE(SUM(CASE WHEN realized_pnl < 0
                                 THEN realized_pnl END), 0), 2)     AS gross_loss,
        ROUND(COALESCE(SUM(CASE WHEN side = 'SELL'
                                 THEN realized_pnl END), 0), 2)     AS net_realized_pnl
FROM trade;

-- ---------------------------------------------------------------------------
-- 4. TRIGGERS (enforcing business rules in the database itself)
-- ---------------------------------------------------------------------------

-- 4.1 Mark a signal as executed when a trade referencing it is recorded
CREATE TRIGGER trg_trade_marks_signal_executed
AFTER INSERT ON trade
WHEN NEW.signal_id IS NOT NULL
BEGIN
    UPDATE signal
    SET executed = 1
    WHERE signal_id = NEW.signal_id;
END;

-- 4.2 A holding row must always represent an OPEN position
CREATE TRIGGER trg_holding_insert_positive_qty
BEFORE INSERT ON holding
WHEN NEW.quantity <= 0
BEGIN
    SELECT RAISE(ABORT, 'holding.quantity must be > 0; closed positions must be DELETEd');
END;

CREATE TRIGGER trg_holding_update_positive_qty
BEFORE UPDATE OF quantity ON holding
WHEN NEW.quantity <= 0
BEGIN
    SELECT RAISE(ABORT, 'holding.quantity must be > 0; closed positions must be DELETEd');
END;

-- 4.3 Auto-soft-disable stocks after a SELL signal arrives
--     (illustrates trigger-based workflow; remove if unwanted)
CREATE TRIGGER trg_signal_updates_stock_state
AFTER INSERT ON signal
WHEN NEW.signal_type = 'SELL'
BEGIN
    UPDATE price_alert
    SET last_notified_price = NEW.price,
        last_notified_at    = NEW.created_at
    WHERE stock_id = NEW.stock_id;
END;

-- ---------------------------------------------------------------------------
-- 5. SEED DATA (minimal, for demonstrating views/queries)
-- ---------------------------------------------------------------------------

INSERT INTO strategy (name, description) VALUES
    ('RSI_BB', 'RSI + Bollinger Bands mean-reversion strategy'),
    ('MACD_X', 'MACD crossover trend-following strategy'),
    ('MANUAL', 'Manual / user-initiated orders');

INSERT INTO stock (symbol, company_name, exchange, sector) VALUES
    ('RELIANCE.NS',  'Reliance Industries Ltd.', 'NSE', 'Energy'),
    ('TCS.NS',       'Tata Consultancy Services','NSE', 'IT Services'),
    ('HDFCBANK.NS',  'HDFC Bank Ltd.',           'NSE', 'Banking'),
    ('INFY.NS',      'Infosys Ltd.',             'NSE', 'IT Services'),
    ('TATAMOTORS.NS','Tata Motors Ltd.',         'NSE', 'Automobile');

INSERT INTO watchlist (stock_id) VALUES (1), (2), (3), (4), (5);

INSERT INTO config (config_key, config_value) VALUES
    ('initial_capital',   '100000'),
    ('current_cash',      '100000'),
    ('max_position_pct',  '15'),
    ('stop_loss_pct',     '3'),
    ('take_profit_pct',   '5'),
    ('max_positions',     '5');

-- Demo rows so every view returns data out of the box ----------------------
INSERT INTO signal (stock_id, signal_type, strength, price, rsi, bb_position,
                    volume_ratio, reason)
VALUES (1, 'BUY', 72.5, 2500.00, 28.4, 5.0, 1.8, 'RSI oversold + price at lower BB'),
       (2, 'BUY', 65.0, 3900.00, 31.2, 12.0, 1.5, 'RSI oversold');

INSERT INTO trade (stock_id, signal_id, side, quantity, price, slippage, reason)
VALUES (1, 1, 'BUY', 6, 2500.00, 2.50, 'Signal #1 executed');

INSERT INTO holding (stock_id, quantity, avg_buy_price, current_price,
                     entry_date, strategy_id, entry_rsi)
VALUES (1, 6, 2500.00, 2540.00, datetime('now'), 1, 28.4);

-- ---------------------------------------------------------------------------
-- 6. LEGACY -> NORMALIZED MIGRATION (reference; run once against old DB)
-- ---------------------------------------------------------------------------
-- INSERT INTO stock (symbol)
--     WITH RECURSIVE split(sym, rest) AS (
--         SELECT '', (SELECT config_value FROM config WHERE config_key='watchlist') || ','
--         UNION ALL
--         SELECT substr(rest, 1, instr(rest, ',') - 1),
--                substr(rest, instr(rest, ',') + 1)
--         FROM split WHERE rest <> '')
--     SELECT sym FROM split WHERE sym <> '';
--
-- INSERT INTO signal (stock_id, signal_type, strength, price, rsi, bb_position,
--                     volume_ratio, reason, created_at, executed)
--     SELECT s.stock_id, signal_type, strength, price, rsi,
--            CASE WHEN bb_position GLOB '*[^0-9.]*' THEN NULL
--                 ELSE CAST(bb_position AS REAL) END,
--            volume_ratio, reason, timestamp, executed
--     FROM signals lg JOIN stock s ON s.symbol = lg.symbol;
-- (analogous INSERT ... SELECT statements for trade, holding, price_snapshot,
--  portfolio_history, price_alert)
