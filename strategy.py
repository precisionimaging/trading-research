"""
Trading strategy implementation - agents modify this file.

This file contains the strategy logic that gets iteratively improved.
Use technical indicators, risk management, and entry/exit rules.

Usage: uv run strategy.py
"""

import numpy as np
from dataclasses import dataclass

from prepare import (
    MarketData, backtest, evaluate_strategy,
    load_market_data, COMMISSION, SLIPPAGE, MAX_POSITION_SIZE
)

# Try to import technical analysis library
try:
    import ta
    HAS_TA = True
except ImportError:
    HAS_TA = False
    print("Warning: ta library not installed. Install with: pip install ta")


# ---------------------------------------------------------------------------
# Strategy Configuration (edit these)
# ----------------------------------------------------------------------------

# Data file to use (must be in ~/.cache/trading-research/)
DATA_FILE = "SPY_data"

# Strategy name (for logging)
STRATEGY_NAME = "baseline_rsi_macd"

# Capital allocation
INITIAL_CAPITAL = 100000.0

# Lookback period for strategy
LOOKBACK = 20

# Risk management
RISK_PER_TRADE = 0.02  # 2% of capital per trade
MAX_DAILY_LOSS = 0.05  # Stop trading if daily loss > 5%


# ---------------------------------------------------------------------------
# Technical Indicators
# ----------------------------------------------------------------------------

def calculate_sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average. Returns array same length as input."""
    sma = np.convolve(data, np.ones(period) / period, mode='valid')
    # Pad with NaN to match original length
    pad_width = period - 1
    return np.concatenate([np.full(pad_width, np.nan), sma])


def calculate_ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    alpha = 2 / (period + 1)
    ema = np.zeros_like(data)
    ema[0] = data[0]
    for i in range(1, len(data)):
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
    return ema


def calculate_rsi(data: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index."""
    delta = np.diff(data)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    avg_gain = np.convolve(gain, np.ones(period) / period, mode='valid')
    avg_loss = np.convolve(loss, np.ones(period) / period, mode='valid')

    rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
    rsi = 100 - (100 / (1 + rs))

    # Pad to match original length
    rsi = np.concatenate([np.full(period, 50.0), rsi])
    return rsi


def calculate_macd(data: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """MACD indicator. Returns (macd, signal, histogram)."""
    ema_fast = calculate_ema(data, fast)
    ema_slow = calculate_ema(data, slow)
    macd = ema_fast - ema_slow
    signal_line = calculate_ema(macd, signal)
    histogram = macd - signal_line
    return macd, signal_line, histogram


def calculate_bollinger_bands(data: np.ndarray, period: int = 20, std_dev: float = 2.0) -> tuple:
    """Bollinger Bands. Returns (upper, middle, lower)."""
    middle = calculate_sma(data, period)
    std = np.array([np.std(data[i-period:i]) if i >= period else 0 for i in range(len(data))])
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range."""
    tr = np.zeros(len(close))

    # True range
    high_low = high - low
    high_close = np.abs(high - np.concatenate([[close[0]], close[:-1]]))
    low_close = np.abs(low - np.concatenate([[close[0]], close[:-1]]))

    tr = np.maximum(high_low, np.maximum(high_close, low_close))

    # ATR
    atr = np.zeros_like(tr)
    atr[period-1] = np.mean(tr[:period])
    for i in range(period, len(tr)):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period

    return atr


# ---------------------------------------------------------------------------
# Strategy Implementation
# ----------------------------------------------------------------------------

def strategy_func(data: MarketData, current_bar: int) -> int:
    """
    Trading strategy function.

    This is the core logic that agents modify to improve performance.

    Args:
        data: MarketData object with OHLCV data
        current_bar: Current bar index (0-indexed, must be >= LOOKBACK)

    Returns:
        Position signal: -1 (short), 0 (flat), 1 (long)
    """
    # Validate we have enough data
    if current_bar < LOOKBACK:
        return 0

    # Extract price series up to current bar
    close = data.close[:current_bar+1]
    high = data.high[:current_bar+1]
    low = data.low[:current_bar+1]

    # --- INDICATOR CALCULATIONS ---
    # Modify these indicator settings and add/remove as needed

    # Moving averages
    sma_fast = calculate_sma(close, 10)
    sma_slow = calculate_sma(close, 30)

    # RSI
    rsi = calculate_rsi(close, 14)

    # MACD
    macd, macd_signal, macd_hist = calculate_macd(close, 12, 26, 9)

    # Bollinger Bands
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(close, 20, 2.0)

    # ATR for volatility
    atr = calculate_atr(high, low, close, 14)

    # --- ENTRY LOGIC ---
    # Conditions for entering trades

    # Long entry conditions
    long_conditions = [
        sma_fast[current_bar] > sma_slow[current_bar],  # Trend following
        rsi[current_bar] < 70,                          # Not overbought
        macd_hist[current_bar] > macd_hist[current_bar-1],  # MACD rising
        close[current_bar] > bb_middle[current_bar],    # Above BB middle
    ]

    # Short entry conditions
    short_conditions = [
        sma_fast[current_bar] < sma_slow[current_bar],  # Downtrend
        rsi[current_bar] > 30,                          # Not oversold
        macd_hist[current_bar] < macd_hist[current_bar-1],  # MACD falling
        close[current_bar] < bb_middle[current_bar],    # Below BB middle
    ]

    # --- EXIT LOGIC ---
    # Currently handled by backtest engine when signal changes

    # --- SIGNAL GENERATION ---
    # Apply logic to generate final signal

    # All conditions must be true for entry
    if all(long_conditions):
        return 1  # Long
    elif all(short_conditions):
        return -1  # Short
    else:
        return 0  # Flat


def create_strategy_wrapper():
    """
    Create a wrapper function that can be used by the backtest engine.
    This allows the strategy to maintain state between calls if needed.
    """
    current_position = 0
    last_signal = 0

    def wrapper(data: MarketData, current_bar: int) -> int:
        nonlocal current_position, last_signal

        # Get new signal from strategy
        signal = strategy_func(data, current_bar)

        # Prevent rapid signal changes (minimize whipsaws)
        if signal != last_signal and signal != 0:
            # Only change if confirmed (could add confirmation logic here)
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

def main():
    print(f"Running strategy: {STRATEGY_NAME}")
    print(f"Data file: {DATA_FILE}")
    print(f"Initial capital: ${INITIAL_CAPITAL:,.2f}")
    print()

    # Load market data
    data = load_market_data(DATA_FILE)

    # Print data info
    print(f"Loaded {len(data.close)} bars of {data.ticker} data")
    print(f"Date range: {data.to_dataframe().index[0]} to {data.to_dataframe().index[-1]}")
    print()

    # Create strategy wrapper
    strategy = create_strategy_wrapper()

    # Run backtest
    print("Running backtest...")
    result = evaluate_strategy(data, strategy, INITIAL_CAPITAL)

    # Print results
    print(result.summary())

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
