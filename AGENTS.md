# trading-research - Agent Guide

This repository implements autonomous trading strategy research where agents iteratively modify trading logic, backtest on historical data, and keep or discard changes based on performance metrics.

## Project Overview

**Purpose:** Autonomous trading strategy discovery - agents experiment with technical indicators, entry/exit logic, and risk management to maximize strategy performance (Sharpe ratio, total return, minimal drawdown).

**Key Concept:** You (the agent) are the quantitative researcher. The human only edits the `program.md` instructions. You modify `strategy.py`, run backtests, and autonomously decide what to keep or discard.

**The Experiment Loop:**
1. Modify `strategy.py` with an experimental change
2. Run backtest: `uv run strategy.py > run.log 2>&1`
3. Extract performance metrics from log
4. If composite score improves (higher), keep the change and advance the branch
5. If score worsens or stays same, git reset back to previous commit
6. Repeat indefinitely until human stops you

## Essential Commands

### Setup (one-time)
```bash
# Install dependencies
uv sync

# Fetch historical data (TradingView example)
# First, export data from TradingView.com as CSV, then:
uv run prepare.py --source tradingview --data SPY_data.csv --ticker SPY

# Or use IBKR (paper trading recommended for testing)
# Requires IB Gateway/TWS running with API enabled
uv run prepare.py --source ibkr --ticker AAPL --period 1y --port 7498

# IBKR live trading (careful with real money!)
uv run prepare.py --source ibkr --ticker SPY --period 5y --port 7497
```

### Running Experiments
```bash
# Single backtest run (typically seconds to minutes)
uv run strategy.py > run.log 2>&1

# Extract results from log
grep "^total_return:\|^sharpe_ratio:\|^max_drawdown:\|^profit_factor:\|^win_rate:\|^num_trades:" run.log
```

### Git Workflow
```bash
# Create a new experiment branch (e.g., research/mar28)
git checkout -b research/<tag>

# Commit your change to strategy.py
git commit -am "experiment description"

# If score improved (higher), commit stays, branch advances
# If score worsened or stayed same, reset back:
git reset --hard HEAD~1

# Check current state
git status
git log --oneline -3
```

### Data Location
- Cached market data: `~/.cache/trading-research/`
- Verify data exists before starting experiments

### IBKR Setup (Interactive Brokers)

**Prerequisites:**
1. Active IBKR account (live or paper trading)
2. IB Gateway or TWS installed and running
3. API enabled in Configure → API → Settings

**Setup Steps:**

1. **Install IB Gateway or TWS:**
   - Download: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
   - Login with your IBKR account

2. **Enable API:**
   - In TWS/IB Gateway: Configure → API → Settings
   - Check "Enable ActiveX and Socket Clients"
   - Set "Socket port" (default: 7497 live, 7498 paper)
   - Check "Allow connections from localhost" (or add your IP)
   - For safety, enable "Read-Only API" initially

3. **Test Connection:**
   ```bash
   # Paper trading (recommended for testing)
   uv run prepare.py --source ibkr --ticker SPY --period 1y --port 7498

   # Live trading (use with caution)
   uv run prepare.py --source ibkr --ticker SPY --period 1y --port 7497
   ```

**IBKR CLI Parameters:**
- `--ticker`: Stock/ETF symbol (e.g., SPY, AAPL, GLD)
- `--period`: Time period (1d, 1w, 1m, 1y, 2y, 5y)
- `--bar-size`: Bar size (1 min, 5 mins, 1 hour, 1 day)
- `--port`: IB Gateway port (7497 live, 7498 paper)
- `--host`: IB Gateway host (default: 127.0.0.1)
- `--client-id`: Unique client ID (default: 1)

**Troubleshooting:**
- "Cannot connect to IBKR": Ensure TWS/IB Gateway is running and API is enabled
- "Invalid ticker": Check ticker symbol, use uppercase (e.g., SPY not spy)
- "No data received": Check ticker is valid and has data for requested period
- Rate limits: IBKR limits data requests; use cached data when possible

**Recommendations:**
- Use paper trading account for all development
- Start with shorter periods (1y) during testing
- Cache data locally to avoid repeated API calls
- Never leave API enabled unattended with live trading

## Code Organization

### File Scope (Critical)

**Files you CAN edit:**
- `strategy.py` - **ONLY** file you modify. Contains technical indicators, entry/exit logic, risk management. Everything here is fair game.

