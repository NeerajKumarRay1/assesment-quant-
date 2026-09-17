"""Configuration for macro regime engine.

Defines strategy parameter overrides per regime and scoring configuration.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RegimeParameters:
    """Strategy parameters to apply for a specific regime.
    
    These override the base strategy parameters based on market conditions.
    Parameter names align with GridStrategy constructor arguments.
    
    Attributes:
        grid_spacing_multiplier: ATR multiplier for grid level spacing
                                Wider spacing in volatile environments
        max_pyramid_levels: Maximum number of pyramid additions allowed
                           Fewer levels in uncertain environments
        stop_loss_multiplier: ATR multiplier for stop loss distance
                             Wider stops in volatile environments
    
    Example:
        # Conservative RISK_OFF parameters
        RegimeParameters(
            grid_spacing_multiplier=2.0,  # Wide spacing
            max_pyramid_levels=1,         # No pyramiding
            stop_loss_multiplier=3.0      # Wide stop
        )
    """
    grid_spacing_multiplier: float
    max_pyramid_levels: int
    stop_loss_multiplier: float


@dataclass(frozen=True)
class MacroRegimeConfig:
    """Configuration for macro regime engine behavior.
    
    Defines how macro indicators are weighted, regime classification thresholds,
    circuit breaker triggers, and parameter overrides per regime.
    
    All weights should sum to 1.0 for interpretability, though not enforced.
    
    Attributes:
        trend_weight: Weight for trend indicator in regime score
        volatility_weight: Weight for volatility indicator (negative contribution)
        sentiment_weight: Weight for sentiment indicator
        
        risk_on_threshold: Score above which regime is RISK_ON
        risk_off_threshold: Score below which regime is RISK_OFF
        
        volatility_circuit_breaker_threshold: Volatility level that triggers circuit breaker
                                             Expressed as normalized volatility
        
        risk_on_params: Strategy parameters to use in RISK_ON regime
        neutral_params: Strategy parameters to use in NEUTRAL regime
        risk_off_params: Strategy parameters to use in RISK_OFF regime
    
    Example:
        MacroRegimeConfig(
            trend_weight=0.4,
            volatility_weight=0.3,
            sentiment_weight=0.3,
            risk_on_threshold=0.3,
            risk_off_threshold=-0.3,
            volatility_circuit_breaker_threshold=2.5,
            risk_on_params=RegimeParameters(1.0, 3, 2.0),
            neutral_params=RegimeParameters(1.5, 2, 2.5),
            risk_off_params=RegimeParameters(2.0, 1, 3.0)
        )
    """
    # Scoring weights (should sum to 1.0)
    trend_weight: float = 0.4
    volatility_weight: float = 0.3
    sentiment_weight: float = 0.3
    
    # Regime classification thresholds
    risk_on_threshold: float = 0.3
    risk_off_threshold: float = -0.3
    
    # Circuit breaker trigger
    volatility_circuit_breaker_threshold: float = 2.5
    
    # Parameter overrides per regime
    risk_on_params: RegimeParameters = RegimeParameters(
        grid_spacing_multiplier=1.0,
        max_pyramid_levels=3,
        stop_loss_multiplier=2.0
    )
    neutral_params: RegimeParameters = RegimeParameters(
        grid_spacing_multiplier=1.5,
        max_pyramid_levels=2,
        stop_loss_multiplier=2.5
    )
    risk_off_params: RegimeParameters = RegimeParameters(
        grid_spacing_multiplier=2.0,
        max_pyramid_levels=1,
        stop_loss_multiplier=3.0
    )

    def __post_init__(self):
        """Validate configuration values."""
        if self.risk_off_threshold >= self.risk_on_threshold:
            raise ValueError(
                f"risk_off_threshold ({self.risk_off_threshold}) must be less than "
                f"risk_on_threshold ({self.risk_on_threshold})"
            )
        
        if self.volatility_circuit_breaker_threshold <= 0:
            raise ValueError("volatility_circuit_breaker_threshold must be positive")
        
        # Validate weights are positive
        if any(w < 0 for w in [self.trend_weight, self.volatility_weight, self.sentiment_weight]):
            raise ValueError("All weights must be non-negative")
