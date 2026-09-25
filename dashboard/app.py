"""Quant Trading Console - minimal Streamlit dashboard.

Run from the project root:
    streamlit run dashboard/app.py

A thin view over src.dashboard.run_session: every number shown comes from the
real strategy, risk, backtest and reconciliation code. Mock data only.
"""

import os
import sys

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.dashboard import SessionConfig, SessionResult, run_session  # noqa: E402

st.set_page_config(page_title="Quant Trading Console", page_icon="📈", layout="wide")

# ---------------------------------------------------------------------------
# Chart tokens - reference palette slots 1/2 (validated pair, both modes).
# Buy/sell also differ by marker shape, so identity is never colour alone.
# ---------------------------------------------------------------------------
_DARK = getattr(getattr(st.context, "theme", None), "type", "light") == "dark"
TOKENS = {
    "series": "#3987e5" if _DARK else "#2a78d6",
    "sell": "#d95926" if _DARK else "#eb6834",
    "ink": "#c3c2b7" if _DARK else "#52514e",
    "muted": "#8a8983" if _DARK else "#9a9993",
    "grid": "#383835" if _DARK else "#e8e7e3",
    "surface": "#0e1117" if _DARK else "#ffffff",
}
CHART_HEIGHT = 240
# Timestamps carry IST wall-clock time labelled UTC (see exchange_time); UTC time
# units stop Vega from shifting them into the viewer's local timezone.
TIME = "utcyearmonthdatehoursminutes(time):T"


def rupees(value: float, decimals: int = 2) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}₹{abs(value):,.{decimals}f}"


def exchange_time(df: pd.DataFrame) -> pd.DataFrame:
    """IST wall-clock time relabelled as UTC.

    Paired with UTC time units in the charts, this shows exchange time whatever
    the server's or viewer's timezone (naive timestamps get re-localised).
    """
    if df.empty:
        return df
    ist = pd.to_datetime(df["time"]).dt.tz_convert("+05:30").dt.tz_localize(None)
    return df.assign(time=ist.dt.tz_localize("UTC"))


# ---------------------------------------------------------------------------
# Sidebar - session configuration
# ---------------------------------------------------------------------------
def sidebar() -> SessionConfig:
    d = SessionConfig()
    sb = st.sidebar
    sb.title("Session")

    strategy_label = sb.segmented_control(
        "Strategy", ["Grid", "Stop-and-Reverse"], default="Grid", selection_mode="single"
    ) or "Grid"
    strategy = "grid" if strategy_label == "Grid" else "sar"

    with sb.expander("Strategy parameters", expanded=True):
        is_grid = strategy == "grid"
        spacing = st.slider("Grid spacing (× ATR)", 0.5, 3.0, d.grid_spacing_atr_multiplier, 0.1, disabled=not is_grid)
        pyramids = st.slider("Max pyramid levels", 1, 5, d.max_pyramid_levels, disabled=not is_grid)
        stop = st.slider("Stop loss (× ATR)", 0.5, 5.0, d.stop_loss_atr_multiplier, 0.1, disabled=not is_grid)
        oversold, overbought = st.slider(
            "RSI entry band", 5, 95, (int(d.rsi_oversold), int(d.rsi_overbought)),
            help="Long below the lower bound, short above the upper bound.",
        )

    with sb.expander("Risk", expanded=True):
        max_position = st.number_input("Position cap (± lots)", 1, 20, d.max_position)
        kill_switch = st.toggle("Kill switch", value=d.kill_switch, help="Blocks new exposure; reductions allowed.")

    with sb.expander("Macro regime"):
        use_macro = st.toggle("Apply regime overrides", value=False)
        vol = st.slider("Volatility proxy", 0.0, 4.0, 0.8, 0.1, disabled=not use_macro,
                        help="≥ 2.5 trips the circuit breaker.")
        trend = st.slider("Trend proxy", -1.0, 1.0, 0.2, 0.1, disabled=not use_macro)
        sentiment = st.slider("Sentiment proxy", -1.0, 1.0, 0.0, 0.1, disabled=not use_macro)

    with sb.expander("Market data"):
        n_bars = st.slider("Bars (1-minute)", 100, 1500, d.n_bars, 25)
        noise = st.slider("Noise per bar (₹)", 2.0, 40.0, d.noise, 1.0)
        drift = st.slider("Drift per bar (₹)", -2.0, 2.0, d.drift, 0.1)
        seed = st.number_input("Random seed", 0, 10_000, d.seed)

    with sb.expander("Execution & costs"):
        lot_size = st.number_input("Lot size", 1, 5000, d.lot_size, help="NIFTY futures: 75")
        slippage_bps = st.slider("Slippage (bps)", 0.0, 50.0, d.slippage_pct * 10_000, 0.5)
        brokerage = st.number_input("Brokerage per order (₹)", 0.0, 100.0, d.brokerage_per_trade, 1.0)
        capital = st.number_input("Initial capital (₹)", 10_000.0, 1e9, d.initial_capital, 100_000.0, format="%.0f")

    sb.caption("Mock data · no live orders are ever placed.")

    return SessionConfig(
        n_bars=int(n_bars), drift=float(drift), noise=float(noise), seed=int(seed),
        strategy=strategy,
        grid_spacing_atr_multiplier=float(spacing), max_pyramid_levels=int(pyramids),
        stop_loss_atr_multiplier=float(stop),
        rsi_oversold=float(oversold), rsi_overbought=float(overbought),
        macro_snapshot=(float(vol), float(trend), float(sentiment)) if use_macro else None,
        max_position=int(max_position), kill_switch=bool(kill_switch),
        lot_size=int(lot_size), slippage_pct=float(slippage_bps) / 10_000,
        brokerage_per_trade=float(brokerage), initial_capital=float(capital),
    )


