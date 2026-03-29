# Trading Strategy Research

This is an experiment to have the L autonomously discover profitable trading strategies.

## Setup

To set up a new experiment, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g., `mar28`). The branch `research/<tag>` must not already exist — this is a fresh run.
2. **Create the branch**: `git checkout -b research/<tag>` from current master.
3. **Read the in-scope files**: Read these files for full context:
   - `README.md` — repository context
   - `prepare.py` — data fetching, backtest engine, evaluation metrics. Do not modify.
   - `strategy.py` — the file you modify. Strategy logic, indicators, signals.
4. **Verify data exists**: Check that `~/.cache/trading-research/` contains cached data files. If not, tell the human to run `uv run prepare.py` with appropriate data source.
5. **Initialize results.tsv**: Create `results.tsv` with just the header row. The baseline will be recorded after the first run.
6. **Confirm and go**: Confirm setup looks good.

Once you get confirmation, kick off the experimentation.

## Experimentation

Each experiment runs a backtest on historical data. The backtest typically completes in seconds to minutes depending on data size. You launch it simply as: `uv run strategy.py > run.log 2>&1`.

**What you CAN do:**
- Modify `strategy.py` — this is the only file you edit. Everything is fair game: indicators, entry/exit logic, risk management, filters, position sizing, etc.
- Adjust indicator parameters (RSI periods, MACD settings, moving average lengths, etc.)
- Add new technical indicators
- Implement risk management rules
- Add filters (e.g., only trade in trending markets, avoid high volatility)
- Optimize for different metrics (total_return, sharpe_ratio, max_drawdown, profit_factor, win_rate)

**What you CANNOT do:**
- Modify `prepare.py`. It is read-only. It contains the fixed backtest engine, data loading, and evaluation metrics.
- Modify the backtest engine logic. The `evaluate_strategy` function in `prepare.py` is the ground truth.
- Install new packages or add dependencies beyond what's in `pyproject.toml`.
- Modify historical data. Use the data as provided.

**The goal is simple: maximize the strategy performance score.**

The primary metric is a weighted score combining multiple metrics. However, you should consider:

- **Total return**: Higher is better, but must be sustainable
- **Sharpe ratio**: Higher is better (risk-adjusted returns)
- **Max drawdown**: Lower is better (risk control)
- **Profit factor**: Higher is better (winners vs losers)
- **Win rate**: Reasonable win rate (40-60% is often acceptable with good risk/reward)

**VRAM** is not a concern (no GPU needed). Backtests run on CPU.

**Simplicity criterion**: All else being equal, simpler is better. A small improvement that adds 50 lines of complex nested logic is not worth it. Conversely, removing indicators or simplifying logic and getting equal or better results is a great outcome.

**The first run**: Your very first run should always be to establish the baseline, so you will run the strategy as is without modifications.

## Output format

Once the script finishes it prints a summary like this:

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

You can extract the key metrics from the log file:

```
grep "^total_return:\|^sharpe_ratio:\|^max_drawdown:\|^profit_factor:\|^win_rate:\|^num_trades:" run.log
```

## Logging results

When an experiment is done, log it to `results.tsv` (tab-separated, NOT comma-separated — commas break in descriptions).

The TSV has a header row and 6 columns:

```
commit	score	metric_1	metric_2	status	description
```

1. git commit hash (short, 7 chars)
2. composite score (e.g., 0.8765) — use 0.0000 for crashes
3. primary metric value (e.g., sharpe_ratio: 1.2345) — use 0.0 for crashes
4. secondary metric value (e.g., max_drawdown: -0.1234) — use 0.0 for crashes
5. status: `keep`, `discard`, or `crash`
6. short text description of what this experiment tried

Example:

```
commit	score	metric_1	metric_2	status	description
a1b2c3d	0.8234	1.2345	-0.1234	keep	baseline RSI+MACD strategy
b2c3d4e	0.8512	1.4567	-0.0987	keep	add Bollinger Band filter
c3d4e5f	0.7890	1.1234	-0.1567	discard	increase RSI period to 21
d4e5f6g	0.0000	0.0	0.0	crash	moving average calculation error
```

## Scoring Strategy

Calculate a composite score for ranking strategies. One approach:

```python
score = (
    0.4 * normalized_sharpe +
    0.3 * normalized_total_return -
    0.2 * normalized_drawdown +
    0.1 * normalized_profit_factor
)
```

