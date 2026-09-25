"""Headless render tests for the Streamlit dashboard (skipped if streamlit isn't installed)."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")


def _metric(at: AppTest, label: str) -> str:
    return next(m.value for m in at.metric if m.label == label)


def _toggle(at: AppTest, label: str):
    return next(t for t in at.toggle if t.label == label)


@pytest.fixture
def app() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    return at


def test_default_session_renders_kpis_and_reconciles(app):
    assert _metric(app, "Trades") != "0"
    assert any("Reconciled to the paisa" in m.value for m in app.markdown)


def test_kill_switch_blocks_all_trades(app):
    _toggle(app, "Kill switch").set_value(True).run()

    assert not app.exception
    assert _metric(app, "Trades") == "0"


def test_macro_circuit_breaker_blocks_all_trades(app):
    _toggle(app, "Apply regime overrides").set_value(True).run()
    next(s for s in app.slider if s.label == "Volatility proxy").set_value(3.2).run()

    assert not app.exception
    assert _metric(app, "Trades") == "0"
    assert any("Circuit breaker ACTIVE" in m.value for m in app.markdown)
