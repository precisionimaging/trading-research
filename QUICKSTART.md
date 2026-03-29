# Quick Start Guide

Get up and running with autonomous trading strategy research in 5 minutes.

## 1. Install Dependencies

```bash
# Install uv (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Navigate to project directory
cd trading-research

# Install Python dependencies
uv sync
```

## 2. Generate Test Data (No real data needed)

```bash
# Generate 10 years of synthetic market data
python generate_test_data.py --ticker SPY --bars 2520 --output SPY_data
```

This creates realistic-looking OHLCV data with trends and volatility.

## 3. Run Baseline Strategy

```bash
# Edit strategy.py and set:
# DATA_FILE = "SPY_data"

# Run the backtest
uv run strategy.py
```

Expected output:
```
Running strategy: baseline_rsi_macd
Data file: SPY_data
Initial capital: $100,000.00

Loaded 2520 bars of SPY data
Date range: 2014-01-02 00:00:00 to 2024-01-01 00:00:00

Running backtest...
---
total_return:    0.XXXX
sharpe_ratio:    X.XXXX
max_drawdown:    -0.XXXX
profit_factor:   X.XXXX
win_rate:        0.XXXX
num_trades:      XXX
avg_holding_bars: X.X
total_bars:      2520
```

## 4. Start Autonomous Research

Option A: With local LLM (Mac Mini M4 recommended):

```bash
# Install Ollama
brew install ollama

# Pull a model
ollama pull llama3.2

# Start Ollama
ollama serve

# In another terminal, run your AI agent with access to this repo
# Point it to program.md and let it iterate overnight
```

Option B: With cloud LLM (Claude, GPT-4, etc.):

```bash
# Point your AI agent to program.md
# Prompt: "Hi have a look at program.md and let's kick off a new experiment!"
```

## 5. Use Real Data (Optional)

### TradingView (Easiest)
1. Go to TradingView.com
2. Search for your ticker (e.g., SPY, AAPL)
3. Click "Download" → Save as CSV
4. Import:
```bash
uv run prepare.py --source tradingview --data SPY_data.csv --ticker SPY
```

### Interactive Brokers
```bash
# Requires IBKR API setup
uv run prepare.py --source ibkr --ticker AAPL --period 1y
```

## What Happens Next?

The agent will:
1. Read `program.md` for instructions
2. Modify `strategy.py` with new ideas
3. Run backtests (`uv run strategy.py > run.log 2>&1`)
4. Evaluate metrics (Sharpe, return, drawdown)
5. Keep improvements, discard failures
6. Repeat continuously (100s of experiments overnight)

You wake up to:
- `results.tsv` - Log of all experiments
- Best strategy saved in the git history
- Metrics showing performance improvements

## Expected Timeline

- **Setup**: 5 minutes
- **Baseline test**: 10 seconds
- **Per experiment**: 5-30 seconds (depends on data size)
- **100 experiments**: ~30 minutes
- **1000 experiments**: ~5 hours

## Common Issues

### "ModuleNotFoundError: No module named 'ta'"
```bash
# Install technical analysis library
uv pip install ta
```

### "FileNotFoundError: data/SPY_data.pkl"
```bash
# Generate test data or import real data
python generate_test_data.py --ticker SPY
```

### Backtest shows 0 trades
- Strategy may be too restrictive (all conditions must be true)
- Try loosening entry conditions
- Check indicator parameters

### Very high Sharpe (> 5)
- Likely overfitting on synthetic data
- Strategy won't generalize to real markets
- Simplify the logic

## Next Steps

1. **Review baseline metrics**: Note the Sharpe, return, and drawdown
2. **Read AGENTS.md**: Learn about strategy patterns and gotchas
3. **Start autonomous research**: Let the agent iterate overnight
4. **Analyze results**: Check `results.tsv` for best performers
5. **Paper trade**: Test promising strategies in a paper trading account
6. **Live trade** (only after thorough testing): Start with small sizes

## Tips for Success

- **Start simple**: Baseline strategy is intentionally basic
- **Let it run**: Autonomy requires time for exploration
- **Check for overfitting**: If Sharpe > 3, simplify
- **Focus on Sharpe**: Risk-adjusted returns matter most
- **Paper trade first**: Never jump straight to live trading
- **Understand your strategy**: Don't trade blind

## Support

- Read `README.md` for full documentation
- Read `AGENTS.md` for detailed agent instructions
- Read `program.md` for autonomous experiment workflow
- Review `prepare.py` for backtest engine details
- Review `strategy.py` for indicator implementations

## Safety Warnings

⚠️ **This is a research tool, not financial advice.**

- Past performance ≠ future results
- Always paper trade before live trading
- Start with small position sizes
- Never risk money you can't afford to lose
- Consult financial professionals before trading
- Understand that trading involves substantial risk

Happy researching! 📈
