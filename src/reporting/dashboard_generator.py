from __future__ import annotations

import html
import json
from pathlib import Path

from src.portfolio.ledger_store import load_positions, load_trades


SNAPSHOT_DIR = Path("data/snapshots")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
DASHBOARD_FILE = REPORTS_DIR / "dashboard.html"


def load_latest_snapshots(limit: int = 10) -> list[dict]:
    snapshot_files = sorted(SNAPSHOT_DIR.glob("market_snapshot_*.json"), reverse=True)[:limit]
    snapshots: list[dict] = []

    for path in snapshot_files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["_file_name"] = path.name
            snapshots.append(payload)
        except Exception:
            continue

    return snapshots


def format_float(value: object) -> str:
    try:
        return f"{float(value):,.6f}"
    except Exception:
        return "-"


def render_table(headers: list[str], rows: list[list[object]]) -> str:
    thead = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)

    body_rows = []
    for row in rows:
        cols = "".join(f"<td>{html.escape(str(col))}</td>" for col in row)
        body_rows.append(f"<tr>{cols}</tr>")

    tbody = "".join(body_rows) if body_rows else f'<tr><td colspan="{len(headers)}">No data</td></tr>'
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>"


def build_dashboard_html() -> str:
    positions = load_positions()
    trades = load_trades()
    snapshots = load_latest_snapshots(limit=10)

    latest_snapshot = snapshots[0] if snapshots else {}
    account_state = latest_snapshot.get("account_state") or {}
    portfolio_summary = latest_snapshot.get("portfolio_summary") or {}

    open_positions = [p for p in positions if p.get("status") == "OPEN"]
    recent_trades = sorted(
        trades,
        key=lambda x: x.get("timestamp_utc", ""),
        reverse=True,
    )[:10]

    snapshot_rows = []
    for snapshot in snapshots:
        account = snapshot.get("account_state") or {}
        snapshot_rows.append(
            [
                snapshot.get("_file_name", "-"),
                snapshot.get("timestamp_utc", "-"),
                snapshot.get("candidate_markets_count", "-"),
                account.get("equity_estimate", "-"),
                account.get("cash_available", "-"),
                snapshot.get("kill_switch_triggered", "-"),
            ]
        )

    position_rows = []
    for position in open_positions:
        position_rows.append(
            [
                position.get("market_id", "-"),
                position.get("question", "-"),
                position.get("entry_price", "-"),
                position.get("current_price", "-"),
                position.get("shares", "-"),
                position.get("stop_loss_price", "-"),
                position.get("take_profit_price", "-"),
                position.get("opened_at_utc", "-"),
            ]
        )

    trade_rows = []
    for trade in recent_trades:
        trade_rows.append(
            [
                trade.get("timestamp_utc", "-"),
                trade.get("market_id", "-"),
                trade.get("action", "-"),
                trade.get("price", "-"),
                trade.get("shares", "-"),
                trade.get("notional_usd", "-"),
            ]
        )

    summary_cards = [
        ("Cash Available", format_float(account_state.get("cash_available"))),
        ("Capital Committed", format_float(account_state.get("capital_committed"))),
        ("Open Market Value", format_float(account_state.get("open_market_value"))),
        ("Realized PnL", format_float(account_state.get("realized_pnl"))),
        ("Unrealized PnL", format_float(account_state.get("unrealized_pnl"))),
        ("Equity Estimate", format_float(account_state.get("equity_estimate"))),
        ("Open Positions", account_state.get("open_positions_count", "-")),
        ("Closed Positions", account_state.get("closed_positions_count", "-")),
        ("Portfolio Cost", format_float(portfolio_summary.get("total_cost"))),
        ("Portfolio Market Value", format_float(portfolio_summary.get("total_market_value"))),
        ("Portfolio Unrealized PnL", format_float(portfolio_summary.get("total_unrealized_pnl"))),
        ("Kill Switch", latest_snapshot.get("kill_switch_triggered", "-")),
    ]

    cards_html = "".join(
        f"""
        <div class="card">
            <div class="card-title">{html.escape(str(title))}</div>
            <div class="card-value">{html.escape(str(value))}</div>
        </div>
        """
        for title, value in summary_cards
    )

    open_positions_table = render_table(
        [
            "Market ID",
            "Question",
            "Entry Price",
            "Current Price",
            "Shares",
            "Stop Loss",
            "Take Profit",
            "Opened At UTC",
        ],
        position_rows,
    )

    recent_trades_table = render_table(
        ["Timestamp UTC", "Market ID", "Action", "Price", "Shares", "Notional USD"],
        trade_rows,
    )

    recent_snapshots_table = render_table(
        ["Snapshot File", "Timestamp UTC", "Candidate Markets", "Equity", "Cash", "Kill Switch"],
        snapshot_rows,
    )

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Polymarket Bot Dashboard</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 24px;
            background: #0f172a;
            color: #e2e8f0;
        }}
        h1, h2 {{
            margin-bottom: 12px;
        }}
        .muted {{
            color: #94a3b8;
            margin-bottom: 20px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .card {{
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 16px;
        }}
        .card-title {{
            font-size: 12px;
            color: #94a3b8;
            margin-bottom: 8px;
            text-transform: uppercase;
        }}
        .card-value {{
            font-size: 22px;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 28px;
            background: #111827;
        }}
        th, td {{
            border: 1px solid #1f2937;
            padding: 10px;
            text-align: left;
            vertical-align: top;
        }}
        th {{
            background: #1e293b;
        }}
        tr:nth-child(even) {{
            background: #0b1220;
        }}
    </style>
</head>
<body>
    <h1>Polymarket Bot Dashboard</h1>
    <div class="muted">Generated from local bot data and snapshots.</div>

    <h2>Account Summary</h2>
    <div class="grid">{cards_html}</div>

    <h2>Open Positions</h2>
    {open_positions_table}

    <h2>Recent Trades</h2>
    {recent_trades_table}

    <h2>Recent Snapshots</h2>
    {recent_snapshots_table}
</body>
</html>
"""


def generate_dashboard() -> str:
    html_content = build_dashboard_html()
    DASHBOARD_FILE.write_text(html_content, encoding="utf-8")
    return str(DASHBOARD_FILE)
