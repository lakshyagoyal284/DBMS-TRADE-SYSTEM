"""
ER Diagram Generator
====================
Renders the ER diagram of the normalized trading-system schema as a
high-resolution PNG + SVG using matplotlib only (no Graphviz needed).

Usage:
    python dbms_docs/generate_er_diagram.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from pathlib import Path

OUT_DIR = Path(__file__).parent

# ----------------------------------------------------------------------------
# Entity definitions: name -> (attributes, PK index, FK indexes)
# ----------------------------------------------------------------------------
ENTITIES = {
    "STRATEGY": {
        "pos": (0.3, 4.15),
        "attrs": ["strategy_id (PK)", "name (UK)", "description"],
    },
    "STOCK": {
        "pos": (4.35, 4.35),
        "attrs": [
            "stock_id (PK)",
            "symbol (UK)",
            "company_name",
            "exchange",
            "sector",
            "is_active",
        ],
    },
    "WATCHLIST": {
        "pos": (9.0, 5.35),
        "attrs": ["stock_id (PK, FK)", "added_at", "is_active"],
    },
    "SIGNAL": {
        "pos": (9.0, 3.05),
        "attrs": [
            "signal_id (PK)",
            "stock_id (FK)",
            "signal_type",
            "strength",
            "price",
            "rsi",
            "bb_position",
            "volume_ratio",
            "reason",
            "created_at",
            "executed",
        ],
    },
    "TRADE": {
        "pos": (9.0, 0.30),
        "attrs": [
            "trade_id (PK)",
            "stock_id (FK)",
            "signal_id (FK)",
            "side",
            "quantity",
            "price",
            "trade_value (G)",
            "slippage",
            "realized_pnl",
            "reason",
            "executed_at",
        ],
    },
    "HOLDING": {
        "pos": (4.35, 1.95),
        "attrs": [
            "stock_id (PK, FK)",
            "quantity",
            "avg_buy_price",
            "current_price",
            "entry_date",
            "strategy_id (FK)",
            "entry_rsi",
        ],
    },
    "PRICE_SNAPSHOT": {
        "pos": (0.3, 0.30),
        "attrs": [
            "snapshot_id (PK)",
            "stock_id (FK)",
            "price",
            "high",
            "low",
            "volume",
            "rsi",
            "captured_at",
        ],
    },
    "PORTFOLIO_HISTORY": {
        "pos": (4.35, 0.30),
        "attrs": [
            "history_id (PK)",
            "snapshot_at",
            "total_value",
            "cash_balance",
            "invested_value",
            "realized_pnl",
            "day_pnl",
        ],
    },
    "PRICE_ALERT": {
        "pos": (13.3, 5.35),
        "attrs": ["stock_id (PK, FK)", "last_notified_price", "last_notified_at"],
    },
    "CONFIG": {
        "pos": (13.3, 3.35),
        "attrs": ["config_key (PK)", "config_value", "(no FK - system-level)"],
    },
}

# Relationships: (from_entity, to_entity, label, from_side, to_side)
# Cardinality is drawn as crow's-foot style markers.
RELATIONSHIPS = [
    ("STOCK", "WATCHLIST", "tracked in", "right", "left"),
    ("STOCK", "SIGNAL", "generates", "right", "left"),
    ("STOCK", "TRADE", "traded as", "bottom", "left"),
    ("STOCK", "HOLDING", "held as", "bottom", "top"),
    ("STOCK", "PRICE_SNAPSHOT", "has prices", "bottom", "top"),
    ("STOCK", "PRICE_ALERT", "alert state", "right", "left"),
    ("STRATEGY", "HOLDING", "opened under", "right", "top"),
    ("SIGNAL", "TRADE", "triggers", "bottom", "top"),
]

# Cardinality labels per relationship (from-side, to-side)
CARDINALITY = {
    ("STOCK", "WATCHLIST"): ("1", "0..1"),
    ("STOCK", "SIGNAL"): ("1", "N"),
    ("STOCK", "TRADE"): ("1", "N"),
    ("STOCK", "HOLDING"): ("1", "0..1"),
    ("STOCK", "PRICE_SNAPSHOT"): ("1", "N"),
    ("STOCK", "PRICE_ALERT"): ("1", "0..1"),
    ("STRATEGY", "HOLDING"): ("1", "N"),
    ("SIGNAL", "TRADE"): ("0..1", "N"),
}

# ----------------------------------------------------------------------------
# Drawing helpers
# ----------------------------------------------------------------------------
ENTITY_W = 3.15          # box width in axis units
LINE_H = 0.315           # per attribute row height
TITLE_H = 0.46           # header band height
COL = dict(
    header="#1f4e79",    # dark blue
    header_txt="white",
    pk="#1f4e79",        # PK rows tinted
    pk_txt="white",
    fk="#dce6f1",        # FK rows tinted
    body="white",
    edge="#17375e",
    rel="#7f7f7f",
)


def entity_geometry(name):
    """Return (x, y, w, h) of an entity box (y = top)."""
    attrs = ENTITIES[name]["attrs"]
    x, y_top = ENTITIES[name]["pos"]
    h = TITLE_H + LINE_H * len(attrs)
    return x, y_top, ENTITY_W, h


def draw_entity(ax, name):
    x, y_top, w, h = entity_geometry(name)
    attrs = ENTITIES[name]["attrs"]
    y = y_top

    # Header band
    ax.add_patch(Rectangle((x, y - TITLE_H), w, TITLE_H,
                           facecolor=COL["header"], edgecolor=COL["edge"],
                           linewidth=1.4, zorder=3))
    ax.text(x + w / 2, y - TITLE_H / 2, name, ha="center", va="center",
            fontsize=10.5, fontweight="bold", color=COL["header_txt"], zorder=4)

    # Attribute rows
    for i, attr in enumerate(attrs):
        y -= LINE_H
        if "(PK" in attr:
            fc, tc = COL["pk"], COL["pk_txt"]
        elif "FK" in attr:
            fc, tc = COL["fk"], "#17375e"
        else:
            fc, tc = COL["body"], "#1a1a1a"
        ax.add_patch(Rectangle((x, y), w, LINE_H,
                               facecolor=fc, edgecolor=COL["edge"],
                               linewidth=0.8, zorder=3))
        ax.text(x + 0.14, y + LINE_H / 2, attr, ha="left", va="center",
                fontsize=8.2, color=tc, zorder=4,
                family="DejaVu Sans Mono", fontweight="bold" if "(PK" in attr else "normal")


def anchor_point(name, side):
    """Connection point on an entity's border for a given side."""
    x, y_top, w, h = entity_geometry(name)
    if side == "left":
        return (x, y_top - h / 2)
    if side == "right":
        return (x + w, y_top - h / 2)
    if side == "top":
        return (x + w / 2, y_top)
    if side == "bottom":
        return (x + w / 2, y_top - h)


