"""Macro regime classification and decision models.

Represents market environment states and the decisions derived from
macro indicators. Used to adjust trading strategy parameters based on
prevailing market conditions.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Regime(Enum):
    """Market regime classification based on macro indicators.
    
    RISK_ON: Favorable environment - low volatility, positive trend, positive sentiment
    NEUTRAL: Mixed signals - moderate conditions
    RISK_OFF: Unfavorable environment - high volatility, negative trend, risk aversion
    """
    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"


@dataclass(frozen=True)
class MacroSnapshot:
    """Point-in-time snapshot of macro market indicators.
    
    Represents the key market environment proxies used for regime classification.
    All values should be normalized to comparable scales before scoring.
    
    Attributes:
        timestamp: When this snapshot was captured
        volatility: Market volatility proxy (e.g., ATR-based, VIX-like measure)
                   Expected range: [0, +inf), higher = more volatile
        trend: Market trend/momentum proxy (e.g., price rate of change)
               Expected range: [-1, +1], negative = bearish, positive = bullish
        sentiment: Risk appetite/sentiment proxy (e.g., put/call ratio derivative)
                  Expected range: [-1, +1], negative = fearful, positive = greedy
    
    Example:
        MacroSnapshot(
            timestamp=datetime(2026, 1, 15, 9, 30),
            volatility=0.8,   # High volatility (normalized)
            trend=-0.6,       # Bearish trend
            sentiment=-0.4    # Fearful sentiment
        )
        → Likely RISK_OFF regime
    """
    timestamp: datetime
    volatility: float
    trend: float
    sentiment: float


@dataclass(frozen=True)
class RegimeDecision:
    """Result of macro regime evaluation.
    
    Immutable decision object containing the classified regime, calculated score,
    circuit breaker status, and parameter overrides to apply to trading strategies.
    
    Attributes:
        regime: Classified market regime (RISK_ON, NEUTRAL, RISK_OFF)
        score: Raw regime score from weighted macro indicators
        circuit_breaker_active: Whether extreme conditions triggered circuit breaker
        circuit_breaker_reason: Explanation if circuit breaker active, None otherwise
        parameters: Strategy parameter overrides for this regime
                   Keys typically include: grid_spacing_multiplier, max_pyramid_levels, etc.
    
    Example:
        RegimeDecision(
            regime=Regime.RISK_OFF,
            score=-0.65,
            circuit_breaker_active=True,
            circuit_breaker_reason="volatility_above_threshold",
            parameters={
                'grid_spacing_multiplier': 2.0,
                'max_pyramid_levels': 1
            }
        )
    """
    regime: Regime
    score: float
    circuit_breaker_active: bool
    circuit_breaker_reason: str | None
    parameters: dict[str, float | int]
