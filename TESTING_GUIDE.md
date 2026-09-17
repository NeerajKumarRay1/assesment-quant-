# Testing Guide

## Quick Test Commands

### Run All Tests
```bash
python -m pytest -v
```

### Run Phase-Specific Tests

**Phase 1 Tests (Contract Master, Async Feed):**
```bash
python -m pytest tests/test_contract_master.py -v
python -m pytest tests/test_rollover.py -v
python -m pytest tests/test_replay_market_data.py -v
python -m pytest tests/test_phase1_integration.py -v
```

**Phase 2 Tests (Macro Regime):**
```bash
python -m pytest tests/test_macro_regime.py -v
python -m pytest tests/test_macro_integration.py -v
```

**Core Tests (Original):**
```bash
python -m pytest tests/test_grid_strategy.py -v
python -m pytest tests/test_risk_manager.py -v
python -m pytest tests/test_order_manager.py -v
python -m pytest tests/test_backtest.py -v
```

### Run Specific Test
```bash
python -m pytest tests/test_macro_regime.py::test_strong_positive_environment_is_risk_on -v
```

### Run Tests with Coverage
```bash
python -m pytest --cov=src tests/
```

## Test Organization

```
tests/
├── test_core.py                    # Core domain objects
├── test_grid_strategy.py           # Grid trading strategy
├── test_stop_and_reverse.py        # SAR strategy
├── test_atr.py                     # ATR indicator
├── test_rsi.py                     # RSI indicator
├── test_ema.py                     # EMA indicator
├── test_obv.py                     # OBV indicator
├── test_risk_manager.py            # Risk management
├── test_order_manager.py           # Order management
├── test_mock_broker.py             # Broker simulation
├── test_mock_market_data.py        # Market data simulation
├── test_backtest.py                # Backtesting engine
├── test_contract_master.py         # Contract registry
├── test_rollover.py                # Rollover management
├── test_replay_market_data.py      # CSV replay feed
├── test_phase1_integration.py      # Phase 1 integration
├── test_macro_regime.py            # Macro regime engine (26 tests)
├── test_macro_integration.py       # Macro + Risk integration (11 tests)
└── test_integration.py             # End-to-end integration
```

## Expected Test Count

- **Phase 0 (Core):** ~140 tests
- **Phase 1 (Infrastructure):** ~57 tests
- **Phase 2 (Macro):** ~37 tests
- **Total:** ~234+ tests

## Common Test Failures

### Import Errors
If you see import errors, ensure you're in the project root and have installed the package:
```bash
pip install -e .
```

### Async Test Failures
If async tests fail, ensure pytest-asyncio is installed:
```bash
pip install pytest-asyncio
```

### Path Issues
Always run tests from the project root directory:
```bash
cd c:\Users\neera\OneDrive\Desktop\assesment\quant-trading-assessment
python -m pytest -v
```

## Verification Scripts

Quick verification without running full test suite:

```bash
# Phase 1 verification
python verify_phase1.py

# Phase 2 verification  
python verify_phase2.py

# Run macro tests specifically
python run_macro_tests.py
```

## Test Patterns Used

### Unit Tests
- Test individual functions/methods
- Use mock/stub dependencies
- Fast execution
- No external dependencies

### Integration Tests
- Test component interactions
- Use real implementations where possible
- Verify data flow between layers
- Example: `test_macro_integration.py`

### End-to-End Tests
- Test complete workflows
- Example: `test_integration.py`
- Verify backtest runs correctly
- Ensure all layers work together

## Debugging Failed Tests

### Get More Detail
```bash
python -m pytest tests/test_macro_regime.py -vv --tb=long
```

### Run Specific Failing Test
```bash
python -m pytest tests/test_macro_regime.py::test_name_here -vv
```

### Print Test Output
```bash
python -m pytest tests/test_macro_regime.py -v -s
```

### Stop on First Failure
```bash
python -m pytest tests/test_macro_regime.py -x
```

## Test Fixtures

Common test fixtures used across tests:

- `_sample_bars()` - Creates list of Bar objects
- `_sample_ticks()` - Creates list of Tick objects
- `_default_config()` - Creates default configuration
- `_create_snapshot()` - Creates MacroSnapshot for testing

## Running Examples

After tests pass, run the examples:

```bash
python examples/grid_backtest_example.py
python examples/async_feed_example.py
python examples/macro_regime_example.py
```

## CI/CD Integration

For continuous integration, use:

```bash
python -m pytest --junitxml=test-results.xml
```

This generates JUnit-compatible XML for CI systems.
