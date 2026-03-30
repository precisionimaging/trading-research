"""
Data fetching and backtesting engine for trading strategy research.
Supports TradingView data export and Interactive Brokers API.

Usage:
    # TradingView (CSV export)
    python prepare.py --source tradingview --data SPY_data.csv

    # IBKR (live account, default port 7497)
    python prepare.py --source ibkr --ticker AAPL --period 1y

    # IBKR (paper trading, port 7498)
    python prepare.py --source ibkr --ticker SPY --period 5y --port 7498

    # IBKR with custom settings
    python prepare.py --source ibkr --ticker GLD --period 2y --bar-size "1 hour" --port 7498

Data is stored in ~/.cache/trading-research/
"""

import os
import sys
import time
import argparse
import pickle
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Constants (fixed, do not modify)
# ----------------------------------------------------------------------------

TIME_BUDGET = 30  # backtest time budget in seconds (for strategy optimization)

# Default evaluation metrics
METRICS = {
    'total_return': 1.0,     # higher is better
    'sharpe_ratio': 1.0,    # higher is better
    'max_drawdown': -1.0,   # lower is better (negated for maximization)
    'profit_factor': 1.0,   # higher is better
    'win_rate': 0.5,        # minimum acceptable
}

# Risk constraints
MAX_POSITION_SIZE = 1.0    # max position as fraction of portfolio
MIN_TRADE_GAP = 1           # minimum bars between trades
COMMISSION = 0.001         # 0.1% per trade
SLIPPAGE = 0.0005          # 0.05% slippage per trade

# ---------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "trading-research")
DATA_DIR = os.path.join(CACHE_DIR, "data")

# ---------------------------------------------------------------------------
# Data Fetching
# ----------------------------------------------------------------------------