@st.cache_data(show_spinner=False)
def cached_session(config: SessionConfig) -> SessionResult:
    return run_session(config)


# ---------------------------------------------------------------------------
# Charts - one measure per chart (no dual axes), thin marks, hover tooltips
# ---------------------------------------------------------------------------
def _axis_config(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure_axis(gridColor=TOKENS["grid"], domainColor=TOKENS["grid"], tickColor=TOKENS["grid"],
                             labelColor=TOKENS["ink"], titleColor=TOKENS["ink"], labelFontSize=11, titleFontSize=11)
        .configure_view(strokeWidth=0)
        .configure_legend(labelColor=TOKENS["ink"], titleColor=TOKENS["ink"], orient="top-left")
    )


def line_chart(df: pd.DataFrame, y: str, title: str, color: str, fmt: str = ",.2f",
               step: bool = False, rules: list[float] | None = None) -> alt.Chart:
    """Single-series line with crosshair + tooltip on hover."""
    x = alt.X(TIME, title=None, axis=alt.Axis(format="%H:%M", labelAngle=0))
    hover = alt.selection_point(encodings=["x"], nearest=True, on="pointerover", empty=False, clear="pointerout")
    base = alt.Chart(df).encode(x=x)

    line = base.mark_line(strokeWidth=2, color=color, interpolate="step-after" if step else "linear").encode(
        y=alt.Y(f"{y}:Q", title=None, scale=alt.Scale(zero=False))
    )
    catcher = base.mark_rule(opacity=0).encode(
        tooltip=[alt.Tooltip(TIME, title="Time", format="%H:%M"), alt.Tooltip(f"{y}:Q", title=title, format=fmt)]
    ).add_params(hover)
    crosshair = base.mark_rule(color=TOKENS["muted"], strokeWidth=1).transform_filter(hover)
    dot = base.mark_point(filled=True, size=64, color=color, stroke=TOKENS["surface"], strokeWidth=2).encode(
        y=f"{y}:Q").transform_filter(hover)

    layers = [line, catcher, crosshair, dot]
    if rules:
        rule_df = pd.DataFrame({"level": rules})
        layers.insert(0, alt.Chart(rule_df).mark_rule(color=TOKENS["muted"], strokeWidth=1).encode(y="level:Q"))
    return _axis_config(alt.layer(*layers).properties(height=CHART_HEIGHT))


