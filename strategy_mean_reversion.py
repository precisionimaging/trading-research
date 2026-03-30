"""
Short-Term Mean Reversion Strategy

Strategy: Bet on price reverting to mean after short-term extremes.

Logic:
1. Calculate VWAP (Volume Weighted Average Price) for the day
2. When price deviates significantly from VWAP, expect reversion
3. Use RSI to confirm overbought/oversold conditions
4. Hold for short periods (15-60 minutes) until mean reversion

Advantage over directional prediction:
- Doesn't require predicting daily close direction
- Works in range-bound markets
- Short holding periods reduce overnight risk
- Multiple opportunities per day
"""

import numpy as np
from dataclasses import dataclass
from datetime import datetime

from prepare import (
    MarketData, backtest, evaluate_strategy,
    load_market_data, COMMISSION, SLIPPAGE, MAX_POSITION_SIZE
)

# ---------------------------------------------------------------------------
# Strategy Configuration (edit these)
# ----------------------------------------------------------------------------

# Data file (intraday 5-min data)
DATA_FILE = "SPY_data"

# Strategy name
STRATEGY_NAME = "mean_reversion_intraday"

# Capital allocation
INITIAL_CAPITAL = 100000.0

# Lookback period
LOOKBACK = 100  # Enough for intraday VWAP calculation

# Risk management
RISK_PER_TRADE = 0.02  # 2% per trade
MAX_DAILY_LOSS = 0.05

# ---------------------------------------------------------------------------
# Technical Indicators
# ----------------------------------------------------------------------------

