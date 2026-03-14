from __future__ import annotations

import html
import json
import subprocess
from pathlib import Path

from src.config.settings import get_settings
from src.portfolio.ledger_store import load_positions, load_trades


SNAPSHOT_DIR = Path("data/snapshots")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
DASHBOARD_FILE = REPORTS_DIR / "dashboard.html"


def load_latest_snapshots(limit: int = 20) -> list[dict]:
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


def build_equity_svg(snapshots: list[dict]) -> str:
    points: list[tuple[str, float]] = []

    for snapshot in reversed(snapshots):
        account = snapshot.get("account_state") or {}
        equity = account.get("equity_estimate")
        timestamp = snapshot.get("timestamp_utc", "-")
        if equity is None:
            continue
        try:
            points.append((timestamp, float(equity)))
        except Exception:
            continue

    if len(points) < 2:
        return '<div class="muted">Not enough equity history to render chart.</div>'

    width = 900
    height = 260
    padding = 30

    values = [value for _, value in points]
    min_value = min(values)
    max_value = max(values)

    if max_value == min_value:
        max_value += 1.0
        min_value -= 1.0

    def scale_x(index: int) -> float:
        usable_width = width - (padding * 2)
        return padding + (usable_width * index / max(1, len(points) - 1))

    def scale_y(value: float) -> float:
        usable_height = height - (padding * 2)
        ratio = (value - min_value) / (max_value - min_value)
        return height - padding - (ratio * usable_height)

    polyline_points = " ".join(
        f"{scale_x(idx):.2f},{scale_y(value):.2f}"
        for idx, (_, value) in enumerate(points)
    )

    circles = []
    labels = []
    for idx, (timestamp, value) in enumerate(points):
        x = scale_x(idx)
        y = scale_y(value)
        circles.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="#38bdf8">'
            f'<title>{html.escape(timestamp)} | Equity: {value:.6f}</title>'
            f'</circle>'
        )

    labels.append(
        f'<text x="{padding}" y="{padding - 10}" fill="#94a3b8" font-size="12">Max: {max(values):.6f}</text>'
    )
    labels.append(
        f'<text x="{padding}" y="{height - 8}" fill="#94a3b8" font-size="12">Min: {min(values):.6f}</text>'
    )

    return f"""
    <svg viewBox="0 0 {width} {height}" class="chart">
        <rect x="0" y="0" width="{width}" height="{height}" fill="#111827" rx="12"></rect>
        <line x1="{padding}" y1="{height - padding}" x2="{width - padding}" y2="{height - padding}" stroke="#334155" />
        <line x1="{padding}" y1="{padding}" x2="{padding}" y2="{height - padding}" stroke="#334155" />
        <polyline fill="none" stroke="#38bdf8" stroke-width="3" points="{polyline_points}" />
        {''.join(circles)}
        {''.join(labels)}
    </svg>
    """


def get_service_status(service_name: str) -> str:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            check=False,
        )
        status = (result.stdout or "").strip()
        return status or "unknown"
    except Exception:
        return "unknown"


def build_status_badge(label: str, value: str) -> str:
    normalized = str(value).strip().lower()

    if normalized in {"active", "enabled", "true", "on"}:
        dot_class = "dot-green"
    elif normalized in {"inactive", "disabled", "false", "off", "unknown"}:
        dot_class = "dot-red"
    else:
        dot_class = "dot-amber"

    return f"""
    <div class="status-card">
        <div class="status-label">{html.escape(label)}</div>
        <div class="status-value">
            <span class="dot {dot_class}"></span>
            {html.escape(value)}
        </div>
    </div>
    """


def build_dashboard_html() -> str:
    settings = get_settings()
    positions = load_positions()
    trades = load_trades()
    snapshots = load_latest_snapshots(limit=20)

    latest_snapshot = snapshots[0] if snapshots else {}
    account_state = latest_snapshot.get("account_state") or {}
    portfolio_summary = latest_snapshot.get("portfolio_summary") or {}
    top_candidates = latest_snapshot.get("top_candidates") or []

    open_positions = [p for p in positions if p.get("status") == "OPEN"]
    closed_positions = [p for p in positions if p.get("status") == "CLOSED"]

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

    closed_position_rows = []
    for position in sorted(closed_positions, key=lambda x: x.get("closed_at_utc", ""), reverse=True)[:10]:
        entry_price = float(position.get("entry_price", 0.0) or 0.0)
        current_price = float(position.get("current_price", entry_price) or entry_price)
        shares = float(position.get("shares", 0.0) or 0.0)
        realized_pnl = round((current_price - entry_price) * shares, 6)

        closed_position_rows.append(
            [
                position.get("market_id", "-"),
                position.get("question", "-"),
                position.get("close_reason", "-"),
                position.get("entry_price", "-"),
                position.get("current_price", "-"),
                position.get("shares", "-"),
                realized_pnl,
                position.get("closed_at_utc", "-"),
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

    candidate_rows = []
    for item in top_candidates[:10]:
        candidate_rows.append(
            [
                item.get("id", "-"),
                item.get("question", "-"),
                item.get("score", "-"),
                item.get("yes_price", "-"),
                item.get("spread", "-"),
                item.get("volume", "-"),
                item.get("liquidity", "-"),
            ]
        )

    bot_service_status = get_service_status("polymarket-bot.service")
    dashboard_service_status = get_service_status("polymarket-dashboard.service")
    telegram_status = "enabled" if (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID) else "disabled"
    kill_switch_status = "on" if latest_snapshot.get("kill_switch_triggered", False) else "off"

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

    status_html = "".join(
        [
            build_status_badge("Bot Service", bot_service_status),
            build_status_badge("Dashboard Service", dashboard_service_status),
            build_status_badge("Telegram", telegram_status),
            build_status_badge("Kill Switch", kill_switch_status),
        ]
    )

    equity_chart = build_equity_svg(snapshots)

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

    closed_positions_table = render_table(
        [
            "Market ID",
            "Question",
            "Close Reason",
            "Entry Price",
            "Exit Price",
            "Shares",
            "Realized PnL",
            "Closed At UTC",
        ],
        closed_position_rows,
    )

    recent_trades_table = render_table(
        ["Timestamp UTC", "Market ID", "Action", "Price", "Shares", "Notional USD"],
        trade_rows,
    )

    candidate_table = render_table(
        ["Market ID", "Question", "Score", "Yes Price", "Spread", "Volume", "Liquidity"],
        candidate_rows,
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
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .card, .status-card {{
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 16px;
        }}
        .card-title, .status-label {{
            font-size: 12px;
            color: #94a3b8;
            margin-bottom: 8px;
            text-transform: uppercase;
        }}
        .card-value {{
            font-size: 22px;
            font-weight: bold;
        }}
        .status-value {{
            font-size: 18px;
            font-weight: bold;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .dot {{
            width: 12px;
            height: 12px;
            border-radius: 999px;
            display: inline-block;
        }}
        .dot-green {{
            background: #22c55e;
        }}
        .dot-red {{
            background: #ef4444;
        }}
        .dot-amber {{
            background: #f59e0b;
        }}
        .chart {{
            width: 100%;
            max-width: 100%;
            height: auto;
            margin-bottom: 28px;
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

    <h2>Operational Status</h2>
    <div class="status-grid">{status_html}</div>

    <h2>Account Summary</h2>
    <div class="grid">{cards_html}</div>

    <h2>Equity History</h2>
    {equity_chart}

    <h2>Top Candidate Markets</h2>
    {candidate_table}

    <h2>Open Positions</h2>
    {open_positions_table}

    <h2>Closed Positions</h2>
    {closed_positions_table}

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