**Files you CANNOT edit (read-only):**
- `prepare.py` - Data fetching, backtest engine, transaction costs, evaluation metrics. Do not modify.
- `program.md` - Agent instructions (edited by human, not you)
- `pyproject.toml` - Dependencies (cannot add new packages)

### Key Constants in prepare.py (Fixed, Do Not Change)
```python
TIME_BUDGET = 30            # not enforced, just for reference
MAX_POSITION_SIZE = 1.0    # max position as fraction of portfolio
COMMISSION = 0.001          # 0.1% per trade
SLIPPAGE = 0.0005          # 0.05% slippage per trade
```

### strategy.py Structure

**Configuration section (lines ~17-30):** Direct edits here for quick experiments
```python
# Data file to use (must be in cache)
DATA_FILE = "SPY_data"

# Strategy name (for logging)
STRATEGY_NAME = "baseline_rsi_macd"

# Capital allocation
INITIAL_CAPITAL = 100000.0

# Lookback period
LOOKBACK = 20

# Risk management
RISK_PER_TRADE = 0.02
MAX_DAILY_LOSS = 0.05
```

**Technical indicators (lines ~50-150):**
- `calculate_sma()` - Simple Moving Average
- `calculate_ema()` - Exponential Moving Average
- `calculate_rsi()` - Relative Strength Index
- `calculate_macd()` - MACD indicator
- `calculate_bollinger_bands()` - Bollinger Bands
- `calculate_atr()` - Average True Range

**Main strategy function (lines ~170-240):**
```python
def strategy_func(data: MarketData, current_bar: int) -> int:
    """
    Trading strategy function.

    Returns:
        Position signal: -1 (short), 0 (flat), 1 (long)
    """
```

This is where you implement your trading logic. The function:
1. Calculates indicators using historical data
2. Evaluates entry/exit conditions
3. Returns a position signal

## Naming Conventions and Style

### Python Style
- Use `snake_case` for functions and variables
- Use `PascalCase` for classes
- Constants in `SCREAMING_SNAKE_CASE` (at module level)
- Type hints used sparingly

### Variable Naming Patterns
- `sma_*`, `ema_*` for moving averages
- `rsi_*` for RSI-related
- `macd_*`, `bb_*`, `atr_*` for other indicators
- `long_conditions`, `short_conditions` for entry logic
- `signal` for final position output (-1, 0, 1)

### Strategy Logic Patterns
```python
# Typical structure
1. Extract price series up to current_bar
2. Calculate indicators
3. Define entry conditions (list of booleans)
4. Define exit conditions (if separate)
5. Apply logic to generate signal
6. Return signal
```

## Testing and Evaluation

### Performance Metrics (from prepare.py)

**Primary metrics (higher is better):**
- `total_return`: Overall profit/loss percentage
- `sharpe_ratio`: Risk-adjusted returns (annualized)
- `profit_factor`: Gross profit / gross loss
- `win_rate`: Percentage of winning trades

**Risk metrics (lower is better):**
- `max_drawdown`: Largest peak-to-trough decline

**Output format:**
```
---
total_return:    0.2345
sharpe_ratio:    1.2345
max_drawdown:    -0.1234
profit_factor:   1.5678
win_rate:        0.4500
num_trades:      125
avg_holding_bars: 12.5
total_bars:      2520
```

### Extracting Results
```bash
grep "^total_return:\|^sharpe_ratio:\|^max_drawdown:\|^profit_factor:\|^win_rate:\|^num_trades:" run.log
```

If output is empty, check crash with:
```bash
tail -n 50 run.log
```

### Composite Score Calculation

Prioritize metrics when evaluating strategies:

```python
# Recommended weighting
score = (
    0.4 * normalized_sharpe +      # Risk-adjusted returns (most important)
    0.3 * normalized_total_return + # Absolute performance
    0.1 * normalized_profit_factor +  # Edge quality
    -0.2 * normalized_drawdown      # Risk control (negative)
)
```

**Normalization:** Scale each metric to [0, 1] across your experiments.

**Decision rule:** Keep if score improves (higher). Discard if score decreases or stays same.

### Results Logging (TSV Format)

