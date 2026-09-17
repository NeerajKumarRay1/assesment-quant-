"""Macro regime engine for market environment classification.

Evaluates macro indicators to classify market regime and provide parameter
overrides and circuit breaker signals for trading strategies.
"""

from src.macro.regime import Regime, MacroSnapshot, RegimeDecision
from src.macro.config import MacroRegimeConfig, RegimeParameters


class MacroRegimeEngine:
    """Engine for evaluating macro market conditions and classifying regime.
    
    Responsibilities:
    - Accept macro indicator snapshots
    - Calculate deterministic regime score
    - Classify into RISK_ON, NEUTRAL, or RISK_OFF
    - Detect extreme conditions requiring circuit breaker
    - Provide regime-appropriate strategy parameters
    
    Does NOT:
    - Place or cancel orders
    - Directly modify strategy behavior
    - Fetch live market data
    
    The engine produces RegimeDecision objects that downstream components
    (strategies, risk manager) can consume to adjust their behavior.
    """

    def __init__(self, config: MacroRegimeConfig):
        """Initialize macro regime engine with configuration.
        
        Args:
            config: Configuration defining weights, thresholds, and parameters
        """
        self._config = config

    def evaluate(self, snapshot: MacroSnapshot) -> RegimeDecision:
        """Evaluate macro snapshot and produce regime decision.
        
        Process:
        1. Check for circuit breaker conditions (extreme volatility)
        2. Normalize inputs to comparable scales
        3. Calculate weighted regime score
        4. Classify regime based on score thresholds
        5. Select appropriate parameter overrides
        6. Return complete decision
        
        Args:
            snapshot: Current macro indicator values
            
        Returns:
            RegimeDecision with regime classification, score, circuit breaker status,
            and parameter overrides
            
        Example:
            snapshot = MacroSnapshot(
                timestamp=datetime.now(),
                volatility=0.5,
                trend=0.6,
                sentiment=0.4
            )
            decision = engine.evaluate(snapshot)
            # decision.regime == Regime.RISK_ON
            # decision.parameters['max_pyramid_levels'] == 3
        """
        # 1. Check circuit breaker first
        circuit_breaker_active, circuit_breaker_reason = self._check_circuit_breaker(snapshot)
        
        # 2. Normalize inputs (already expected in normalized form, but validate)
        normalized_trend = self._normalize_trend(snapshot.trend)
        normalized_volatility = self._normalize_volatility(snapshot.volatility)
        normalized_sentiment = self._normalize_sentiment(snapshot.sentiment)
        
        # 3. Calculate regime score
        # Positive contributors: trend, sentiment
        # Negative contributor: volatility (high vol is bad for risk-taking)
        score = (
            self._config.trend_weight * normalized_trend
            - self._config.volatility_weight * normalized_volatility
            + self._config.sentiment_weight * normalized_sentiment
        )
        
        # 4. Classify regime
        regime = self._classify_regime(score)
        
        # 5. Select parameters based on regime
        parameters = self._get_regime_parameters(regime)
        
        # 6. Return decision
        return RegimeDecision(
            regime=regime,
            score=score,
            circuit_breaker_active=circuit_breaker_active,
            circuit_breaker_reason=circuit_breaker_reason,
            parameters=parameters
        )

    def _check_circuit_breaker(self, snapshot: MacroSnapshot) -> tuple[bool, str | None]:
        """Check if extreme conditions warrant circuit breaker activation.
        
        Circuit breaker triggers on extreme volatility. When active, it signals
        the risk manager to block new risk-increasing positions.
        
        Args:
            snapshot: Current macro indicators
            
        Returns:
            Tuple of (circuit_breaker_active, reason)
        """
        if snapshot.volatility >= self._config.volatility_circuit_breaker_threshold:
            return True, f"volatility_above_threshold ({snapshot.volatility:.2f} >= {self._config.volatility_circuit_breaker_threshold})"
        
        return False, None

    def _normalize_trend(self, trend: float) -> float:
        """Normalize trend indicator to [-1, 1] range.
        
        Trend is expected to already be normalized (e.g., momentum indicator).
        This method validates and clips to expected range.
        
        Args:
            trend: Raw trend value
            
        Returns:
            Normalized trend in [-1, 1]
        """
        # Clip to expected range
        return max(-1.0, min(1.0, trend))

    def _normalize_volatility(self, volatility: float) -> float:
        """Normalize volatility indicator to [0, 1] range.
        
        Higher volatility gets higher normalized value. For scoring purposes,
        we want volatility to negatively contribute to the regime score.
        
        Args:
            volatility: Raw volatility value (0 to circuit_breaker_threshold or beyond)
            
        Returns:
            Normalized volatility in [0, 1]
        """
        # Normalize using circuit breaker threshold as reference
        # 0 = no volatility, 1 = at/above circuit breaker threshold
        normalized = volatility / self._config.volatility_circuit_breaker_threshold
        return min(1.0, normalized)

    def _normalize_sentiment(self, sentiment: float) -> float:
        """Normalize sentiment indicator to [-1, 1] range.
        
        Sentiment is expected to already be normalized (e.g., fear/greed index).
        This method validates and clips to expected range.
        
        Args:
            sentiment: Raw sentiment value
            
        Returns:
            Normalized sentiment in [-1, 1]
        """
        # Clip to expected range
        return max(-1.0, min(1.0, sentiment))

    def _classify_regime(self, score: float) -> Regime:
        """Classify regime based on calculated score.
        
        Uses configured thresholds to map score to regime:
        - score >= risk_on_threshold → RISK_ON
        - score <= risk_off_threshold → RISK_OFF
        - otherwise → NEUTRAL
        
        Args:
            score: Calculated regime score
            
        Returns:
            Classified regime
        """
        if score >= self._config.risk_on_threshold:
            return Regime.RISK_ON
        elif score <= self._config.risk_off_threshold:
            return Regime.RISK_OFF
        else:
            return Regime.NEUTRAL

    def _get_regime_parameters(self, regime: Regime) -> dict[str, float | int]:
        """Get strategy parameter overrides for the given regime.
        
        Args:
            regime: Classified regime
            
        Returns:
            Dictionary of parameter name -> value mappings
        """
        # Select regime-specific parameters
        if regime == Regime.RISK_ON:
            params = self._config.risk_on_params
        elif regime == Regime.RISK_OFF:
            params = self._config.risk_off_params
        else:  # NEUTRAL
            params = self._config.neutral_params
        
        # Convert to dictionary for easy consumption
        return {
            'grid_spacing_multiplier': params.grid_spacing_multiplier,
            'max_pyramid_levels': params.max_pyramid_levels,
            'stop_loss_multiplier': params.stop_loss_multiplier
        }
