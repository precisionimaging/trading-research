"""
Generate synthetic market data for testing the trading research framework.

This creates realistic-looking OHLCV data with trends, volatility, and noise.
Perfect for testing the framework without fetching real data first.

Usage:
    python generate_test_data.py --ticker TEST --bars 2520 --output TEST_data
"""

import os
import sys
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Cache directory
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "trading-research")
DATA_DIR = os.path.join(CACHE_DIR, "data")


def generate_synthetic_ohlcv(
    n_bars: int = 2520,
    starting_price: float = 100.0,
    trend_strength: float = 0.0002,  # Daily drift
    volatility: float = 0.015,  # Daily volatility
    trend_change_prob: float = 0.005,  # Probability of trend change
    seed: int = 42
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data with realistic characteristics.

    Args:
        n_bars: Number of bars (2520 = ~10 trading years)
        starting_price: Starting price
        trend_strength: Daily price drift (positive = uptrend)
        volatility: Daily price volatility
        trend_change_prob: Probability of trend reversal
        seed: Random seed

    Returns:
        DataFrame with OHLCV data and datetime index
    """
    np.random.seed(seed)

    # Generate daily returns with trend and noise
    returns = np.random.normal(trend_strength, volatility, n_bars)

    # Add occasional trend changes (regime shifts)
    for i in range(1, n_bars):
        if np.random.random() < trend_change_prob:
            trend_strength *= -1  # Reverse trend
            # Add some volatility during regime change
            returns[i] += np.random.normal(0, volatility * 2)

    # Generate price series
    prices = starting_price * (1 + np.cumsum(returns))

    # Generate OHLC from close prices
    high = prices * (1 + np.random.uniform(0, 0.01, n_bars))
    low = prices * (1 - np.random.uniform(0, 0.01, n_bars))
    open_ = np.concatenate([[starting_price], prices[:-1]])

    # Generate volume (random with some correlation to price moves)
    volume = np.random.lognormal(10, 0.5, n_bars)
    # Increase volume on large price moves
    volume *= (1 + np.abs(returns) * 10)

    # Create DataFrame with trading days
    start_date = datetime(2014, 1, 2)  # Start on a Thursday
    dates = pd.date_range(start_date, periods=n_bars, freq='B')  # Business days

    df = pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': prices,
        'volume': volume,
    }, index=dates)

    return df


def save_test_data(df: pd.DataFrame, ticker: str, output_filename: str):
    """Save test data to cache."""
    import pickle

    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Save as CSV (for TradingView compatibility testing)
    csv_path = os.path.join(DATA_DIR, f"{output_filename}.csv")
    df.to_csv(csv_path)
    print(f"Saved CSV to {csv_path}")

    # Save as pickled MarketData (for prepare.py compatibility)
    from prepare import MarketData
    data = MarketData.from_dataframe(df, ticker)
    pkl_path = os.path.join(DATA_DIR, f"{output_filename}.pkl")
    with open(pkl_path, 'wb') as f:
        pickle.dump(data, f)
    print(f"Saved MarketData to {pkl_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic test data")
    parser.add_argument('--ticker', type=str, default='TEST',
                        help='Ticker symbol for the data')
    parser.add_argument('--bars', type=int, default=2520,
                        help='Number of bars (2520 = ~10 years of daily data)')
    parser.add_argument('--output', type=str, default='TEST_data',
                        help='Output filename (without extension)')
    parser.add_argument('--starting-price', type=float, default=100.0,
                        help='Starting price')
    parser.add_argument('--trend', type=float, default=0.0002,
                        help='Trend strength (positive = uptrend)')
    parser.add_argument('--volatility', type=float, default=0.015,
                        help='Daily volatility (1.5% = typical)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed')

    args = parser.parse_args()

    print(f"Generating {args.bars} bars of synthetic data for {args.ticker}...")
    print(f"Trend: {args.trend:.6f}, Volatility: {args.volatility:.3f}")

    # Generate data
    df = generate_synthetic_ohlcv(
        n_bars=args.bars,
        starting_price=args.starting_price,
        trend_strength=args.trend,
        volatility=args.volatility,
        seed=args.seed
    )

    # Print statistics
    print("\nData statistics:")
    print(df.describe())
    print(f"\nDate range: {df.index[0]} to {df.index[-1]}")
    print(f"Total return: {(df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100:.2f}%")

    # Save data
    save_test_data(df, args.ticker, args.output)

    print("\nNow you can run the baseline strategy:")
    print(f"  1. Edit strategy.py: DATA_FILE = '{args.output}'")
    print("  2. Run: uv run strategy.py")

    return 0


if __name__ == '__main__':
    sys.exit(main())
