# ER Diagram — Automated Stock Trading System

> Render the Mermaid block below at [mermaid.live](https://mermaid.live), or paste this file into any Mermaid-aware viewer (GitHub renders it natively).

## 1. Entity–Relationship Diagram

![ER Diagram — Automated Stock Trading System](er_diagram.png)

*Figure 1 — ER diagram of the normalized schema (10 entities, 8 relationships). A print-quality vector version is provided as `er_diagram.svg`, and the generator script is `generate_er_diagram.py` (run `python dbms_docs/generate_er_diagram.py` to regenerate after schema changes).*

### Mermaid source (editable online)

> Render the Mermaid block below at [mermaid.live](https://mermaid.live) if you want to restyle the diagram (GitHub also renders it natively).

```mermaid
erDiagram
    STOCK ||--o{ WATCHLIST : "is tracked in"
    STOCK ||--o{ SIGNAL : "generates"
    STOCK ||--o{ TRADE : "is traded as"
    STOCK ||--o{ HOLDING : "is held as"
    STOCK ||--o{ PRICE_SNAPSHOT : "has"
    STOCK ||--o{ PRICE_ALERT : "has"
    STRATEGY ||--o{ HOLDING : "opened under"
    SIGNAL |o--o| TRADE : "triggers"

    STRATEGY {
        int strategy_id PK "AUTOINCREMENT"
        string name UK "unique"
        string description
    }
    STOCK {
        int stock_id PK "AUTOINCREMENT"
        string symbol UK "e.g. RELIANCE.NS"
        string company_name
        string exchange "default NSE"
        string sector
        bool is_active
    }
    WATCHLIST {
        int stock_id PK_FK "references stock"
        datetime added_at
        bool is_active
    }
    CONFIG {
        string config_key PK
        string config_value
        string note "no FK - standalone key-value store"
    }
    SIGNAL {
        int signal_id PK "AUTOINCREMENT"
        int stock_id FK
        string signal_type "BUY|SELL|EXIT"
        float strength "0-100"
        float price "> 0"
        float rsi "0-100, nullable"
        float bb_position "nullable"
        float volume_ratio "nullable"
        string reason
        datetime created_at
        bool executed "0|1, trigger-maintained"
    }
    TRADE {
        int trade_id PK "AUTOINCREMENT"
        int stock_id FK
        int signal_id FK "nullable"
        string side "BUY|SELL"
        int quantity "> 0"
        float price "> 0"
        float trade_value "generated column qty*price"
        float slippage
        float realized_pnl "SELL only"
        float realized_pnl_pct
        string reason
        datetime executed_at
    }
    HOLDING {
        int stock_id PK_FK "references stock, 1:1 open position"
        int quantity "> 0"
        float avg_buy_price "> 0"
        float current_price "live cache"
        datetime entry_date
        int strategy_id FK "nullable"
        float entry_rsi "nullable"
        datetime last_updated
    }
    PRICE_SNAPSHOT {
        int snapshot_id PK "AUTOINCREMENT"
        int stock_id FK
        float price "> 0"
        float high
        float low
        int volume
        float rsi "nullable"
        datetime captured_at
        string note "grows unbounded, time series"
    }
    PORTFOLIO_HISTORY {
        int history_id PK "AUTOINCREMENT"
        datetime snapshot_at
        float total_value
        float cash_balance ">= 0"
        float invested_value
        float realized_pnl
        float day_pnl
        string note "no FK - portfolio-level event log"
    }
    PRICE_ALERT {
        int stock_id PK_FK "references stock"
        float last_notified_price
        datetime last_notified_at
    }
```

## 2. Entities and Their Role

| Entity | Purpose | Real-world meaning |
|---|---|---|
| **STOCK** | Central master entity | A tradable security (e.g., RELIANCE.NS) |
| **STRATEGY** | Lookup entity | Trading strategy that produced a signal / opened a position |
| **WATCHLIST** | Associative subset | Stocks currently monitored by the engine |
| **SIGNAL** | Event entity | A BUY/SELL/EXIT recommendation from the strategy |
| **TRADE** | Event entity | An executed order with quantity and price |
| **HOLDING** | State entity | Current open position per stock (max 1 per stock) |
| **PRICE_SNAPSHOT** | Time-series entity | Market price recorded at intervals |
| **PORTFOLIO_HISTORY** | Time-series entity | Portfolio totals recorded at intervals |
| **PRICE_ALERT** | State entity | Deduplication state for rise alerts |
| **CONFIG** | Key–value store | Engine parameters (capital, limits, flags) |

## 3. Relationships (with cardinality and participation)

| # | Relationship | Cardinality | Participation | Notes |
|---|---|---|---|---|
| R1 | STOCK – WATCHLIST | 1 : 1 (0..1) | Partial on both | Only monitored stocks appear; watchlist member **is-a** stock (subset/specialization pattern) |
| R2 | STOCK – SIGNAL | 1 : N | Stock partial, signal total | A stock may generate many signals over time |
| R3 | STOCK – TRADE | 1 : N | Stock partial, trade total | |
| R4 | STOCK – HOLDING | 1 : 1 (0..1) | Partial | At most one open position per symbol |
| R5 | STOCK – PRICE_SNAPSHOT | 1 : N | | Time series |
| R6 | STOCK – PRICE_ALERT | 1 : 1 (0..1) | Partial | |
| R7 | STRATEGY – HOLDING | 1 : N | Optional | Which strategy opened the position |
| R8 | SIGNAL – TRADE | 1 : 0..1 | Optional on both | A trade may be signal-driven or manual |
| R9 | PORTFOLIO_HISTORY / CONFIG | — | — | Standalone; no relationship to other entities (portfolio-level and system-level facts) |

## 4. Design Decisions Worth Defending in Your Viva

1. **STOCK as hub.** Every event table points to `stock_id` instead of repeating `symbol` text. This is the fix for the legacy design where the watchlist lived as a comma-separated string inside `config` (a 1NF violation).
2. **HOLDING keyed by `stock_id` (1:1).** A stock either has an open position or it doesn't; quantity>0 is enforced by CHECK + triggers, and closed positions are *deleted*, not zeroed.
3. **SIGNAL 1—0..1 TRADE.** Not every signal becomes a trade (capital limits, max positions); not every trade comes from a signal (manual orders). Implemented as a nullable FK.
4. **Derived data removed from tables, computed in views.** `unrealized_pnl`, `current_value`, `total_pnl`, `trade_value` semantics — see `schema_documentation.md` §5 for the normalization argument.
5. **CONFIG and PORTFOLIO_HISTORY stay FK-free.** Forcing a FK here would create artificial entities; they are system/portfolio-level logs.
6. **executed flag maintained by trigger** (`trg_trade_marks_signal_executed`) — demonstrates trigger-based workflow integrity instead of trusting application code.
7. **Timestamps are ISO-8601 TEXT.** Deliberate for SQLite; if porting to MySQL/PostgreSQL, change to `DATETIME`/`TIMESTAMP` — see `schema_documentation.md` §7.

## 5. How to produce the diagram image for your report

- **Fastest:** open <https://mermaid.live>, paste the block above, export PNG/SVG.
- **Alternative tools:** draw.io (recreate the boxes from §2/§3), dbdiagram.io (its own DSL, quick to mirror the same schema), or Graphviz.
- **Report tip:** show the ER diagram *before* the schema and mention that the schema is in **3NF** — examiners look for that word.