Create `results.tsv` (tab-separated, NOT comma-separated):
```
commit	score	metric_1	metric_2	status	description
a1b2c3d	0.8234	1.2345	-0.1234	keep	baseline RSI+MACD strategy
b2c3d4e	0.8512	1.4567	-0.0987	keep	add Bollinger Band filter
c3d4e5f	0.7890	1.1234	-0.1567	discard	increase RSI period to 21
d4e5f6g	0.0000	0.0	0.0	crash	moving average calculation error
```

Columns:
1. `commit` - git hash (short, 7 chars)
2. `score` - composite performance score (0.0000 for crashes)
3. `metric_1` - primary metric (e.g., sharpe_ratio)
4. `metric_2` - secondary metric (e.g., max_drawdown)
5. `status` - `keep`, `discard`, or `crash`
6. `description` - short text of what was tried

**Important:** `results.tsv` should NOT be committed to git.

## Important Gotchas and Patterns

### Lookahead Bias
**CRITICAL:** Never use future data in your calculations. The strategy function receives `data[:current_bar+1]` - you can use data up to and including `current_bar` when making decisions for the *next* bar.

**Correct:**
```python
close = data.close[:current_bar+1]  # Data up to current bar
sma = calculate_sma(close, 20)
# Use sma[current_bar] for decision
```

**Incorrect:**
```python
sma = calculate_sma(data.close, 20)  # Uses ALL data including future!
# This is lookahead bias - DO NOT DO THIS
```

### Transaction Costs
Every trade costs money:
- Commission: 0.1% per trade (built-in)
- Slippage: 0.05% per trade (built-in)
- High-frequency strategies may be unprofitable after costs

### Minimize Whipsaws
Rapid signal changes (long → flat → long) cause unnecessary costs. The `create_strategy_wrapper()` function prevents this by requiring signal confirmation.

You can also add manual filters:
```python
# Only enter if price moved X% since last signal
if abs(close[current_bar] - close[current_bar-1]) / close[current_bar-1] > 0.01:
    # Allow signal change
```

### Simplicity Criterion
All else being equal, simpler is better:
- Similar score with 20 fewer lines = definitely keep
- Small score improvement with 50 complex lines = probably not worth it
- Same score but more conditions = discard

**Why simple is better:**
- Less prone to overfitting
- More robust to market changes
- Easier to understand and debug

### First Experiment
Your very first run should always be to establish baseline:
1. Check out new branch
2. Run `uv run strategy.py` without any modifications
3. Log baseline metrics and score
4. THEN start experiments

### Crashes
If a run crashes (index error, division by zero, etc.):
- If it's dumb/easy to fix (off-by-one, missing indicator), fix and re-run
- If the idea itself is fundamentally broken, log as "crash" and move on
- Common errors:
  - Index out of range (current_bar < LOOKBACK)
  - Division by zero (avoid with epsilon or check)
  - Empty calculations (check array length)

### Never Stop
Once experiment loop begins:
- Do NOT ask human "should I continue?"
- Do NOT pause to report progress
- Run continuously until manually stopped
- If out of ideas: read technical analysis docs, try combining indicators, try different market regimes

### Data Lookback
Ensure you have enough historical data before accessing indicators:
```python
if current_bar < LOOKBACK:
    return 0  # Not enough data, stay flat
```

### Indicator Period Selection
Good starting points:
- Moving averages: 10-50
- RSI: 14
- MACD: 12, 26, 9
- Bollinger Bands: 20, 2.0
- ATR: 14

Avoid extreme values unless you have a specific reason.

## Technical Indicators Reference

### Trend Indicators
**Simple Moving Average (SMA)**
```python
sma = calculate_sma(close, 20)
# Price > SMA = uptrend, Price < SMA = downtrend
```

**Exponential Moving Average (EMA)**
```python
ema = calculate_ema(close, 20)
# Faster response than SMA
```

**SMA Crossover**
```python
sma_fast = calculate_sma(close, 10)
sma_slow = calculate_sma(close, 30)
# Fast > Slow = uptrend
```

### Momentum Indicators
**RSI (Relative Strength Index)**
```python
rsi = calculate_rsi(close, 14)
# > 70 = overbought (potential sell)
# < 30 = oversold (potential buy)
```

**MACD**
```python
macd, signal, hist = calculate_macd(close, 12, 26, 9)
# MACD > signal = bullish
# MACD < signal = bearish
# Histogram rising = momentum up
```