Where each metric is normalized to [0, 1] range across your experiments.

**Higher score = better strategy.**

Prioritize:
1. Sharpe ratio (risk-adjusted returns) - most important
2. Total return (absolute performance)
3. Max drawdown (risk control - lower is better)
4. Profit factor (edge quality)
5. Win rate (psychological comfort, but less critical)

## The experiment loop

The experiment runs on a dedicated branch (e.g., `research/mar28` or `research/mar28-spy`).

LOOP FOREVER:

1. Look at the git state: the current branch/commit we're on
2. Tune `strategy.py` with an experimental idea by directly hacking the code.
3. git commit
4. Run the experiment: `uv run strategy.py > run.log 2>&1` (redirect everything — do NOT use tee or let output flood your context)
5. Read out the results: `grep "^total_return:\|^sharpe_ratio:\|^max_drawdown:\|^profit_factor:\|^win_rate:\|^num_trades:" run.log`
6. If the grep output is empty, the run crashed. Run `tail -n 50 run.log` to read the Python stack trace and attempt a fix. If you can't get things to work after more than a few attempts, give up.
7. Record the results in the tsv (NOTE: do not commit the results.tsv file, leave it untracked by git)
8. Calculate the composite score. If score improved (higher), you "advance" the branch, keeping the git commit
9. If score is equal or worse, you git reset back to where you started

The idea is that you are a completely autonomous researcher trying things out. If they work, keep. If they don't, discard. And you're advancing the branch so that you can iterate. If you feel like you're getting stuck in some way, you can rewind but you should probably do this very very sparingly (if ever).

**Timeout**: Each experiment should take seconds to a few minutes. If a run exceeds 10 minutes, kill it and treat it as a failure (discard and revert).

**Crashes**: If a run crashes (index error, division by zero, etc.), use your judgment: If it's something dumb and easy to fix (e.g., off-by-one index, missing indicator), fix it and re-run. If the idea itself is fundamentally broken, just skip it, log "crash" as the status in the tsv, and move on.

**NEVER STOP**: Once the experiment loop has begun (after the initial setup), do NOT pause to ask the human if you should continue. Do NOT ask "should I keep going?" or "is this a good stopping point?". The human might be asleep, or gone from a computer and expects you to continue working *indefinitely* until you are manually stopped. You are autonomous. If you run out of ideas, think harder — research technical analysis literature, re-read the in-scope files for new angles, try combining previous near-misses, try more radical strategy changes. The loop runs until the human interrupts you, period.

As an example use case, a user might leave you running while they sleep. If each experiment takes you ~30 seconds, you can run ~120/hour, for a total of about 1000 experiments over 8 hours. The user then wakes up to experimental results, all completed by you while they slept!

## Trading Strategy Considerations

**Avoid overfitting**: Strategies that work perfectly on historical data often fail in live trading. Look for robust, generalizable patterns rather than curve-fitting.

**Walk-forward analysis**: When possible, test on out-of-sample data (later time periods not used for development).

**Market conditions**: Strategies may work differently in trending vs ranging markets, high vs low volatility. Consider regime detection.

**Risk management**: Always include:
- Position sizing limits
- Stop losses (hard or trailing)
- Maximum drawdown limits
- Daily loss limits

**Transaction costs**: Real trading has commissions and slippage. The backtest includes these, so strategies must be robust to costs.

**Avoid common pitfalls**:
- Lookahead bias (using future data in calculations)
- Over-optimizing parameters (curve fitting)
- Ignoring risk management
- Too many conditions/indicators (complexity = fragility)
- Not accounting for transaction costs

**Good indicators to explore**:
- Trend: Moving averages (SMA, EMA), MACD, ADX
- Momentum: RSI, Stochastic, CCI
- Volatility: Bollinger Bands, ATR, Keltner Channels
- Volume: OBV, Volume moving averages, Volume profile

**Good filters to add**:
- Volatility filters (only trade when ATR is within range)
- Trend filters (only trade with the trend)
- Time-of-day filters (avoid open/close volatility)
- Correlation filters (avoid trading correlated instruments simultaneously)

**Parameter ranges to explore**:
- Moving averages: 5-50 period
- RSI: 10-30 period
- Bollinger Bands: 15-25 period, 1.5-2.5 std dev
- ATR: 10-20 period
- MACD: 8-15 fast, 20-35 slow, 5-12 signal