def draw_relationship(ax, frm, to, label, side_f, side_t):
    (x1, y1) = anchor_point(frm, side_f)
    (x2, y2) = anchor_point(to, side_t)

    # Orthogonal (elbow) routing via a midpoint
    if side_f in ("left", "right") and side_t in ("left", "right"):
        xm = (x1 + x2) / 2
        pts = [(x1, y1), (xm, y1), (xm, y2), (x2, y2)]
    elif side_f in ("top", "bottom") and side_t in ("top", "bottom"):
        ym = (y1 + y2) / 2
        pts = [(x1, y1), (x1, ym), (x2, ym), (x2, y2)]
    else:  # one horizontal, one vertical
        pts = [(x1, y1), (x1, y2), (x2, y2)]

    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=COL["rel"], linewidth=1.6, zorder=1)

    # Crow's foot at the "many" end, single tick at the "1" end
    c_f, c_t = CARDINALITY.get((frm, to), ("1", "N"))

    def marker(px, py, card, dx, dy):
        # unit direction toward the entity
        if card in ("N", "0..1"):
            if dx == 0 and dy == 0:
                return
            if dx != 0:
                s = 1 if dx > 0 else -1
                if card == "N":  # crow's foot: 3 prongs
                    for off in (-0.10, 0.0, 0.10):
                        ax.plot([px - s * 0.42, px],
                                [py + off, py],
                                color=COL["rel"], linewidth=1.4, zorder=1)
                else:            # circle for optional-one
                    ax.plot([px - s * 0.30, px], [py, py],
                            color=COL["rel"], linewidth=1.2, zorder=1)
                    ax.add_patch(plt.Circle((px - s * 0.36, py), 0.06,
                                            fill=False, color=COL["rel"],
                                            linewidth=1.2, zorder=1))
            else:
                s = 1 if dy > 0 else -1
                if card == "N":
                    for off in (-0.10, 0.0, 0.10):
                        ax.plot([px + off, px],
                                [py - s * 0.42, py],
                                color=COL["rel"], linewidth=1.4, zorder=1)
                else:
                    ax.plot([px, px], [py - s * 0.30, py],
                            color=COL["rel"], linewidth=1.2, zorder=1)
                    ax.add_patch(plt.Circle((px, py - s * 0.36), 0.06,
                                            fill=False, color=COL["rel"],
                                            linewidth=1.2, zorder=1))
        else:  # "1" -> single tick
            if dx != 0:
                s = 1 if dx > 0 else -1
                ax.plot([px - s * 0.16, px - s * 0.16], [py - 0.10, py + 0.10],
                        color=COL["rel"], linewidth=1.6, zorder=1)
            else:
                s = 1 if dy > 0 else -1
                ax.plot([px - 0.10, px + 0.10], [py - s * 0.16, py - s * 0.16],
                        color=COL["rel"], linewidth=1.6, zorder=1)

    (xa, ya) = pts[0]
    (xb, yb) = pts[-1]
    dx_a = 1 if side_f == "right" else (-1 if side_f == "left" else 0)
    dy_a = 1 if side_f == "bottom" else (-1 if side_f == "top" else 0)
    dx_b = 1 if side_t == "right" else (-1 if side_t == "left" else 0)
    dy_b = 1 if side_t == "bottom" else (-1 if side_t == "top" else 0)
    marker(xa, ya, c_f, dx_a, dy_a)
    marker(xb, yb, c_t, dx_b, dy_b)

    # Label near the middle of the elbow
    lx = (x1 + x2) / 2
    ly = (y1 + y2) / 2
    ax.text(lx, ly + 0.12, label, ha="center", va="bottom",
            fontsize=8.0, style="italic", color="#404040", zorder=5,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                      edgecolor="none", alpha=0.85))


