"""
0DTE Credit Spread Strategy

This strategy identifies optimal times to enter call or put credit spreads on SPY/QQQ.

Key concepts:
- Time-based pattern recognition (morning vs afternoon)
- Direction prediction for the rest of the day
- Volatility filtering (avoid high-volatility days)
- Support/resistance levels

For 0DTE credit spreads:
- CALL credit spread = sell calls above current price (bet on flat/down)
- PUT credit spread = sell puts below current price (bet on flat/up)
- Target: Price stays between strikes by close

Strategy signals:
- 1 = Up (bet on flat/up → put credit spread)
- 0 = Flat (bet on sideways → either spread)
- -1 = Down (bet on flat/down → call credit spread)
"""

import numpy as np
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

from prepare import (
    MarketData, backtest, evaluate_strategy,
    load_market_data, COMMISSION, SLIPPAGE, MAX_POSITION_SIZE
)

# ---------------------------------------------------------------------------
# Strategy Configuration
# ----------------------------------------------------------------------------

# Data file (intraday 5-min data)
DATA_FILE = "SPY_data"

# Strategy name
STRATEGY_NAME = "0dte_credit_spreads"

# Capital allocation
INITIAL_CAPITAL = 100000.0

# Lookback period for pattern recognition
LOOKBACK = 78  # ~1 day of 5-min bars (78 bars = 6.5 hours)

# Risk management
RISK_PER_TRADE = 0.02  # 2% of capital per trade
MAX_DAILY_LOSS = 0.05  # Stop trading if daily loss > 5%

# Trading times (Eastern time)
ENTRY_TIME_START = "10:00"  # Earliest entry
ENTRY_TIME_END = "14:30"    # Latest entry (30 min before close)
MARKET_CLOSE = "16:00"      # Market close

# Volatility thresholds
ATR_THRESHOLD = 1.5  # Avoid trading if ATR > 1.5x average

# ---------------------------------------------------------------------------
# Time-based Utilities
# ----------------------------------------------------------------------------

def get_time_of_day(timestamp: int) -> float:
    """
    Convert Unix timestamp to hour of day (0-24).

    Args:
        timestamp: Unix timestamp in seconds

    Returns:
        Hour of day as float (e.g., 10.5 = 10:30 AM)
    """
    dt = datetime.fromtimestamp(timestamp)
    return dt.hour + dt.minute / 60.0


def is_market_hours(timestamp: int) -> bool:
    """Check if timestamp is within market hours (9:30 - 16:00)."""
    hour = get_time_of_day(timestamp)
    return 9.5 <= hour < 16.0


def is_entry_window(timestamp: int) -> bool:
    """Check if timestamp is within entry window."""
    hour = get_time_of_day(timestamp)
    start = datetime.strptime(ENTRY_TIME_START, "%H:%M").hour
    end = datetime.strptime(ENTRY_TIME_END, "%H:%M").hour + 0.5  # Add 30 mins
    return start <= hour <= end


def get_session_type(timestamp: int) -> str:
    """
    Determine trading session: morning, afternoon, or late.

    Returns:
        'morning', 'afternoon', or 'late'
    """
    hour = get_time_of_day(timestamp)
    if hour < 11.0:
        return 'morning'
    elif hour < 14.0:
        return 'afternoon'
    else:
        return 'late'


# ---------------------------------------------------------------------------
# Technical Indicators (Intraday)
# ----------------------------------------------------------------------------

def calculate_sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average. Returns array same length as input."""
    sma = np.convolve(data, np.ones(period) / period, mode='valid')
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

    rsi = np.concatenate([np.full(period, 50.0), rsi])
    return rsi


def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range."""
    tr = np.zeros(len(close))

    high_low = high - low
    high_close = np.abs(high - np.concatenate([[close[0]], close[:-1]]))
    low_close = np.abs(low - np.concatenate([[close[0]], close[:-1]]))

    tr = np.maximum(high_low, np.maximum(high_close, low_close))

    atr = np.zeros_like(tr)
    atr[period-1] = np.mean(tr[:period])
    for i in range(period, len(tr)):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period

    return atr


