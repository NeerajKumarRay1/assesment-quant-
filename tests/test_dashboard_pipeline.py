"""Tests for the dashboard's session pipeline."""

import pytest
from src.dashboard import SessionConfig, generate_synthetic_bars, run_session
from src.dashboard.pipeline import ReconciliationCheck
from src.observability.events import EventType


def test_synthetic_bars_are_deterministic_and_valid_ohlc():
    a = generate_synthetic_bars("X", 50, 100.0, 0.0, 2.0, seed=3)
    b = generate_synthetic_bars("X", 50, 100.0, 0.0, 2.0, seed=3)

    assert a == b
    assert all(bar.low <= min(bar.open, bar.close) and bar.high >= max(bar.open, bar.close) for bar in a)
    assert a[1].timestamp - a[0].timestamp == a[2].timestamp - a[1].timestamp


@pytest.mark.parametrize("config", [
    SessionConfig(),
    SessionConfig(strategy="sar"),
    SessionConfig(strategy="sar", noise=15.0, seed=1),
    SessionConfig(lot_size=1, slippage_pct=0.0),
    SessionConfig(macro_snapshot=(0.3, 0.8, 0.7)),
])
def test_session_reconciles_to_the_paisa(config):
    result = run_session(config)

    assert result.backtest.total_trades > 0
    assert result.reconciled, [(c.name, c.engine_value, c.recomputed_value) for c in result.reconciliation]


def test_bars_frame_is_aligned_with_backtest():
    result = run_session(SessionConfig())
    bars = result.bars

    assert len(bars) == SessionConfig().n_bars
    assert bars["equity"].iloc[-1] == pytest.approx(SessionConfig().initial_capital + result.backtest.net_pnl)
    assert bars["position"].iloc[-1] == result.backtest.final_position.quantity
    # Position only changes on bars that had a fill
    changed = bars.index[bars["position"].diff().fillna(bars["position"]) != 0]
    assert set(bars.loc[changed, "time"]) <= set(result.blotter["time"])


def test_blotter_attributes_costs_and_realized_pnl_per_fill():
    result = run_session(SessionConfig())

    assert len(result.blotter) == result.backtest.total_trades
    assert result.blotter["costs"].sum() == pytest.approx(result.backtest.transaction_costs)
    assert result.blotter["realized_pnl"].sum() == pytest.approx(result.backtest.final_position.realized_pnl)


def test_positions_never_exceed_cap():
    result = run_session(SessionConfig(max_position=2, max_pyramid_levels=5, grid_spacing_atr_multiplier=0.5))
    assert result.bars["position"].abs().max() <= 2


def test_kill_switch_blocks_all_entries_and_records_risk_events():
    result = run_session(SessionConfig(kill_switch=True))

    assert result.backtest.total_trades == 0
    assert result.risk_events
    assert all(e.event_type == EventType.RISK_REJECTED for e in result.risk_events)


def test_macro_circuit_breaker_blocks_entries_and_overrides_params():
    result = run_session(SessionConfig(macro_snapshot=(3.0, -0.8, -0.9)))

    assert result.regime is not None and result.regime.circuit_breaker_active
    assert result.effective_params["max_pyramid_levels"] == 1   # RISK_OFF override
    assert result.backtest.total_trades == 0


def test_no_macro_snapshot_keeps_configured_params():
    config = SessionConfig(grid_spacing_atr_multiplier=1.7, max_pyramid_levels=2, stop_loss_atr_multiplier=2.2)
    result = run_session(config)

    assert result.regime is None
    assert result.effective_params == {
        "grid_spacing_multiplier": 1.7,
        "max_pyramid_levels": 2,
        "stop_loss_multiplier": 2.2,
    }


def test_reconciliation_check_is_exact_to_the_paisa():
    assert ReconciliationCheck("x", 100.004, 100.0).is_match
    assert not ReconciliationCheck("x", 100.01, 100.0).is_match
    assert not ReconciliationCheck("x", -5.005, -5.0).is_match   # rounds half away from zero