# ----------------------------------------------------------------------------
# Render
# ----------------------------------------------------------------------------
def main():
    fig, ax = plt.subplots(figsize=(17.5, 11.0), dpi=100)

    for name in ENTITIES:
        draw_entity(ax, name)
    for frm, to, label, side_f, side_t in RELATIONSHIPS:
        draw_relationship(ax, frm, to, label, side_f, side_t)

    ax.set_title("ER Diagram — Automated Stock Trading System (Normalized to 3NF/BCNF)",
                 fontsize=15, fontweight="bold", pad=18, color="#17375e")

    # Legend
    ax.add_patch(Rectangle((13.3, 1.55), 3.15, 1.55,
                           facecolor="#f5f7fa", edgecolor="#b0b8c4",
                           linewidth=1.0, zorder=2))
    ax.text(13.42, 2.86, "Legend", fontsize=9, fontweight="bold", zorder=3)
    ax.add_patch(Rectangle((13.42, 2.52), 0.28, 0.20, facecolor=COL["pk"],
                           edgecolor=COL["edge"], zorder=3))
    ax.text(13.80, 2.62, "Primary key", fontsize=8, va="center", zorder=3)
    ax.add_patch(Rectangle((13.42, 2.22), 0.28, 0.20, facecolor=COL["fk"],
                           edgecolor=COL["edge"], zorder=3))
    ax.text(13.80, 2.32, "Foreign key", fontsize=8, va="center", zorder=3)
    ax.text(13.42, 1.98, "—||  one      —<  many", fontsize=8, va="center",
            zorder=3, family="DejaVu Sans Mono")

    ax.set_xlim(0, 16.8)
    ax.set_ylim(0, 7.6)
    ax.invert_yaxis()
    ax.axis("off")
    ax.set_aspect("equal")

    fig.tight_layout()
    png = OUT_DIR / "er_diagram.png"
    svg = OUT_DIR / "er_diagram.svg"
    fig.savefig(png, dpi=200, bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Written: {png}")
    print(f"Written: {svg}")


if __name__ == "__main__":
    main()