def price_with_fills(bars: pd.DataFrame, blotter: pd.DataFrame) -> alt.Chart:
    x = alt.X(TIME, title=None, axis=alt.Axis(format="%H:%M", labelAngle=0))
    hover = alt.selection_point(encodings=["x"], nearest=True, on="pointerover", empty=False, clear="pointerout")
    base = alt.Chart(bars).encode(x=x)
    price = base.mark_line(strokeWidth=1.5, color=TOKENS["ink"]).encode(
        y=alt.Y("close:Q", title=None, scale=alt.Scale(zero=False)),
    )
    catcher = base.mark_rule(opacity=0).encode(
        tooltip=[
            alt.Tooltip(TIME, title="Time", format="%H:%M"),
            alt.Tooltip("open:Q", title="Open", format=",.2f"),
            alt.Tooltip("high:Q", title="High", format=",.2f"),
            alt.Tooltip("low:Q", title="Low", format=",.2f"),
            alt.Tooltip("close:Q", title="Close", format=",.2f"),
            alt.Tooltip("position:Q", title="Position (lots)"),
        ]
    ).add_params(hover)
    crosshair = base.mark_rule(color=TOKENS["muted"], strokeWidth=1).transform_filter(hover)
    layers = [price, catcher, crosshair]
    if blotter.empty:
        return _axis_config(alt.layer(*layers).properties(height=CHART_HEIGHT + 60))

    fills = blotter.assign(action=blotter["side"].map({"BUY": "Buy", "SELL": "Sell"}))
    markers = alt.Chart(fills).mark_point(filled=True, size=200, stroke=TOKENS["surface"], strokeWidth=2, opacity=1).encode(
        x=x, y="price:Q",
        color=alt.Color("action:N", title=None,
                        scale=alt.Scale(domain=["Buy", "Sell"], range=[TOKENS["series"], TOKENS["sell"]])),
        shape=alt.Shape("action:N", title=None,
                        scale=alt.Scale(domain=["Buy", "Sell"], range=["triangle-up", "triangle-down"])),
        tooltip=[
            alt.Tooltip(TIME, title="Time", format="%H:%M"),
            alt.Tooltip("action:N", title="Side"),
            alt.Tooltip("quantity:Q", title="Lots"),
            alt.Tooltip("price:Q", title="Fill price", format=",.2f"),
            alt.Tooltip("costs:Q", title="Costs (₹)", format=",.2f"),
            alt.Tooltip("position_after:Q", title="Position after"),
        ],
    )
    return _axis_config(alt.layer(*layers, markers).properties(height=CHART_HEIGHT + 60)).configure_legend(
        labelColor=TOKENS["ink"], orient="top-left", symbolSize=140, labelFontSize=12
    )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
config = sidebar()
result = cached_session(config)
bt = result.backtest
bars_view = exchange_time(result.bars)
blotter_view = exchange_time(result.blotter)


def table_view(df: pd.DataFrame) -> pd.DataFrame:
    """Tables show exchange time as text so no widget re-localises it."""
    return df.assign(time=df["time"].dt.strftime("%H:%M")) if not df.empty else df

st.title("Quant Trading Console")
st.caption(
    f"{config.instrument} · {config.n_bars} one-minute bars · "
    f"{'Grid' if config.strategy == 'grid' else 'Stop-and-Reverse'} strategy · simulated session"
)

# Status strip - every state carries an icon + label, never colour alone
status = st.columns(4)
with status[0]:
    if result.regime is None:
        st.badge("Macro overrides off", icon=":material/tune:", color="gray")
    else:
        regime = result.regime.regime.value
        st.badge(f"Regime {regime} ({result.regime.score:+.2f})", icon=":material/public:",
                 color={"RISK_ON": "blue", "NEUTRAL": "gray", "RISK_OFF": "orange"}[regime])
with status[1]:
    if result.regime is not None and result.regime.circuit_breaker_active:
        st.badge("Circuit breaker ACTIVE", icon=":material/bolt:", color="red")
    else:
        st.badge("Circuit breaker off", icon=":material/bolt:", color="gray")
with status[2]:
    if config.kill_switch:
        st.badge("Kill switch ON", icon=":material/block:", color="red")
    else:
        st.badge("Kill switch off", icon=":material/block:", color="gray")
with status[3]:
    if result.reconciled:
        st.badge("Reconciled to the paisa", icon=":material/check_circle:", color="green")
    else:
        st.badge("Reconciliation mismatch", icon=":material/error:", color="red")

# KPI row
kpis = st.columns(6)
kpis[0].metric("Net P&L", rupees(bt.net_pnl, 0), f"{bt.returns_pct:+.2f}%",
               delta_color="normal" if bt.net_pnl else "off", help=f"Exact: {rupees(bt.net_pnl)}")
kpis[1].metric("Gross P&L", rupees(bt.gross_pnl, 0), help=f"Exact: {rupees(bt.gross_pnl)}")
kpis[2].metric("Transaction costs", rupees(bt.transaction_costs, 0), help=f"Exact: {rupees(bt.transaction_costs)}")
kpis[3].metric("Slippage", rupees(bt.slippage_costs, 0),
               help=f"Exact: {rupees(bt.slippage_costs)}. Already inside fill prices (and so inside Gross P&L).")
kpis[4].metric("Trades", f"{bt.total_trades}")
kpis[5].metric("Final position", f"{bt.final_position.quantity:+d} lots" if bt.final_position else "0 lots")

