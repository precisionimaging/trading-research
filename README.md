# trading-research

Autonomous trading strategy research. AI agents iteratively modify trading strategies, backtest them on historical data, and keep or discard changes based on performance metrics.

## Overview

**Inspired by:** [karpathy/autoresearch](https://github.com/karpathy/autoresearch) but adapted for trading strategy discovery instead of neural network architecture.

**The idea:** Give an AI agent a backtesting engine and historical market data. Let it experiment with trading strategies overnight. The agent modifies strategy logic, runs backtests, checks if performance improved, keeps or discards, and repeats. You wake up to a log of experiments and (hopefully) profitable strategies.

## How it works

The repo has three files that matter:

- **`prepare.py`** — data fetching (TradingView/IBKR), backtest engine, performance evaluation. Read-only, do not modify.
- **`strategy.py`** — the single file the agent edits. Contains technical indicators, entry/exit logic, risk management. Everything is fair game. **This file is edited and iterated on by the agent**.
- **`program.md`** — baseline instructions for one agent. Point your agent here and let it go. **This file is edited and iterated on by the human**.

## Key Differences from autoresearch

| autoresearch | trading-research |
|-------------|-----------------|
| LLM pretraining | Trading strategy discovery |
| 5-minute GPU training budget | Seconds-to-minutes CPU backtest |
| Metric: val_bpb (lower is better) | Metrics: sharpe, return, drawdown (higher is better) |
| Neural architecture optimization | Trading logic optimization |
| NVIDIA GPU required | Works on any machine (Mac Mini, etc.) |
| Fixed 5-minute time budget | Flexible (backtests complete quickly) |

## Quick Start

**Requirements:** Python 3.10+, [uv](https://docs.astral.sh/uv/), historical market data.

### 1. Install dependencies

```bash
# Install uv project manager (if you don't already have it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

### 2. Get historical data

**Option A: TradingView (easiest)**
1. Go to TradingView.com
2. Select your ticker (e.g., SPY, AAPL)
3. Click "Download" to export CSV
4. Run: `uv run prepare.py --source tradingview --data SPY_data.csv --ticker SPY`

**Option B: Interactive Brokers**
```bash
uv run prepare.py --source ibkr --ticker AAPL --period 1y
```
Note: Requires IBKR API integration (placeholder implementation).

### 3. Manually run a single backtest

```bash
uv run strategy.py
```

Expected output:
```
---
total_return:    0.2345
sharpe_ratio:    1.2345
max_drawdown:    -0.1234
profit_factor:   1.5678
win_rate:        0.4500
num_trades:      125
```

If this works, your setup is ready for autonomous research.

## Running the Agent

Spin up your Claude, Codex, or other LLM agent in this repo, then prompt:

```
Hi have a look at program.md and let's kick off a new experiment! Let's do the setup first.
```

The `program.md` file is essentially a "skill" for the agent to autonomously research trading strategies.

## Project Structure

```
prepare.py      — data fetching, backtest engine, evaluation (do not modify)
strategy.py     — strategy logic, indicators, signals (agent modifies this)
program.md      — agent instructions
pyproject.toml  — dependencies
```

## Performance Metrics

The backtest engine calculates multiple metrics:

- **Total return**: Overall profit/loss percentage
- **Sharpe ratio**: Risk-adjusted returns (higher is better, >1 is good)
- **Max drawdown**: Largest peak-to-trough decline (lower is better, <20% is good)
- **Profit factor**: Gross profit / gross loss (>1.5 is good)
- **Win rate**: Percentage of winning trades (40-60% is often acceptable)

The agent optimizes for a composite score, primarily weighted toward Sharpe ratio and total return.

## Strategy Example

The baseline strategy in `strategy.py` combines:

- Trend: SMA crossover (10-day vs 30-day)
- Momentum: RSI (14-day)
- Momentum: MACD (12, 26, 9)
- Volatility: Bollinger Bands (20-day, 2 std dev)

Entry conditions (all must be true):
- Fast SMA > Slow SMA (uptrend)
- RSI < 70 (not overbought)
- MACD histogram rising
- Price above BB middle

This is just a starting point. The agent will experiment with:
- Different indicator combinations
- Parameter optimization
- Adding filters (volatility, trend, time)
- Risk management rules
- Entry/exit logic

## Data Sources

### TradingView (Recommended)
- Free
- Easy export to CSV
- Wide range of tickers (stocks, ETFs, crypto, forex)
- Multiple timeframes (1 day, 1 hour, 5 min, etc.)

### Interactive Brokers
- Professional data quality
- Real-time and historical data
- Requires API setup with IB Gateway or TWS
- Note: Placeholder implementation, requires integration work

## Hardware Requirements

Unlike autoresearch, this runs on CPU only. Perfect for Mac Mini M4:

- **CPU**: Any modern CPU works
- **RAM**: 16GB is plenty
- **Storage**: Minimal (<100MB for data)
- **GPU**: Not required

Backtests complete in seconds, not minutes.

## Platform Support

- **macOS** (Intel and Apple Silicon M1/M2/M3/M4) - Fully supported
- **Linux** - Fully supported
- **Windows** - Fully supported

## Design Choices

**Single file to modify.** The agent only touches `strategy.py`. Keeps scope manageable and diffs reviewable.

**Backtest speed.** CPU-based backtesting completes in seconds to minutes. Enables rapid iteration (100+ experiments/hour).

**Simplicity.** No complex ML training, no GPUs, no distributed computing. Just strategy logic + historical data.

**Risk-aware.** Transaction costs, slippage, and risk management built-in. Strategies must be robust to real-world friction.

**Overfitting prevention.** Walk-forward analysis recommended (test on out-of-sample data). Avoid curve-fitting.

## Gotchas and Warnings

**Historical performance ≠ future results.** Past performance does not guarantee future success. Always paper trade before live trading.

**Overfitting.** Strategies optimized too heavily on historical data often fail. Look for robust, generalizable patterns.

**Transaction costs.** Every trade costs money (commission + slippage). High-frequency strategies may not be profitable after costs.

**Market regimes.** Strategies that worked in 2023 may not work in 2025. Markets change.

**Live vs backtest.** Real trading has psychological pressure, slippage, order execution issues, and regime shifts that backtests don't capture.

**No guarantees.** This is a research tool. It helps discover potential strategies, but does not guarantee profitability.

## Future Enhancements

Potential improvements for future versions:

- **Walk-forward analysis**: Automatic out-of-sample testing
- **Multiple timeframes**: Daily + intraday signals
- **Portfolio management**: Multi-asset strategies
- **Machine learning**: RL or ML-based strategies
- **Live trading integration**: IBKR API execution
- **Telegram alerts**: Real-time strategy signals
- **Visualization**: Equity curves, trade charts

## Notable Inspirations

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) - Autonomous ML research
- [VectorBT](https://github.com/polakowo/vectorbt) - Fast backtesting library
- [Backtrader](https://github.com/mementum/backtrader) - Python trading framework
- [QuantConnect](https://www.quantconnect.com/) - Cloud backtesting platform

## License

MIT

## Disclaimer

This software is for educational and research purposes only. Trading involves substantial risk of loss. Past performance does not guarantee future results. The authors are not responsible for any financial losses incurred while using this software. Always do your own research and consult with financial professionals before trading.
