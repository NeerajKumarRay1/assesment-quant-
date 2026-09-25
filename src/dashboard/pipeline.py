"""One end-to-end trading session, UI-free.

data -> indicators -> macro regime overrides -> strategy -> risk -> backtest
-> blotter -> reconciliation

The dashboard is a thin view over `run_session`; everything here is plain
Python/pandas so it is unit-tested like the rest of the engine.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, UTC
from decimal import Decimal
from typing import Literal

import numpy as np
import pandas as pd

from src.backtest import BacktestEngine, BacktestResult, FixedPercentageSlippage, IndianEquityFuturesCosts
from src.core.bar import Bar
from src.core.order import Side
from src.core.position import Position
from src.indicators import atr, ema, obv, rsi
from src.macro import MacroRegimeConfig, MacroRegimeEngine, MacroSnapshot, RegimeDecision
from src.observability.events import TradingEvent
from src.risk import RiskManager
from src.strategy import GridStrategy, StopAndReverseStrategy

StrategyName = Literal["grid", "sar"]

# Exchange time. Fixed offset (India has no DST), so no tz database is needed on Windows.
IST = timezone(timedelta(hours=5, minutes=30), "IST")


@dataclass(frozen=True)
class SessionConfig:
    """Every knob the dashboard exposes. Defaults give a sensible demo run."""
    # Market data (synthetic, seeded -> deterministic)
    instrument: str = "NIFTY_FUT"
    n_bars: int = 375             # one NSE session of 1-minute bars (09:15-15:30)
    start_price: float = 18000.0
    drift: float = 0.0            # mean move per bar
    noise: float = 10.0           # uniform noise half-width per bar
    seed: int = 7

    # Indicators
    atr_period: int = 14
    rsi_period: int = 14
    ema_period: int = 20

    # Strategy
    strategy: StrategyName = "grid"
    grid_spacing_atr_multiplier: float = 1.5
    max_pyramid_levels: int = 3
    stop_loss_atr_multiplier: float = 2.0
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    position_size: int = 1

    # Macro regime (None = don't apply overrides)
    macro_snapshot: tuple[float, float, float] | None = None   # (volatility, trend, sentiment)

    # Risk
    max_position: int = 3
    kill_switch: bool = False

    # Execution & costs
    lot_size: int = 75
    slippage_pct: float = 0.0005
    brokerage_per_trade: float = 20.0
    initial_capital: float = 1_000_000.0


@dataclass(frozen=True)
class ReconciliationCheck:
    name: str
    engine_value: float
    recomputed_value: float

    @property
    def is_match(self) -> bool:
        """Matches to the paisa, not 'roughly'."""
        return _to_paisa(self.engine_value) == _to_paisa(self.recomputed_value)


@dataclass
class SessionResult:
    config: SessionConfig
    bars: pd.DataFrame                  # one row per bar: OHLCV, indicators, target, position, equity
    blotter: pd.DataFrame               # one row per fill
    backtest: BacktestResult
    regime: RegimeDecision | None
    effective_params: dict[str, float | int]
    risk_events: list[TradingEvent] = field(default_factory=list)
    reconciliation: list[ReconciliationCheck] = field(default_factory=list)

    @property
    def reconciled(self) -> bool:
        return all(check.is_match for check in self.reconciliation)


class _CollectingEventLogger:
    def __init__(self) -> None:
        self.events: list[TradingEvent] = []

    def log_event(self, event: TradingEvent) -> None:
        self.events.append(event)


def generate_synthetic_bars(
    instrument: str,
    n_bars: int,
    start_price: float,
    drift: float,
    noise: float,
    seed: int,
) -> list[Bar]:
    """Seeded random-walk OHLCV bars at 1-minute spacing from 09:15 IST."""
    rng = np.random.default_rng(seed)
    opens = start_price + np.cumsum(drift + rng.uniform(-noise, noise, n_bars))
    ranges = np.abs(rng.uniform(-noise, noise, n_bars)) + noise / 2
    closes = opens + rng.uniform(-0.5, 0.5, n_bars) * ranges
    highs = np.maximum(opens, closes) + rng.uniform(0, 1, n_bars) * ranges
    lows = np.minimum(opens, closes) - rng.uniform(0, 1, n_bars) * ranges
    volumes = 100_000 + rng.integers(-10_000, 10_000, n_bars)
    start = datetime(2024, 1, 1, 9, 15, tzinfo=IST)

    return [
        Bar(
            instrument=instrument,
            timestamp=start + timedelta(minutes=i),
            open=round(float(opens[i]), 2),
            high=round(float(highs[i]), 2),
            low=round(float(lows[i]), 2),
            close=round(float(closes[i]), 2),
            volume=int(volumes[i]),
        )
        for i in range(n_bars)
    ]


def run_session(config: SessionConfig) -> SessionResult:
    bars = generate_synthetic_bars(
        config.instrument, config.n_bars, config.start_price, config.drift, config.noise, config.seed
    )
    atr_values = atr(bars, config.atr_period)
    rsi_values = rsi(bars, config.rsi_period)

    regime, params, circuit_breaker = _apply_macro(config)

    event_logger = _CollectingEventLogger()
    signal_risk = RiskManager(config.max_position, config.kill_switch, event_logger=event_logger)
    targets = _generate_targets(config, bars, atr_values, rsi_values, params, signal_risk, circuit_breaker)

    cost_model = IndianEquityFuturesCosts(brokerage_per_trade=config.brokerage_per_trade)
    engine = BacktestEngine(FixedPercentageSlippage(config.slippage_pct), cost_model)
    result = engine.run_simple(
        bars,
        targets,
        risk_manager=RiskManager(config.max_position, config.kill_switch),
        initial_capital=config.initial_capital,
        lot_size=config.lot_size,
        circuit_breaker_active=circuit_breaker,
    )

    blotter = _build_blotter(result, cost_model, config.lot_size)
    bars_df = _build_bars_frame(bars, atr_values, rsi_values, targets, result, config)

    return SessionResult(
        config=config,
        bars=bars_df,
        blotter=blotter,
        backtest=result,
        regime=regime,
        effective_params=params,
        risk_events=event_logger.events,
        reconciliation=_reconcile(result, blotter, bars[-1].close, config),
    )


def _apply_macro(config: SessionConfig) -> tuple[RegimeDecision | None, dict[str, float | int], bool]:
    params: dict[str, float | int] = {
        "grid_spacing_multiplier": config.grid_spacing_atr_multiplier,
        "max_pyramid_levels": config.max_pyramid_levels,
        "stop_loss_multiplier": config.stop_loss_atr_multiplier,
    }
    if config.macro_snapshot is None:
        return None, params, False

    volatility, trend, sentiment = config.macro_snapshot
    decision = MacroRegimeEngine(MacroRegimeConfig()).evaluate(
        MacroSnapshot(timestamp=datetime.now(UTC), volatility=volatility, trend=trend, sentiment=sentiment)
    )
    return decision, {**params, **decision.parameters}, decision.circuit_breaker_active


def _generate_targets(
    config: SessionConfig,
    bars: list[Bar],
    atr_values: pd.Series,
    rsi_values: pd.Series,
    params: dict[str, float | int],
    risk: RiskManager,
    circuit_breaker: bool,
) -> list[int]:
    """Strategy + risk at each bar close, tracking the position the orders would produce."""
    if config.strategy == "grid":
        grid = GridStrategy(
            grid_spacing_atr_multiplier=float(params["grid_spacing_multiplier"]),
            max_pyramid_levels=int(params["max_pyramid_levels"]),
            stop_loss_atr_multiplier=float(params["stop_loss_multiplier"]),
            rsi_oversold=config.rsi_oversold,
            rsi_overbought=config.rsi_overbought,
            position_size=config.position_size,
        )
    else:
        sar = StopAndReverseStrategy(
            position_size=config.position_size,
            rsi_oversold=config.rsi_oversold,
            rsi_overbought=config.rsi_overbought,
        )

    position = Position(instrument=config.instrument)
    targets: list[int] = []
    # .to_numpy() once, then index - no per-row pandas access in the loop
    atr_arr, rsi_arr = atr_values.to_numpy(), rsi_values.to_numpy()

    for i, bar in enumerate(bars):
        bar_atr, bar_rsi = atr_arr[i], rsi_arr[i]
        if np.isnan(bar_atr) or np.isnan(bar_rsi) or bar_atr == 0:
            targets.append(position.quantity)
            continue

        if config.strategy == "grid":
            desired = grid.calculate_target_quantity(config.instrument, bar.close, position, float(bar_atr), float(bar_rsi))
        else:
            desired = sar.calculate_target_quantity(config.instrument, position, float(bar_rsi))

        decision = risk.evaluate(config.instrument, desired, position, circuit_breaker_active=circuit_breaker)
        final = decision.target_quantity if decision.allowed else position.quantity
        if final != position.quantity and position.quantity == 0:
            position.avg_price = bar.close
        position.quantity = final
        targets.append(final)

    return targets


def _build_blotter(result: BacktestResult, cost_model: IndianEquityFuturesCosts, lot_size: int) -> pd.DataFrame:
    """Canonical per-fill record: costs and realized P&L attributed to each fill."""
    position = Position(instrument=result.instrument, multiplier=lot_size)
    rows = []
    for fill in result.fills:
        realized_before = position.realized_pnl
        position.apply_fill(fill)
        rows.append({
            "time": fill.filled_at,
            "side": fill.side.value,
            "quantity": fill.quantity,
            "price": fill.price,
            "notional": fill.price * fill.quantity * lot_size,
            "costs": cost_model.calculate_costs(fill, multiplier=lot_size),
            "realized_pnl": position.realized_pnl - realized_before,
            "position_after": position.quantity,
            "fill_id": fill.fill_id,
        })
    columns = ["time", "side", "quantity", "price", "notional", "costs", "realized_pnl", "position_after", "fill_id"]
    return pd.DataFrame(rows, columns=columns)


def _build_bars_frame(
    bars: list[Bar],
    atr_values: pd.Series,
    rsi_values: pd.Series,
    targets: list[int],
    result: BacktestResult,
    config: SessionConfig,
) -> pd.DataFrame:
    df = pd.DataFrame({
        "time": [b.timestamp for b in bars],
        "open": [b.open for b in bars],
        "high": [b.high for b in bars],
        "low": [b.low for b in bars],
        "close": [b.close for b in bars],
        "volume": [b.volume for b in bars],
    })
    df["atr"] = atr_values.to_numpy()
    df["rsi"] = rsi_values.to_numpy()
    df["ema"] = ema(bars, config.ema_period).to_numpy()
    df["obv"] = obv(bars).to_numpy()
    df["target"] = targets
    df["equity"] = result.equity_curve[1:]   # [0] is initial capital, then one mark per bar

    # Position held at each bar's close = cumulative signed fills up to that bar
    fills = pd.DataFrame({
        "time": [f.filled_at for f in result.fills],
        "signed": [f.quantity if f.side == Side.BUY else -f.quantity for f in result.fills],
    })
    per_bar = fills.groupby("time")["signed"].sum() if not fills.empty else pd.Series(dtype=int)
    df["position"] = df["time"].map(per_bar).fillna(0).astype(int).cumsum()
    return df


def _reconcile(
    result: BacktestResult,
    blotter: pd.DataFrame,
    final_close: float,
    config: SessionConfig,
) -> list[ReconciliationCheck]:
    """Recompute P&L from the blotter with Decimal average-cost math, independent of Position."""
    lot = Decimal(config.lot_size)
    qty, avg, realized = 0, Decimal(0), Decimal(0)
    for row in blotter.itertuples(index=False):   # one row per fill, small - clarity over vectorisation
        price = Decimal(repr(row.price))
        signed = row.quantity if row.side == "BUY" else -row.quantity
        if qty != 0 and (qty > 0) != (signed > 0):
            closed = min(abs(signed), abs(qty))
            realized += (1 if qty > 0 else -1) * closed * (price - avg) * lot
        new_qty = qty + signed
        if new_qty == 0:
            avg = Decimal(0)
        elif qty == 0 or (qty > 0) == (signed > 0):
            avg = (avg * abs(qty) + price * abs(signed)) / abs(new_qty)
        elif (new_qty > 0) != (qty > 0):
            avg = price
        qty = new_qty

    unrealized = qty * (Decimal(repr(final_close)) - avg) * lot
    costs = sum((Decimal(repr(c)) for c in blotter["costs"]), Decimal(0))
    net = realized + unrealized - costs
    final_qty = result.final_position.quantity if result.final_position else 0

    return [
        ReconciliationCheck("Final position (lots)", final_qty, qty),
        ReconciliationCheck("Realized P&L", result.final_position.realized_pnl if result.final_position else 0.0, float(realized)),
        ReconciliationCheck("Transaction costs", result.transaction_costs, float(costs)),
        ReconciliationCheck("Net P&L", result.net_pnl, float(net)),
        ReconciliationCheck("Final equity - capital", result.equity_curve[-1] - config.initial_capital, float(net)),
    ]


def _to_paisa(value: float) -> int:
    return int((Decimal(repr(value)) * 100).quantize(Decimal(1), rounding="ROUND_HALF_UP"))