def calculate_vwap(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """
    Calculate cumulative VWAP.

    VWAP = Cumulative(price * volume) / Cumulative(volume)
    """
    cumulative_volume = np.cumsum(volume)
    cumulative_price_volume = np.cumsum(close * volume)
    vwap = cumulative_price_volume / np.where(cumulative_volume == 0, 1, cumulative_volume)
    return vwap


def calculate_sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average."""
    sma = np.convolve(data, np.ones(period) / period, mode='valid')
    pad_width = period - 1
    return np.concatenate([np.full(pad_width, np.nan), sma])


def calculate_rsi(data: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index."""
    delta = np.diff(data)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    avg_gain = np.convolve(gain, np.ones(period) / period, mode='valid')
    avg_loss = np.convolve(loss, np.ones(period) / period, mode='valid')

    rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
    rsi = 100 - (100 / (1 + rs))

    rsi = np.concatenate([np.full(period, 50.0), rsi])
    return rsi


def calculate_bollinger_bands(data: np.ndarray, period: int = 20, std_dev: float = 2.0) -> tuple:
    """Bollinger Bands. Returns (upper, middle, lower)."""
    middle = calculate_sma(data, period)

    # Calculate rolling standard deviation using convolve (much faster than list comprehension)
    # Variance = E[X^2] - (E[X])^2
    squares = data ** 2
    mean_sq = np.convolve(squares, np.ones(period) / period, mode='valid')
    mean = np.convolve(data, np.ones(period) / period, mode='valid')
    var = mean_sq - mean ** 2
    std = np.sqrt(np.maximum(var, 0))  # Ensure non-negative

    # Pad to match original length
    std = np.concatenate([np.zeros(period - 1), std])

    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range."""
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1]))
    )
    atr = np.convolve(tr, np.ones(period) / period, mode='valid')
    atr = np.concatenate([np.full(period, np.nan), atr])
    return atr


# ---------------------------------------------------------------------------
# Main Strategy Function
# ----------------------------------------------------------------------------

def strategy_func(data: MarketData, current_bar: int) -> int:
    """
    Mean reversion strategy based on VWAP and RSI.

    Returns:
        Position signal: -1 (short), 0 (flat), 1 (long)
    """
    # Need enough data
    if current_bar < LOOKBACK:
        return 0

    # Extract price series up to current bar
    close = data.close[:current_bar+1]
    high = data.high[:current_bar+1]
    low = data.low[:current_bar+1]
    volume = data.volume[:current_bar+1]

    # Calculate indicators
    vwap = calculate_vwap(close, volume)  # Keep for reference, but using BB now
    rsi = calculate_rsi(close, 14)
    upper, middle, lower = calculate_bollinger_bands(close, 20, 2.0)
    atr = calculate_atr(high, low, close, 14)

    # Current values
    current_price = close[current_bar]
    current_rsi = rsi[current_bar]

    # ---------------------------------------------------------------------------
    # Entry Conditions
    # ----------------------------------------------------------------------------

    # Mean reversion based on short-term momentum with RSI confirmation
    # If price moved X% in N bars, bet on reversal

    # Configuration (experiment 6: add RSI filter)
    REVERSAL_PERIOD = 20  # Look back N bars
    REVERSAL_THRESHOLD = 0.003  # X% move = 0.3%

    # RSI filter: avoid trading when RSI is extreme (strong momentum likely to continue)
    RSI_EXTREME_HIGH = 75  # Don't short if RSI is very high
    RSI_EXTREME_LOW = 25  # Don't long if RSI is very low

    if current_bar < REVERSAL_PERIOD:
        return 0

    # Calculate recent price change
    past_price = close[current_bar - REVERSAL_PERIOD]
    price_change = (current_price - past_price) / past_price

    # Long: Price dropped significantly, expect bounce (but not if RSI is extreme oversold)
    if price_change < -REVERSAL_THRESHOLD and current_rsi > RSI_EXTREME_LOW:
        return 1

    # Short: Price rose significantly, expect pullback (but not if RSI is extreme overbought)
    elif price_change > REVERSAL_THRESHOLD and current_rsi < RSI_EXTREME_HIGH:
        return -1

    # ---------------------------------------------------------------------------
    # Exit Conditions (handled by backtest engine automatically)
    # ----------------------------------------------------------------------------

    # Note: The backtest engine in prepare.py will automatically exit
    # when the signal changes. For mean reversion, we rely on signal
    # flipping when price returns to middle band range.

    return 0  # No position


def create_strategy_wrapper():
    """
    Create a wrapper function that prevents rapid signal changes.
    """
    current_position = 0
    last_signal = 0

    def wrapper(data: MarketData, current_bar: int) -> int:
        nonlocal current_position, last_signal

        # Get new signal from strategy
        signal = strategy_func(data, current_bar)

        # Prevent rapid signal changes (minimize whipsaws)
        if signal != last_signal and signal != 0:
            last_signal = signal
            current_position = signal
        elif signal == 0:
            current_position = 0
            last_signal = 0

        return current_position

    return wrapper


# ---------------------------------------------------------------------------
# Main Execution
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    # Load data
    print(f"Loading data: {DATA_FILE}")
    data = load_market_data(DATA_FILE)

    if data is None:
        print(f"Error: Could not load data file '{DATA_FILE}'")
        print(f"Available files in ~/.cache/trading-research/:")
        import os
        cache_dir = os.path.expanduser("~/.cache/trading-research/")
        if os.path.exists(cache_dir):
            for f in os.listdir(cache_dir):
                if f.endswith('.parquet') or f.endswith('.csv'):
                    print(f"  - {f}")
        exit(1)

    print(f"Loaded {len(data.close)} bars")
    print(f"Date range: {data.datetime[0]} to {data.datetime[-1]}")
    print(f"Strategy: {STRATEGY_NAME}")
    print(f"Initial capital: ${INITIAL_CAPITAL:,.0f}")
    print()

    # Create strategy wrapper
    strategy = create_strategy_wrapper()

    # Run backtest and evaluate
    print("Running backtest...")
    results = evaluate_strategy(data, strategy, INITIAL_CAPITAL)

    # Print results
    print()
    print("=" * 60)
    print("Strategy Performance Summary")
    print("=" * 60)
    print(results.summary())
    print()
