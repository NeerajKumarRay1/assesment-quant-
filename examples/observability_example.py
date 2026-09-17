"""Observability and Reconciliation Example.

Demonstrates:
- Structured JSON logging
- Trade blotter recording
- Position reconciliation
- P&L reconciliation
- Alert generation on mismatches
"""

import tempfile
from pathlib import Path
from datetime import datetime, UTC
from src.core.order import Fill, Side
from src.core.position import Position
from src.observability import (
    StructuredLogger,
    TradeBlotter,
    LoggingAlertSink,
    CollectingAlertSink,
    create_order_submitted_event,
    create_order_filled_event,
    create_position_changed_event,
    create_reconciliation_mismatch_event,
    reconcile_positions,
    reconcile_pnl,
    format_reconciliation_report,
    create_reconciliation_report,
)


def print_section(title: str):
    """Print section header."""
    print(f"\n{'='*70}")
    print(f"{title}")
    print(f"{'='*70}\n")


def main():
    print_section("OBSERVABILITY & RECONCILIATION DEMONSTRATION")
    
    # Use temp directory for this example
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "trading.log"
        blotter_file = Path(tmpdir) / "trade_blotter.csv"
        
        # Initialize observability components
        logger = StructuredLogger("trading_engine", log_file=log_file)
        blotter = TradeBlotter(blotter_file)
        alert_sink = CollectingAlertSink()
        
        print_section("1. ORDER LIFECYCLE WITH STRUCTURED LOGGING")
        
        # Order submitted
        submit_event = create_order_submitted_event(
            client_order_id="grid_001",
            instrument="NIFTY",
            side="BUY",
            quantity=50
        )
        logger.log_event(submit_event)
        print(f"✓ ORDER_SUBMITTED: BUY 50 NIFTY")
        
        # Order filled
        fill = Fill(
            order_id="grid_001",
            instrument="NIFTY",
            side=Side.BUY,
            quantity=50,
            price=25000.0,
            fill_id="fill_001"
        )
        
        fill_event = create_order_filled_event(
            order_id=fill.order_id,
            instrument=fill.instrument,
            side=fill.side.value,
            quantity=fill.quantity,
            price=fill.price
        )
        logger.log_event(fill_event)
        print(f"✓ ORDER_FILLED: BUY 50 NIFTY @ ₹25,000.00")
        
        print_section("2. TRADE BLOTTER RECORDING")
        
        # Record to blotter
        blotter.record_fill(
            fill,
            strategy="Grid",
            costs=20.50,
            realized_pnl=0.0
        )
        blotter.flush()
        print(f"✓ Trade recorded to blotter")
        print(f"  Fill ID: {fill.fill_id}")
        print(f"  Strategy: Grid")
        print(f"  Costs: ₹20.50")
        
        # Verify blotter
        trades = blotter.read_trades()
        print(f"\n✓ Blotter contains {len(trades)} trade(s)")
        
        print_section("3. POSITION TRACKING")
        
        # Update position
        position = Position("NIFTY", quantity=0)
        old_qty = position.quantity
        position.apply_fill(fill)
        new_qty = position.quantity
        
        # Log position change
        pos_event = create_position_changed_event(
            instrument="NIFTY",
            old_quantity=old_qty,
            new_quantity=new_qty,
            realized_pnl=position.realized_pnl
        )
        logger.log_event(pos_event)
        
        print(f"✓ POSITION_CHANGED: NIFTY {old_qty} → {new_qty}")
        print(f"  Average Price: ₹{position.avg_price:,.2f}")
        print(f"  Realized P&L: ₹{position.realized_pnl:,.2f}")
        
        print_section("4. POSITION RECONCILIATION - MATCHING")
        
        # Internal positions
        internal_positions = {
            "NIFTY": position
        }
        
        # Broker positions (matching)
        broker_positions = {
            "NIFTY": 50
        }
        
        result = reconcile_positions(internal_positions, broker_positions)
        
        if result.matched:
            print("✓ Position reconciliation: MATCH")
            for mismatch in result.position_mismatches:
                print(f"  {mismatch.symbol}: "
                      f"Expected={mismatch.expected_quantity}, "
                      f"Actual={mismatch.actual_quantity} ✓")
        else:
            print("✗ Position reconciliation: MISMATCH")
        
        print_section("5. P&L RECONCILIATION - MATCHING")
        
        # Calculate unrealized P&L
        current_price = 25100.0
        unrealized = position.unrealized_pnl(current_price)
        total_pnl = position.realized_pnl + unrealized
        
        print(f"Internal P&L Calculation:")
        print(f"  Realized P&L: ₹{position.realized_pnl:,.2f}")
        print(f"  Unrealized P&L: ₹{unrealized:,.2f}")
        print(f"  Total P&L: ₹{total_pnl:,.2f}")
        
        # Simulate broker P&L (slightly different due to rounding)
        broker_pnl = 4999.50
        
        pnl_mismatch = reconcile_pnl(
            expected=total_pnl,
            actual=broker_pnl,
            tolerance=1.0
        )
        
        if pnl_mismatch.is_match:
            print(f"\n✓ P&L reconciliation: MATCH (within tolerance)")
            print(f"  Difference: ₹{pnl_mismatch.difference:,.2f}")
            print(f"  Tolerance: ₹{pnl_mismatch.tolerance:,.2f}")
        else:
            print(f"\n✗ P&L reconciliation: MISMATCH")
        
        print_section("6. DELIBERATE POSITION MISMATCH → ALERT")
        
        # Simulate broker with different position
        wrong_broker_positions = {
            "NIFTY": 25,  # Wrong!
            "BANKNIFTY": 10  # Extra position!
        }
        
        result = reconcile_positions(internal_positions, wrong_broker_positions)
        
        print(f"Reconciliation Status: {'MATCH' if result.matched else 'MISMATCH'}")
        
        if result.has_position_mismatches():
            print("\n✗ Position Mismatches Detected:")
            for mismatch in result.position_mismatches:
                if not mismatch.is_match:
                    print(f"  {mismatch.symbol}: "
                          f"Expected={mismatch.expected_quantity}, "
                          f"Actual={mismatch.actual_quantity}, "
                          f"Diff={mismatch.difference:+d}")
                    
                    # Generate alert
                    alert_msg = (
                        f"Position mismatch for {mismatch.symbol}: "
                        f"expected {mismatch.expected_quantity}, "
                        f"got {mismatch.actual_quantity}"
                    )
                    alert_sink.send(alert_msg)
                    
                    # Log reconciliation mismatch event
                    mismatch_event = create_reconciliation_mismatch_event(
                        instrument=mismatch.symbol,
                        expected=mismatch.expected_quantity,
                        actual=mismatch.actual_quantity,
                        mismatch_type="position"
                    )
                    logger.log_event(mismatch_event)
        
        print(f"\n🚨 {len(alert_sink)} ALERT(S) GENERATED:")
        for alert in alert_sink.get_alerts():
            print(f"  - {alert}")
        
        print_section("7. P&L MISMATCH → ALERT")
        
        # Simulate large P&L difference
        wrong_broker_pnl = 3000.0  # Significant difference!
        
        pnl_mismatch = reconcile_pnl(
            expected=total_pnl,
            actual=wrong_broker_pnl,
            tolerance=100.0
        )
        
        if not pnl_mismatch.is_match:
            print(f"✗ P&L Mismatch Detected:")
            print(f"  Expected: ₹{pnl_mismatch.expected:,.2f}")
            print(f"  Actual: ₹{pnl_mismatch.actual:,.2f}")
            print(f"  Difference: ₹{pnl_mismatch.difference:,.2f}")
            print(f"  Tolerance: ₹{pnl_mismatch.tolerance:,.2f}")
            
            alert_sink.send(
                f"P&L mismatch: expected ₹{pnl_mismatch.expected:,.2f}, "
                f"got ₹{pnl_mismatch.actual:,.2f} "
                f"(diff: ₹{pnl_mismatch.difference:,.2f})"
            )
        
        print(f"\n🚨 Total Alerts: {len(alert_sink)}")
        
        print_section("8. COMPLETE RECONCILIATION REPORT")
        
        # Create full report
        full_result = create_reconciliation_report(
            internal=internal_positions,
            broker=wrong_broker_positions,
            expected_pnl=total_pnl,
            actual_pnl=wrong_broker_pnl,
            pnl_tolerance=100.0
        )
        
        report = format_reconciliation_report(full_result)
        print(report)
        
        print_section("9. STRUCTURED LOG OUTPUT")
        
        print("JSON log file contents (last 3 events):\n")
        with open(log_file, 'r') as f:
            lines = f.readlines()
            for line in lines[-3:]:
                print(f"  {line.rstrip()}")
        
        print_section("10. TRADE BLOTTER OUTPUT")
        
        print(f"CSV blotter file: {blotter_file}")
        print(f"Total trades recorded: {blotter.get_trade_count()}")
        print("\nBlotter contents:")
        for trade in blotter.read_trades():
            print(f"  {trade.timestamp[:19]} | {trade.side:4s} | "
                  f"{trade.quantity:>3d} | {trade.instrument:10s} | "
                  f"₹{trade.price:>8,.2f} | {trade.strategy}")
        
        print_section("DEMONSTRATION COMPLETE")
        print("Key Features Demonstrated:")
        print("  ✓ Structured JSON logging")
        print("  ✓ Trade blotter with idempotency")
        print("  ✓ Position reconciliation")
        print("  ✓ P&L reconciliation with tolerance")
        print("  ✓ Alert generation on mismatches")
        print("  ✓ Complete reconciliation reporting")
        print("\nThe observability layer operates independently of trading logic,")
        print("providing transparency and auditability for all trading operations.")


if __name__ == "__main__":
    main()
