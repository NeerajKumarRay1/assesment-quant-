"""Position and P&L reconciliation."""

from dataclasses import dataclass
from datetime import datetime, UTC
from src.core.position import Position


@dataclass
class PositionMismatch:
    """Represents a position mismatch between expected and actual."""
    symbol: str
    expected_quantity: int
    actual_quantity: int
    difference: int
    
    @property
    def is_match(self) -> bool:
        """Check if positions match."""
        return self.difference == 0


@dataclass
class PnLMismatch:
    """Represents a P&L mismatch between expected and actual."""
    expected: float
    actual: float
    difference: float
    tolerance: float
    
    @property
    def is_match(self) -> bool:
        """Check if P&L matches within tolerance."""
        return abs(self.difference) <= self.tolerance


@dataclass
class ReconciliationResult:
    """Complete reconciliation result.
    
    Contains position mismatches, P&L comparison, and overall status.
    """
    timestamp: datetime
    matched: bool
    position_mismatches: list[PositionMismatch]
    pnl_mismatch: PnLMismatch | None = None
    
    def get_mismatched_symbols(self) -> list[str]:
        """Get list of symbols with position mismatches.
        
        Returns:
            List of symbol names
        """
        return [m.symbol for m in self.position_mismatches if not m.is_match]
    
    def has_position_mismatches(self) -> bool:
        """Check if any position mismatches exist.
        
        Returns:
            True if mismatches found
        """
        return any(not m.is_match for m in self.position_mismatches)
    
    def has_pnl_mismatch(self) -> bool:
        """Check if P&L mismatch exists.
        
        Returns:
            True if P&L mismatch outside tolerance
        """
        return self.pnl_mismatch is not None and not self.pnl_mismatch.is_match


def reconcile_positions(
    internal: dict[str, Position],
    broker: dict[str, int],
    tolerance: int = 0
) -> ReconciliationResult:
    """Reconcile internal positions against broker positions.
    
    Compares position quantities for all symbols present in either internal
    or broker data. Uses exact comparison (tolerance for future extensions).
    
    Args:
        internal: Dictionary mapping symbol to Position object
        broker: Dictionary mapping symbol to quantity (from broker)
        tolerance: Allowed difference in quantities (default: 0 for exact match)
        
    Returns:
        ReconciliationResult with all position comparisons
        
    Example:
        internal = {"NIFTY": Position("NIFTY", quantity=50)}
        broker = {"NIFTY": 50, "BANKNIFTY": 10}
        result = reconcile_positions(internal, broker)
    """
    # Get all symbols from both sources
    all_symbols = set(internal.keys()) | set(broker.keys())
    
    mismatches: list[PositionMismatch] = []
    
    for symbol in sorted(all_symbols):
        # Get internal quantity
        if symbol in internal:
            expected_qty = internal[symbol].quantity
        else:
            expected_qty = 0
        
        # Get broker quantity
        actual_qty = broker.get(symbol, 0)
        
        # Calculate difference
        difference = actual_qty - expected_qty
        
        # Create mismatch record (even if matched, for complete reporting)
        mismatch = PositionMismatch(
            symbol=symbol,
            expected_quantity=expected_qty,
            actual_quantity=actual_qty,
            difference=difference
        )
        mismatches.append(mismatch)
    
    # Overall match status
    matched = all(abs(m.difference) <= tolerance for m in mismatches)
    
    return ReconciliationResult(
        timestamp=datetime.now(UTC),
        matched=matched,
        position_mismatches=mismatches
    )


def reconcile_pnl(
    expected: float,
    actual: float,
    tolerance: float = 1.0
) -> PnLMismatch:
    """Reconcile P&L values with floating-point tolerance.
    
    Compares expected vs actual P&L using configurable tolerance.
    Critical for comparing backtest results against live/broker P&L.
    
    Args:
        expected: Expected P&L (from internal calculation or backtest)
        actual: Actual P&L (from broker or external source)
        tolerance: Maximum allowed absolute difference (default: ₹1.00)
        
    Returns:
        PnLMismatch object with comparison results
        
    Example:
        mismatch = reconcile_pnl(
            expected=10000.00,
            actual=9999.50,
            tolerance=1.0
        )
        assert mismatch.is_match  # Within tolerance
    """
    difference = actual - expected
    
    return PnLMismatch(
        expected=expected,
        actual=actual,
        difference=difference,
        tolerance=tolerance
    )


def format_reconciliation_report(result: ReconciliationResult) -> str:
    """Format reconciliation result as human-readable report.
    
    Args:
        result: ReconciliationResult to format
        
    Returns:
        Formatted string report
    """
    lines = []
    lines.append("=" * 70)
    lines.append("POSITION RECONCILIATION REPORT")
    lines.append("=" * 70)
    lines.append(f"Timestamp: {result.timestamp.isoformat()}")
    lines.append(f"Overall Status: {'✓ MATCH' if result.matched else '✗ MISMATCH'}")
    lines.append("")
    
    # Position details
    lines.append("POSITIONS")
    lines.append("-" * 70)
    
    for mismatch in result.position_mismatches:
        status = "✓" if mismatch.is_match else "✗"
        lines.append(f"{status} {mismatch.symbol:15s} "
                    f"Expected: {mismatch.expected_quantity:>6d}  "
                    f"Actual: {mismatch.actual_quantity:>6d}  "
                    f"Diff: {mismatch.difference:>+6d}")
    
    # P&L details if present
    if result.pnl_mismatch:
        lines.append("")
        lines.append("P&L RECONCILIATION")
        lines.append("-" * 70)
        pnl = result.pnl_mismatch
        status = "✓ MATCH" if pnl.is_match else "✗ MISMATCH"
        lines.append(f"Expected P&L:  ₹{pnl.expected:>12,.2f}")
        lines.append(f"Actual P&L:    ₹{pnl.actual:>12,.2f}")
        lines.append(f"Difference:    ₹{pnl.difference:>+12,.2f}")
        lines.append(f"Tolerance:     ₹{pnl.tolerance:>12,.2f}")
        lines.append(f"Status: {status}")
    
    lines.append("=" * 70)
    
    return "\n".join(lines)


def create_reconciliation_report(
    internal: dict[str, Position],
    broker: dict[str, int],
    expected_pnl: float | None = None,
    actual_pnl: float | None = None,
    pnl_tolerance: float = 1.0
) -> ReconciliationResult:
    """Create complete reconciliation report with positions and P&L.
    
    Convenience function that combines position and P&L reconciliation.
    
    Args:
        internal: Internal position tracking
        broker: Broker positions
        expected_pnl: Expected P&L (optional)
        actual_pnl: Actual P&L from broker (optional)
        pnl_tolerance: P&L comparison tolerance
        
    Returns:
        Complete ReconciliationResult
    """
    # Reconcile positions
    result = reconcile_positions(internal, broker)
    
    # Add P&L reconciliation if data provided
    if expected_pnl is not None and actual_pnl is not None:
        pnl_mismatch = reconcile_pnl(expected_pnl, actual_pnl, pnl_tolerance)
        result.pnl_mismatch = pnl_mismatch
        
        # Update overall match status to include P&L
        result.matched = result.matched and pnl_mismatch.is_match
    
    return result