### Volatility Indicators
**Bollinger Bands**
```python
upper, middle, lower = calculate_bollinger_bands(close, 20, 2.0)
# Price > upper = overextended
# Price < lower = oversold
```

**ATR (Average True Range)**
```python
atr = calculate_atr(high, low, close, 14)
# Measure of volatility
# Use for stop losses: stop = entry - 2 * atr
```

### Volume Indicators
(Not implemented in baseline, but you can add)
- On-Balance Volume (OBV)
- Volume Moving Average
- Volume Profile

## Strategy Patterns

### Trend Following
```python
# Entry: Follow the trend
long = sma_fast[current_bar] > sma_slow[current_bar]
short = sma_fast[current_bar] < sma_slow[current_bar]
```

### Mean Reversion
```python
# Entry: Price away from mean
long = close[current_bar] < lower[current_bar]  # Below BB
short = close[current_bar] > upper[current_bar]  # Above BB
```

### Momentum
```python
# Entry: RSI + MACD confirmation
long = (rsi[current_bar] < 70 and
        hist[current_bar] > hist[current_bar-1])
```

### Filtered Trend (Recommended)
```python
# Only trade if trend AND conditions met
trend_up = sma_fast[current_bar] > sma_slow[current_bar]
not_overbought = rsi[current_bar] < 70
momentum_up = hist[current_bar] > hist[current_bar-1]

long = all([trend_up, not_overbought, momentum_up])
```

### Volatility Filter
```python
# Avoid trading in extreme volatility
atr_current = atr[current_bar]
atr_avg = np.mean(atr[current_bar-20:current_bar])
volatility_ok = atr_current < atr_avg * 1.5  # < 50% above average
```

## Risk Management Patterns

### Position Sizing
```python
# Scale position based on ATR (volatility)
position_size = MAX_POSITION_SIZE / atr[current_bar]
```

### Trailing Stop
```python
# (Requires state tracking in wrapper)
# Trail stop loss as price moves favorably
```

### Time-based Exit
```python
# Exit after N bars
holding_bars = current_bar - entry_bar
if holding_bars > 20:
    return 0  # Exit position
```

## Experiment Loop Workflow

1. **Setup:**
   - Create branch: `git checkout -b research/<date-tag>`
   - Verify data exists in `~/.cache/trading-research/`
   - Initialize `results.tsv` with header row
   - Run baseline (unmodified strategy.py) to establish initial metrics

2. **Experiment:**
   - Modify `strategy.py` with your idea
   - `git commit -am "description"`
   - `uv run strategy.py > run.log 2>&1`
   - Extract: `grep "^total_return:\|^sharpe_ratio:\|^max_drawdown:\|^profit_factor:\|^win_rate:\|^num_trades:" run.log`

3. **Evaluate:**
   - Calculate composite score
   - If score higher (improved): keep commit, branch advances
   - If score equal/lower: `git reset --hard HEAD~1`
   - Log result to `results.tsv`

4. **Repeat:** Continue indefinitely

## Common Experiment Ideas

### Indicator Parameters
```python
# Change RSI period
rsi = calculate_rsi(close, 21)  # Try 10, 14, 21, 30

# Change SMA periods
sma_fast = calculate_sma(close, 15)  # Try 5, 10, 15, 20
sma_slow = calculate_sma(close, 35)  # Try 20, 30, 40, 50

# Change Bollinger Bands
upper, middle, lower = calculate_bollinger_bands(close, 20, 2.5)  # Try 1.5, 2.0, 2.5
```

### Add New Indicators
```python
# Add ADX for trend strength
# Add Stochastic oscillator
# Add CCI (Commodity Channel Index)
# Add Williams %R
```

### Add Filters
```python
# Volatility filter
atr_ok = atr[current_bar] < atr[current_bar-1] * 1.5

# Trend strength filter
adx > 25  # Only trade strong trends

# Time-of-day filter
# Only trade during certain hours (intraday)
```

### Change Entry Logic
```python
# Require ALL conditions vs ANY condition
if all(long_conditions):  # AND logic
    return 1

if any(long_conditions):  # OR logic
    return 1

# Add confirmation (2 of 3 conditions)
if sum(long_conditions) >= 2:
    return 1
```

### Multi-timeframe (Advanced)
```python
# Check daily trend + hourly signal
# Requires data with multiple timeframes
```

## Success Metrics