@dataclass
class MarketData:
    """OHLCV market data with datetime index."""
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    datetime: np.ndarray
    ticker: str

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame."""
        return pd.DataFrame({
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
        }, index=pd.to_datetime(self.datetime))

    @staticmethod
    def from_dataframe(df: pd.DataFrame, ticker: str) -> 'MarketData':
        """Create from pandas DataFrame."""
        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        # Ensure required columns exist
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                # Try alternative capitalizations
                alt_col = col.capitalize()
                if alt_col in df.columns:
                    df.rename(columns={alt_col: col}, inplace=True)
                else:
                    raise ValueError(f"Missing required column: {col}")

        return MarketData(
            open=df['open'].values,
            high=df['high'].values,
            low=df['low'].values,
            close=df['close'].values,
            volume=df['volume'].values,
            datetime=df.index.astype(np.int64) // 10**9,  # Unix timestamp
            ticker=ticker,
        )


def fetch_tradingview_data(csv_path: str, ticker: str) -> MarketData:
    """
    Load data from TradingView export (CSV format).

    Expected columns: time, open, high, low, close, volume
    """
    df = pd.read_csv(csv_path)

    # TradingView exports have 'time' column, rename to datetime
    if 'time' in df.columns:
        df.rename(columns={'time': 'datetime'}, inplace=True)
        df.set_index('datetime', inplace=True)

    data = MarketData.from_dataframe(df, ticker)
    print(f"Loaded {len(data.close)} bars of {ticker} data from TradingView")
    return data


def fetch_ibkr_data(ticker: str, period: str = '1y', bar_size: str = '1 day',
                    host: str = '127.0.0.1', port: int = 7497,
                    client_id: int = 1) -> MarketData:
    """
    Fetch data from Interactive Brokers using ib_insync.

    Requires:
    - IB Gateway or TWS running
    - API enabled in IB Gateway/TWS (Configure → API → Settings)
    - Active connection to IBKR account (paper trading recommended for testing)

    Args:
        ticker: Stock/ETF ticker (e.g., 'AAPL', 'SPY', 'GLD')
        period: Time period ('1d', '1w', '1m', '1y', '2y', '5y')
        bar_size: Bar size ('1 min', '5 mins', '15 mins', '1 hour', '1 day')
        host: IB Gateway/TWS host (default localhost)
        port: IB Gateway/TWS port (7497 for live, 7498 for paper trading)
        client_id: Unique client ID (1-9999)

    Returns:
        MarketData object with OHLCV data

    Raises:
        ConnectionError: If cannot connect to IB Gateway/TWS
        ValueError: If invalid ticker or parameters
    """
    try:
        from ib_insync import IB, Stock, util
    except ImportError:
        raise ImportError(
            "ib_insync not installed. Install with: uv pip install ib-insync\n"
            "Or add to pyproject.toml dependencies."
        )

    print(f"Connecting to IBKR at {host}:{port}...")
    print(f"Fetching {ticker} data (period: {period}, bar size: {bar_size})...")

    # Create IB instance and connect
    ib = IB()
    try:
        ib.connect(host, port, clientId=client_id)
        if not ib.isConnected():
            raise ConnectionError(f"Failed to connect to IBKR at {host}:{port}")

        print(f"Connected! Client ID: {client_id}")

    except Exception as e:
        raise ConnectionError(
            f"Cannot connect to IBKR. Please ensure:\n"
            f"  1. IB Gateway or TWS is running\n"
            f"  2. API is enabled in Configure → API → Settings\n"
            f"  3. Socket clients are allowed on port {port}\n\n"
            f"Error: {e}"
        )

    # Map period to IBKR format
    duration_map = {
        '1d': '1 D',
        '1w': '1 W',
        '1m': '1 M',
        '2m': '2 M',
        '3m': '3 M',
        '6m': '6 M',
        '1y': '1 Y',
        '2y': '2 Y',
        '5y': '5 Y',
        '10y': '10 Y',
    }

    if period not in duration_map:
        raise ValueError(
            f"Invalid period: {period}. Use one of: {', '.join(duration_map.keys())}"
        )

    # Define stock contract
    try:
        contract = Stock(ticker, 'SMART', 'USD')
        ib.qualifyContracts(contract)
        print(f"Contract qualified: {contract}")
    except Exception as e:
        raise ValueError(f"Invalid ticker '{ticker}': {e}")

    # Request historical data
    try:
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',  # Current time
            durationStr=duration_map[period],
            barSizeSetting=bar_size,
            whatToShow='TRADES',  # Use MIDPOINT for forex, TRADES for stocks
            useRTH=True,  # Regular trading hours only
            formatDate=1,  # Format as datetime string
        )

        print(f"Received {len(bars)} bars from IBKR")

    except Exception as e:
        ib.disconnect()
        raise RuntimeError(f"Failed to fetch historical data from IBKR: {e}")

    # Convert to DataFrame
    if not bars:
        ib.disconnect()
        raise ValueError(f"No data received for {ticker}")

    try:
        # Create DataFrame with proper datetime index
        df = pd.DataFrame({
            'open': [b.open for b in bars],
            'high': [b.high for b in bars],
            'low': [b.low for b in bars],
            'close': [b.close for b in bars],
            'volume': [b.volume for b in bars],
        }, index=[b.date for b in bars])

        # Ensure index is datetime
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        print(f"Date range: {df.index[0]} to {df.index[-1]}")
        print(f"Total bars: {len(df)}")

    except Exception as e:
        ib.disconnect()
        raise RuntimeError(f"Failed to convert bars to DataFrame: {e}")

    # Disconnect
    ib.disconnect()
    print("Disconnected from IBKR")

    # Convert to MarketData
    return MarketData.from_dataframe(df, ticker)


def save_market_data(data: MarketData, filename: str):
    """Save market data to cache."""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, f"{filename}.pkl")
    with open(filepath, 'wb') as f:
        pickle.dump(data, f)
    print(f"Saved market data to {filepath}")


def load_market_data(filename: str) -> MarketData:
    """Load market data from cache."""
    filepath = os.path.join(DATA_DIR, f"{filename}.pkl")
    with open(filepath, 'rb') as f:
        data = pickle.load(f)
    print(f"Loaded market data from {filepath}")
    return data

# ---------------------------------------------------------------------------
# Backtesting Engine
# ----------------------------------------------------------------------------

@dataclass
class Trade:
    """Individual trade record."""
    entry_bar: int
    exit_bar: int
    entry_price: float
    exit_price: float
    position: float  # positive for long, negative for short
    pnl: float
    pnl_pct: float
    holding_bars: int


@dataclass
class BacktestResult:
    """Results from backtesting a strategy."""
    trades: List[Trade]
    equity_curve: np.ndarray
    returns: np.ndarray
    metrics: Dict[str, float]

    def summary(self) -> str:
        """Return formatted summary of results."""
        lines = ["---"]
        lines.append(f"total_return:    {self.metrics.get('total_return', 0):.4f}")
        lines.append(f"sharpe_ratio:    {self.metrics.get('sharpe_ratio', 0):.4f}")
        lines.append(f"max_drawdown:    {self.metrics.get('max_drawdown', 0):.4f}")
        lines.append(f"profit_factor:   {self.metrics.get('profit_factor', 0):.4f}")
        lines.append(f"win_rate:        {self.metrics.get('win_rate', 0):.4f}")
        lines.append(f"num_trades:      {len(self.trades)}")
        lines.append(f"avg_holding_bars: {np.mean([t.holding_bars for t in self.trades]) if self.trades else 0:.1f}")
        lines.append(f"total_bars:      {len(self.equity_curve)}")
        return "\n".join(lines)


def backtest(data: MarketData, strategy_func, initial_capital: float = 100000.0) -> BacktestResult:
    """
    Run backtest with a given strategy function.

    Strategy function signature:
        strategy_func(data: MarketData, current_bar: int) -> int
        Returns: position (-1 for short, 0 for flat, 1 for long)

    Args:
        data: OHLCV market data
        strategy_func: Function that generates trading signals
        initial_capital: Starting capital for backtest

    Returns:
        BacktestResult with trades and metrics
    """
    n_bars = len(data.close)

    # Track state
    equity = np.full(n_bars, initial_capital)
    position = 0.0
    entry_price = 0.0
    entry_bar = -1
    trades = []

    for bar in range(1, n_bars):
        # Get signal from strategy (look back at bar-1 to avoid lookahead bias)
        signal = strategy_func(data, bar - 1)

        # Apply transaction costs
        open_price = data.open[bar]
        if position != 0.0 and signal != position:
            # Exit trade
            exit_price = open_price * (1 - SLIPPAGE * np.sign(position))
            commission = abs(position) * initial_capital * COMMISSION

            if position > 0:  # Long exit
                pnl = (exit_price - entry_price) / entry_price * abs(position) * initial_capital - commission
            else:  # Short exit
                pnl = (entry_price - exit_price) / entry_price * abs(position) * initial_capital - commission

            pnl_pct = pnl / (abs(position) * initial_capital)

            trades.append(Trade(
                entry_bar=entry_bar,
                exit_bar=bar,
                entry_price=entry_price,
                exit_price=exit_price,
                position=position,
                pnl=pnl,
                pnl_pct=pnl_pct,
                holding_bars=bar - entry_bar,
            ))

            equity[bar] = equity[bar - 1] + pnl
            position = 0.0
            entry_bar = -1

        # Enter new position
        if position == 0.0 and signal != 0.0:
            entry_price = open_price * (1 + SLIPPAGE * np.sign(signal))
            entry_bar = bar
            position = signal * MAX_POSITION_SIZE
            equity[bar] = equity[bar - 1]  # No change on entry

        # Update equity for existing position (mark-to-market)
        elif position != 0.0:
            close_price = data.close[bar]
            if position > 0:  # Long
                equity[bar] = equity[bar - 1] * (close_price / data.close[bar - 1])
            else:  # Short
                equity[bar] = equity[bar - 1] * (data.close[bar - 1] / close_price)
        else:
            equity[bar] = equity[bar - 1]

    # Close any remaining position at last bar
    if position != 0.0 and entry_bar >= 0:
        exit_price = data.close[-1]
        commission = abs(position) * initial_capital * COMMISSION

        if position > 0:
            pnl = (exit_price - entry_price) / entry_price * abs(position) * initial_capital - commission
        else:
            pnl = (entry_price - exit_price) / entry_price * abs(position) * initial_capital - commission

        pnl_pct = pnl / (abs(position) * initial_capital)

        trades.append(Trade(
            entry_bar=entry_bar,
            exit_bar=n_bars - 1,
            entry_price=entry_price,
            exit_price=exit_price,
            position=position,
            pnl=pnl,
            pnl_pct=pnl_pct,
            holding_bars=n_bars - 1 - entry_bar,
        ))

        equity[-1] = equity[-2] + pnl

    # Calculate returns
    returns = np.diff(np.log(equity[equity > 0]))
    returns = returns[np.isfinite(returns)]

    # Calculate metrics
    metrics = calculate_metrics(equity, returns, trades)

    return BacktestResult(
        trades=trades,
        equity_curve=equity,
        returns=returns,
        metrics=metrics,
    )


def calculate_metrics(equity: np.ndarray, returns: np.ndarray, trades: List[Trade]) -> Dict[str, float]:
    """Calculate trading performance metrics."""
    if len(returns) == 0:
        return {
            'total_return': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'profit_factor': 0.0,
            'win_rate': 0.0,
        }

    # Total return
    total_return = equity[-1] / equity[0] - 1

    # Sharpe ratio (annualized)
    if len(returns) > 1:
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)
    else:
        sharpe_ratio = 0.0

    # Maximum drawdown
    equity_series = pd.Series(equity)
    running_max = equity_series.expanding().max()
    drawdown = (equity_series - running_max) / running_max
    max_drawdown = drawdown.min()

    # Win rate and profit factor
    if trades:
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl <= 0]

        win_rate = len(winning_trades) / len(trades)

        total_profit = sum(t.pnl for t in winning_trades)
        total_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    else:
        win_rate = 0.0
        profit_factor = 0.0

    return {
        'total_return': total_return,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'profit_factor': profit_factor,
        'win_rate': win_rate,
    }


def evaluate_strategy(data: MarketData, strategy_func, initial_capital: float = 100000.0) -> BacktestResult:
    """
    Main evaluation function (analogous to evaluate_bpb in autoresearch).
    This is the ground truth metric for strategy performance.

    Returns BacktestResult with full metrics.
    """
    result = backtest(data, strategy_func, initial_capital)
    return result

# ---------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Prepare data for trading strategy research")
    parser.add_argument('--source', choices=['tradingview', 'ibkr'], required=True,
                        help='Data source')
    parser.add_argument('--ticker', type=str, help='Ticker symbol (for IBKR)')
    parser.add_argument('--data', type=str, help='CSV file path (for TradingView)')
    parser.add_argument('--period', type=str, default='1y',
                        help='Time period: 1d, 1w, 1m, 1y, 2y, 5y (for IBKR)')
    parser.add_argument('--bar-size', type=str, default='1 day',
                        help='Bar size: 1 min, 5 mins, 1 hour, 1 day (for IBKR)')
    parser.add_argument('--host', type=str, default='127.0.0.1',
                        help='IB Gateway/TWS host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=7497,
                        help='IB Gateway/TWS port (default: 7497 live, 7498 paper)')
    parser.add_argument('--client-id', type=int, default=1,
                        help='Unique client ID (default: 1)')
    parser.add_argument('--output', type=str, help='Output filename for cached data')

    args = parser.parse_args()

    if args.source == 'tradingview':
        if not args.data:
            print("Error: --data required for TradingView source")
            return 1

        ticker = args.ticker or os.path.splitext(os.path.basename(args.data))[0]
        data = fetch_tradingview_data(args.data, ticker)

    elif args.source == 'ibkr':
        if not args.ticker:
            print("Error: --ticker required for IBKR source")
            return 1

        data = fetch_ibkr_data(
            ticker=args.ticker,
            period=args.period,
            bar_size=args.bar_size,
            host=args.host,
            port=args.port,
            client_id=args.client_id,
        )

    else:
        print(f"Error: Unknown source {args.source}")
        return 1

    # Save to cache
    output_filename = args.output or f"{data.ticker}_data"
    save_market_data(data, output_filename)

    # Print summary
    df = data.to_dataframe()
    print("\nData summary:")
    print(df.describe())
    print(f"\nDate range: {df.index[0]} to {df.index[-1]}")
    print(f"Total bars: {len(df)}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