def calculate_vwap(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """
    Volume Weighted Average Price.

    Intraday VWAP is key for 0DTE:
    - Price above VWAP = bullish
    - Price below VWAP = bearish
    - VWAP acts as dynamic support/resistance
    """
    cumulative_volume = np.cumsum(volume)
    cumulative_price_volume = np.cumsum(close * volume)
    vwap = cumulative_price_volume / np.where(cumulative_volume == 0, 1, cumulative_volume)
    return vwap


# ---------------------------------------------------------------------------
# Pattern Recognition
# ----------------------------------------------------------------------------

def detect_morning_sweep(close: np.ndarray, index: int) -> bool:
    """
    Detect morning sweep pattern:
    - Price makes a push in one direction early in session
    - Then reverses and trends opposite direction rest of day

    Signs:
    - Strong move first 30-60 mins (9:30-10:30)
    - Then consolidation or reversal
    """
    if index < 15:  # Need at least 75 mins of data
        return False

    # First 12 bars (1 hour) vs last 12 bars (1 hour)
    early_open = close[index-12] if index >= 12 else close[0]
    early_close = close[index]
    early_change = (early_close - early_open) / early_open

    # Look for early strong move (>0.5%)
    if abs(early_change) > 0.005:
        return True

    return False


def detect_afternoon_drift(close: np.ndarray, volume: np.ndarray, index: int) -> str:
    """
    Detect afternoon drift pattern.

    Returns:
        'up' if drifting up, 'down' if drifting down, 'none' otherwise
    """
    if index < 20:
        return 'none'

    # Last 20 bars (100 mins)
    recent_close = close[index-20:index]
    recent_volume = volume[index-20:index]

    # Calculate drift with volume weighting
    volume_weighted_change = np.sum(np.diff(recent_close) * recent_volume[1:]) / np.sum(recent_volume[1:])

    if volume_weighted_change > 0.0005:  # Upward drift
        return 'up'
    elif volume_weighted_change < -0.0005:  # Downward drift
        return 'down'
    else:
        return 'none'


def detect_support_resistance(close: np.ndarray, high: np.ndarray, low: np.ndarray, index: int, lookback: int = 78) -> tuple:
    """
    Detect key support and resistance levels.

    Returns:
        (support_level, resistance_level) or (None, None)
    """
    if index < lookback:
        return None, None

    # Recent data
    recent_high = high[index-lookback:index]
    recent_low = low[index-lookback:index]
    recent_close = close[index-lookback:index]

    # Find resistance (local highs)
    resistance = np.percentile(recent_high, 90)

    # Find support (local lows)
    support = np.percentile(recent_low, 10)

    return support, resistance


def detect_volatility_spike(atr: np.ndarray, index: int, lookback: int = 78) -> bool:
    """
    Detect if current volatility is unusually high.

    Returns:
        True if ATR is > ATR_THRESHOLD times average
    """
    if index < lookback:
        return True  # Not enough data, be conservative

    current_atr = atr[index]
    avg_atr = np.mean(atr[index-lookback:index])

    return current_atr > avg_atr * ATR_THRESHOLD


# ---------------------------------------------------------------------------
# Strategy Implementation
# ----------------------------------------------------------------------------

def strategy_func(data: MarketData, current_bar: int) -> int:
    """
    0DTE Credit Spread Strategy Function

    Returns:
        1 = Up (put credit spread)
        0 = Flat (no trade)
        -1 = Down (call credit spread)
    """
    # Need enough data for analysis
    if current_bar < LOOKBACK:
        return 0

    # Extract price series
    close = data.close[:current_bar+1]
    high = data.high[:current_bar+1]
    low = data.low[:current_bar+1]
    volume = data.volume[:current_bar+1]
    timestamps = data.datetime[:current_bar+1]

    # Check if within entry window
    current_time = data.datetime[current_bar]

    # Check if we have enough intraday bars
    if current_bar < LOOKBACK:
        return 0

    # Check time-based entry window
    # Temporarily disabled to test strategy logic
    # if not is_entry_window(current_time):
    #     return 0

    # Get session type
    session = get_session_type(current_time)

    # Calculate indicators
    vwap = calculate_vwap(close, volume)
    rsi = calculate_rsi(close, 14)
    atr = calculate_atr(high, low, close, 14)

    # Check for NaN
    if (np.isnan(vwap[current_bar]) or np.isnan(rsi[current_bar]) or
        np.isnan(atr[current_bar])):
        return 0

    # Volatility filter - avoid high volatility days
    if detect_volatility_spike(atr, current_bar):
        return 0

    current_price = close[current_bar]
    vwap_level = vwap[current_bar]

    # ---------------------------------------------------------------------------
    # PATTERN RECOGNITION
    # ---------------------------------------------------------------------------

    # Morning patterns
    if session == 'morning':
        # Morning sweep detection
        if detect_morning_sweep(close, current_bar):
            # If price swept up early, bet on reversal (down)
            if current_price > vwap_level:
                return -1  # Call credit spread
            # If price swept down early, bet on reversal (up)
            elif current_price < vwap_level:
                return 1  # Put credit spread

    # Afternoon patterns
    elif session == 'afternoon':
        # Detect drift direction
        drift = detect_afternoon_drift(close, volume, current_bar)

        if drift == 'up':
            # Price drifting up, bet on continuation or flat
            if current_price < vwap_level:
                return 1  # Put credit spread (catch up to VWAP)
        elif drift == 'down':
            # Price drifting down, bet on continuation or flat
            if current_price > vwap_level:
                return -1  # Call credit spread

    # Late session patterns
    elif session == 'late':
        # After 2:30, more conservative
        # Look for range-bound behavior
        support, resistance = detect_support_resistance(close, high, low, current_bar)

        if support and resistance:
            range_width = (resistance - support) / support

            # If range is tight (<0.5%), bet on flat
            if range_width < 0.005:
                if current_price > (support + resistance) / 2:
                    return -1  # Call credit spread (in upper half)
                else:
                    return 1  # Put credit spread (in lower half)

    # ---------------------------------------------------------------------------
    # VWAP AND RSI FILTERS
    # ---------------------------------------------------------------------------

    # RSI filter - avoid overextended
    if rsi[current_bar] > 70:
        return -1  # Overbought, call credit spread

    if rsi[current_bar] < 30:
        return 1  # Oversold, put credit spread

    # VWAP relative positioning
    if current_price > vwap_level * 1.002:  # 0.2% above VWAP
        # Price extended above VWAP
        if rsi[current_bar] > 60:
            return -1  # Call credit spread (expect pullback)

    elif current_price < vwap_level * 0.998:  # 0.2% below VWAP
        # Price extended below VWAP
        if rsi[current_bar] < 40:
            return 1  # Put credit spread (expect bounce)

    # Default: no trade if no clear signal
    return 0


def create_strategy_wrapper():
    """
    Create a wrapper function that maintains state between calls.
    """
    current_position = 0
    last_signal = 0

    def wrapper(data: MarketData, current_bar: int) -> int:
        nonlocal current_position, last_signal

        # Get new signal from strategy
        signal = strategy_func(data, current_bar)

        # Prevent rapid signal changes
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

def main():
    print(f"Running strategy: {STRATEGY_NAME}")
    print(f"Data file: {DATA_FILE}")
    print(f"Initial capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"Entry window: {ENTRY_TIME_START} - {ENTRY_TIME_END}")
    print(f"Market close: {MARKET_CLOSE}")
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