if result.regime is not None:
    p = result.effective_params
    st.caption(
        f"Regime overrides applied → grid spacing {p['grid_spacing_multiplier']}× ATR, "
        f"max pyramids {p['max_pyramid_levels']}, stop {p['stop_loss_multiplier']}× ATR."
    )

perf_tab, ind_tab, blotter_tab, risk_tab = st.tabs(["Performance", "Indicators", "Trade blotter", "Risk & reconciliation"])

with perf_tab:
    st.subheader("Price & fills", divider="gray")
    st.altair_chart(price_with_fills(bars_view, blotter_view), width="stretch")
    left, right = st.columns(2)
    with left:
        st.subheader("Equity", divider="gray")
        st.altair_chart(line_chart(bars_view, "equity", "Equity (₹)", TOKENS["series"]), width="stretch")
    with right:
        st.subheader("Position", divider="gray")
        st.altair_chart(line_chart(bars_view, "position", "Lots", TOKENS["series"], fmt="+d", step=True),
                        width="stretch")

with ind_tab:
    left, right = st.columns(2)
    with left:
        st.subheader(f"RSI ({config.rsi_period})", divider="gray")
        st.altair_chart(line_chart(bars_view.dropna(subset=["rsi"]), "rsi", "RSI", TOKENS["series"], fmt=".1f",
                                   rules=[config.rsi_oversold, config.rsi_overbought]), width="stretch")
        st.subheader(f"EMA ({config.ema_period})", divider="gray")
        st.altair_chart(line_chart(bars_view.dropna(subset=["ema"]), "ema", "EMA (₹)", TOKENS["series"]),
                        width="stretch")
    with right:
        st.subheader(f"ATR ({config.atr_period})", divider="gray")
        st.altair_chart(line_chart(bars_view.dropna(subset=["atr"]), "atr", "ATR (₹)", TOKENS["series"]),
                        width="stretch")
        st.subheader("On-balance volume", divider="gray")
        st.altair_chart(line_chart(bars_view, "obv", "OBV", TOKENS["series"], fmt=",d"), width="stretch")
    with st.expander("Bar data table"):
        st.dataframe(table_view(bars_view), hide_index=True, width="stretch")

with blotter_tab:
    if result.blotter.empty:
        st.info("No fills this session. Loosen the RSI band, turn off the kill switch, or change the seed.",
                icon=":material/info:")
    else:
        st.dataframe(
            table_view(blotter_view),
            hide_index=True,
            width="stretch",
            column_config={
                "time": "Time (IST)",
                "side": "Side",
                "quantity": st.column_config.NumberColumn("Lots"),
                "price": st.column_config.NumberColumn("Price (₹)", format="%.2f"),
                "notional": st.column_config.NumberColumn("Notional (₹)", format="%.2f"),
                "costs": st.column_config.NumberColumn("Costs (₹)", format="%.2f"),
                "realized_pnl": st.column_config.NumberColumn("Realized P&L (₹)", format="%.2f"),
                "position_after": st.column_config.NumberColumn("Position after"),
                "fill_id": "Fill ID",
            },
        )
        st.download_button("Download blotter CSV", result.blotter.to_csv(index=False).encode("utf-8"),
                           file_name="trade_blotter.csv", mime="text/csv", icon=":material/download:")

with risk_tab:
    st.subheader("Reconciliation", divider="gray")
    st.caption("Engine numbers vs an independent Decimal recomputation from the blotter. Acceptance = equal to the paisa.")
    st.dataframe(
        pd.DataFrame([
            {
                "Check": c.name,
                "Engine": c.engine_value,
                "Recomputed": c.recomputed_value,
                "Difference": c.engine_value - c.recomputed_value,
                "Status": "✓ Match" if c.is_match else "✗ Mismatch",
            }
            for c in result.reconciliation
        ]),
        hide_index=True,
        width="stretch",
        column_config={
            "Engine": st.column_config.NumberColumn(format="%.2f"),
            "Recomputed": st.column_config.NumberColumn(format="%.2f"),
            "Difference": st.column_config.NumberColumn(format="%.4f"),
        },
    )

    st.subheader(f"Risk events ({len(result.risk_events)})", divider="gray")
    if not result.risk_events:
        st.caption("No signals were blocked by the kill switch or circuit breaker.")
    else:
        st.dataframe(
            pd.DataFrame([
                {
                    "Event": e.event_type.value,
                    "Desired (lots)": e.metadata.get("desired_quantity"),
                    "Reason": e.metadata.get("reason"),
                }
                for e in result.risk_events
            ]),
            hide_index=True,
            width="stretch",
        )
