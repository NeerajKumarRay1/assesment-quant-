"""Contract master for managing derivative instruments and expiry information.

Provides a simple registry of contracts with lookup capabilities for current
and next contracts based on expiry dates. Uses the existing Instrument model
from src.core to avoid duplication.
"""

from datetime import date
from src.core.instrument import Instrument


class ContractMaster:
    """Registry of derivative contracts with expiry-based lookup.
    
    This is a minimal implementation using deterministic fixtures rather than
    a complete exchange master. In production, this would load from a broker
    API or exchange reference data feed.
    """

    def __init__(self, contracts: list[Instrument]) -> None:
        """Initialize with a list of contracts.
        
        Args:
            contracts: List of Instrument objects with expiry dates set.
        """
        self._contracts = contracts
        # Index by (symbol, expiry) for fast lookup
        self._by_key: dict[tuple[str, date], Instrument] = {}
        for c in contracts:
            if c.expiry is not None:
                key = (c.symbol, c.expiry)
                self._by_key[key] = c

    def get_contract(self, symbol: str, expiry: date) -> Instrument | None:
        """Lookup a specific contract by symbol and expiry date.
        
        Args:
            symbol: Contract symbol (e.g. "NIFTY")
            expiry: Expiry date
            
        Returns:
            Instrument if found, None otherwise
        """
        return self._by_key.get((symbol, expiry))

    def get_current_contract(self, symbol: str, as_of: date) -> Instrument | None:
        """Find the currently active contract for a symbol.
        
        Returns the nearest unexpired contract as of the given date.
        
        Args:
            symbol: Contract symbol
            as_of: Reference date
            
        Returns:
            Active Instrument, or None if no valid contract exists
        """
        candidates = [
            c for c in self._contracts 
            if c.symbol == symbol and c.expiry is not None and c.expiry >= as_of
        ]
        if not candidates:
            return None
        # Return the contract with the nearest expiry
        return min(candidates, key=lambda c: c.expiry)  # type: ignore

    def get_next_contract(self, symbol: str, as_of: date) -> Instrument | None:
        """Find the next contract after the current one.
        
        Args:
            symbol: Contract symbol
            as_of: Reference date
            
        Returns:
            Next Instrument, or None if no next contract exists
        """
        current = self.get_current_contract(symbol, as_of)
        if current is None or current.expiry is None:
            return None
        
        # Find contracts expiring after the current one
        candidates = [
            c for c in self._contracts
            if c.symbol == symbol and c.expiry is not None and c.expiry > current.expiry
        ]
        if not candidates:
            return None
        
        return min(candidates, key=lambda c: c.expiry)  # type: ignore

    def list_contracts(self, symbol: str) -> list[Instrument]:
        """List all contracts for a given symbol, sorted by expiry.
        
        Args:
            symbol: Contract symbol
            
        Returns:
            List of Instrument objects sorted by expiry date
        """
        contracts = [
            c for c in self._contracts 
            if c.symbol == symbol and c.expiry is not None
        ]
        return sorted(contracts, key=lambda c: c.expiry)  # type: ignore