- Primary: Maximize composite score (Sharpe-weighted)
- Target: Sharpe > 1.5, Total Return > 20%, Max Drawdown < 15%
- Secondary: Profit factor > 2.0, Win rate 40-60%
- Constraints: Realistic transaction costs, avoid overfitting

## Platform and Hardware

**CPU-only:** No GPU required
- Mac Mini M4: Perfectly fine
- RAM: 16GB is plenty
- Storage: <100MB for data

**Backtest speed:**
- Seconds for daily data (2520 bars = ~10 years)
- Minutes for intraday data

**Local LLM compatibility:**
- Can run local LLM (Llama 3.2, Mistral) for strategy generation
- Mac Mini M4 16GB can handle: LLM + backtesting + data
- Recommended: Use Ollama for local LLM management

## Dependency Management

### Package Manager: uv
```bash
uv sync              # install dependencies
uv run <script.py>  # run scripts with correct env
```

### Key Dependencies
- `pandas` - Data manipulation
- `numpy` - Numerical calculations
- `ta` - Technical analysis library (optional but recommended)
- `plotly` - Visualization (optional)
- `python-telegram-bot` - Alerts (optional)

**Cannot add new packages** - limited to what's in `pyproject.toml`

## Trading Knowledge Needed

### Essential Concepts
- **Long**: Profit when price goes up
- **Short**: Profit when price goes down
- **Flat**: No position
- **Uptrend**: Higher highs and higher lows
- **Downtrend**: Lower highs and lower lows
- **Support/Resistance**: Price levels where price tends to reverse
- **Breakout**: Price moves beyond support/resistance

### Market Regimes
- **Bull market**: Prices rising
- **Bear market**: Prices falling
- **Sideways/Range**: Prices oscillating in range
- **Volatile**: Large price swings
- **Low volatility**: Small price swings

### Technical Analysis Basics
- **Trend**: Direction of price movement
- **Momentum**: Speed of price change
- **Volatility**: Magnitude of price changes
- **Volume**: Number of shares traded

### Risk Management
- **Position sizing**: How much to invest per trade
- **Stop loss**: Automatic exit if price moves against you
- **Take profit**: Automatic exit at target price
- **Max drawdown**: Largest account value decline

## Overfitting Prevention

**Warning:** Strategies can look great historically but fail in live trading.

**Signs of overfitting:**
- Too many conditions (>5-7 rules)
- Perfect metrics (Sharpe > 3, win rate > 80%)
- Works perfectly on specific time period only
- Uses many indicator parameters without logic

**Prevention strategies:**
- Keep strategies simple (<10 lines of logic)
- Use walk-forward analysis (test on future data)
- Avoid parameter hunting to extreme precision
- Focus on robust, generalizable patterns
- Consider out-of-sample testing

## Integration with Local LLM

**On Mac Mini M4 16GB:**
1. Install Ollama: `brew install ollama`
2. Pull a model: `ollama pull llama3.2`
3. Run ollama: `ollama serve`
4. Configure agent to use local LLM

**Benefits:**
- No API costs
- Privacy (data stays local)
- Can run 24/7 without rate limits
- Lower latency than cloud APIs

**Resource usage:**
- LLM: ~4-8GB RAM (depends on model size)
- Backtesting: <100MB RAM
- Data: ~10MB disk
- Total: Well within 16GB capacity

## Comparison with autoresearch

| Aspect | autoresearch | trading-research |
|--------|-------------|-----------------|
| Domain | ML architecture | Trading strategies |
| Hardware | NVIDIA GPU required | CPU only |
| Time per experiment | 5 minutes (GPU) | Seconds (CPU) |
| Metric | val_bpb (lower) | Sharpe/Return (higher) |
| Data | 400B tokens text | OHLCV price data |
| Complexity | Neural networks | Technical analysis |
| Overfitting risk | High (arch search) | High (curve fitting) |
| Local LLM | Possible | Recommended |

## Safety and Disclaimer

**This is a research tool, not financial advice.**

- Past performance ≠ future results
- Always paper trade before live trading
- Start with small position sizes
- Never risk money you can't afford to lose
- Consult financial professionals
- Understand the risks before trading

**Common pitfalls to avoid:**
- Overconfidence in backtest results
- Ignoring transaction costs
- Overleveraging positions
- Trading without risk management
- Following signals blindly without understanding

Remember: The goal is to discover promising strategies, not guaranteed profits. Use good judgment and risk management.
