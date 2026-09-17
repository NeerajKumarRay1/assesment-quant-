"""Rollover manager for handling contract expiry and transitions.

Provides logic to determine when a contract should be rolled over to the next
expiry based on configurable window before expiry.
"""

from dataclasses import dataclass
from datetime import date
from src.contracts.contract_master import ContractMaster


@dataclass(frozen=True)
class RolloverDecision:
    """Result of a rollover check.
    
    Attributes:
        required: Whether rollover should happen
        current_symbol: Current contract identifier (symbol + expiry)
        next_symbol: Next contract identifier, if available
        reason: Human-readable explanation
    """
    required: bool
    current_symbol: str | None
    next_symbol: str | None
    reason: str


class RolloverManager:
    """Manages contract rollover decisions based on expiry windows.
    
    Does NOT place orders automatically - only returns rollover decisions
    for the execution layer to act upon.
    """

    def __init__(self, contract_master: ContractMaster, rollover_days: int = 3) -> None:
        """Initialize rollover manager.
        
        Args:
            contract_master: Registry of available contracts
            rollover_days: Number of days before expiry to trigger rollover
        """
        self._contract_master = contract_master
        self._rollover_days = rollover_days

    def check_rollover(self, symbol: str, as_of: date) -> RolloverDecision:
        """Determine if rollover is required for a given symbol and date.
        
        Args:
            symbol: Contract symbol (e.g. "NIFTY")
            as_of: Current date to check against
            
        Returns:
            RolloverDecision indicating whether rollover is needed
        """
        current = self._contract_master.get_current_contract(symbol, as_of)
        
        if current is None:
            return RolloverDecision(
                required=False,
                current_symbol=None,
                next_symbol=None,
                reason="no_active_contract"
            )
        
        if current.expiry is None:
            return RolloverDecision(
                required=False,
                current_symbol=self._format_symbol(current.symbol, current.expiry),
                next_symbol=None,
                reason="no_expiry_set"
            )
        
        # Check if we're within the rollover window
        days_to_expiry = (current.expiry - as_of).days
        
        if days_to_expiry > self._rollover_days:
            return RolloverDecision(
                required=False,
                current_symbol=self._format_symbol(current.symbol, current.expiry),
                next_symbol=None,
                reason=f"expiry_not_near (>{self._rollover_days} days)"
            )
        
        # Rollover is required - find next contract
        next_contract = self._contract_master.get_next_contract(symbol, as_of)
        
        if next_contract is None:
            return RolloverDecision(
                required=True,
                current_symbol=self._format_symbol(current.symbol, current.expiry),
                next_symbol=None,
                reason="expiry_within_window_no_next_contract"
            )
        
        return RolloverDecision(
            required=True,
            current_symbol=self._format_symbol(current.symbol, current.expiry),
            next_symbol=self._format_symbol(next_contract.symbol, next_contract.expiry),
            reason=f"expiry_within_window ({days_to_expiry} days)"
        )

    @staticmethod
    def _format_symbol(symbol: str, expiry: date | None) -> str:
        """Format contract identifier for display."""
        if expiry is None:
            return symbol
        return f"{symbol}_{expiry.strftime('%Y%m%d')}"
