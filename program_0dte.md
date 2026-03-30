# Autonomous 0DTE Credit Spread Research

## Your Mission

You are an autonomous AI agent conducting quantitative research on 0DTE (zero days to expiration) credit spread strategies for SPY and QQQ.

Your goal: Discover patterns in intraday price movements that help predict whether the rest of the day will be flat, up, or down.

## Context

You are modifying `strategy_0dte.py` (NOT `strategy.py`) to find profitable 0DTE credit spread patterns.

**Data:** SPY intraday (5-minute bars, 3 months, 4836 bars)

## Key Concepts

### Call Credit Spread
- Sell calls above current price
- Profit if price stays below strike by close
- Bet: Flat or down → Signal -1

### Put Credit Spread
- Sell puts below current price
- Profit if price stays above strike by close
- Bet: Flat or up → Signal 1

### Strategy Signals
- **1 (Long/Up):** Expect price to go up or stay flat → Put credit spread
- **0 (Flat):** No clear signal → Wait
- **-1 (Short/Down):** Expect price to go down or stay flat → Call credit spread

## Current Strategy Architecture

Your strategy in `strategy_0dte.py` has:

1. **Time-based pattern recognition:**
   - Morning sweep detection
   - Afternoon drift detection
   - Late-day range detection

2. **Technical indicators:**
   - VWAP (Volume Weighted Average Price)
   - RSI (Relative Strength Index)
   - ATR (Average True Range)

3. **Entry window:**
   - 10:00 AM to 2:30 PM Eastern
   - Avoids market open/close volatility

4. **Filters:**
   - Volatility filter (avoid high ATR days)
   - RSI overextension filter

## Performance Metrics

```bash
# Extract from log
grep "^total_return:\|^sharpe_ratio:\|^max_drawdown:\|^profit_factor:\|^win_rate:\|^num_trades:" run.log
```

**Target metrics for 0DTE:**
- Sharpe ratio > 1.5
- Total return > 5% per quarter (extrapolated)
- Max drawdown < 10%
- Win rate > 55%
- Profit factor > 1.5

## Composite Score

```python
# Recommended weighting for 0DTE
score = (
    0.35 * normalized_sharpe +      # Risk-adjusted returns (most important)
    0.25 * normalized_total_return + # Absolute performance
    0.20 * normalized_win_rate +      # Winning percentage
    -0.20 * normalized_drawdown       # Risk control (negative)
)
```

## Experiment Ideas

### 1. Time Window Adjustments

```python
# Try different entry windows
ENTRY_TIME_START = "09:45"  # Earlier entry
ENTRY_TIME_END = "15:00"     # Later entry

# Or session-specific logic
if session == 'morning':
    # Aggressive morning trading
elif session == 'afternoon':
    # Conservative afternoon trading
elif session == 'late':
    # Very selective late-day trading
```

### 2. VWAP Enhancements

```python
# Add VWAP band
vwap_band_pct = 0.003  # 0.3% band around VWAP
if current_price > vwap_level * (1 + vwap_band_pct):
    # Extended above VWAP → call credit spread
elif current_price < vwap_level * (1 - vwap_band_pct):
    # Extended below VWAP → put credit spread
```

### 3. Volatility Regime Detection

```python
# Adjust ATR threshold based on market conditions
ATR_THRESHOLD = 1.3  # More aggressive entry

# Or use rolling ATR percentile
atr_percentile = calculate_atr_percentile(atr, current_bar, lookback=78)
if atr_percentile < 30:  # Low volatility days
    # Wider entry criteria
elif atr_percentile > 70:  # High volatility days
    # Stricter entry or no trades
```

### 4. Morning Pattern Refinement

```python
# Enhance morning sweep detection
def detect_morning_sweep_v2(close, volume, index):
    """Improved morning sweep with volume confirmation."""
    if index < 20:
        return False

    # Check for early strong move with volume
    early_move = abs(close[index] - close[index-12]) / close[index-12]
    early_vol = np.mean(volume[index-12:index])

    if early_move > 0.005 and early_vol > np.mean(volume) * 1.2:
        # Strong move with volume → reversal expected
        return True

    return False
```

### 5. Afternoon Drift Enhancement

```python
# Add drift confirmation with RSI
drift = detect_afternoon_drift(close, volume, current_bar)

if drift == 'up' and 30 < rsi[current_bar] < 70:
    # Confirmed upward drift, not overextended
    return 1  # Put credit spread

elif drift == 'down' and 30 < rsi[current_bar] < 70:
    # Confirmed downward drift, not oversold
    return -1  # Call credit spread
```

### 6. Support/Resistance Integration

```python
# Use S/R levels more aggressively
support, resistance = detect_support_resistance(close, high, low, current_bar)

if support and resistance:
    price_position = (current_price - support) / (resistance - support)

    if price_position > 0.8:  # Near resistance
        return -1  # Call credit spread
    elif price_position < 0.2:  # Near support
        return 1  # Put credit spread
```

### 7. Multi-Condition Signals

```python
# Require ALL conditions for high-confidence trades
if (session == 'morning' and
    detect_morning_sweep(close, current_bar) and
    current_price < vwap_level and
    rsi[current_bar] < 60):
    # Strong put credit spread signal
    return 1

# Or ANY condition for more trades
if (detect_morning_sweep(close, current_bar) or
    detect_afternoon_drift(close, volume, current_bar) == 'up'):
    return 1
```

### 8. Risk Management

```python
# Add trade cooldown
if current_bar - last_entry_bar < 10:  # Min 50 mins between trades
    return 0

# Stop trading after losses
if consecutive_losses >= 2:
    return 0

# Position sizing based on confidence
if (all(long_conditions) and  # High confidence
    current_bar % 2 == 0):  # Throttle frequency
    return 1
```

## 0DTE-Specific Considerations

### Intraday Dynamics
- **Morning (9:30-11:00):** High volatility, reversal opportunities
- **Mid-day (11:00-2:00):** Lower volatility, range trading
- **Late (2:00-4:00):** Volume pickup, potential moves

### Volatility Regimes
- **Low vol days:** More likely to stay flat → ideal for credit spreads
- **High vol days:** Risk of large moves → avoid or be selective

### Price Action Patterns
- **Gaps up/down:** Measure gap size and decide if fade or follow
- **First 30 mins:** Often sets tone for day
- **Pre-earnings:** Avoid entirely (unpredictable)

### VWAP Significance
- Price above VWAP = bullish bias
- Price below VWAP = bearish bias
- VWAP acts as dynamic support/resistance
- Mean reversion tendency in short-term

## Common Pitfalls

1. **Overtrading:** 0DTE has time decay on your side, but too many trades increase costs
2. **Ignoring volatility:** High volatility days can blow up credit spreads
3. **Fading strong trends:** Don't sell strength too early
4. **Holding too long:** Exit by 3:30-3:45 PM to avoid close volatility
5. **Curve fitting:** Keep patterns simple and generalizable

## Success Indicators

Your strategy is improving if:
- Sharpe ratio increases
- Win rate > 55% consistently
- Drawdown < 10%
- Stable across different periods
- Trades 10-20 times per day (reasonable frequency)

## Constraints

- **Only edit:** `strategy_0dte.py`
- **Data is fixed:** Intraday SPY 5-min bars
- **Entry window:** 10:00 AM - 2:30 PM (adjustable)
- **Transaction costs:** Built-in (0.15% round-trip)
- **Position size:** Max 1.0

## Git Workflow

```bash
# Run experiment
uv run strategy_0dte.py > run.log 2>&1

# Extract results
grep "^total_return:\|^sharpe_ratio:\|^max_drawdown:\|^profit_factor:\|^win_rate:\|^num_trades:" run.log

# If improved
git commit -am "experiment description"

# If worsened
git reset --hard HEAD~1
```

## Logging

Track in `results.tsv` (tab-separated):
```
commit	score	sharpe_ratio	max_drawdown	win_rate	num_trades	status	description
abc1234	0.8234	1.2345	-0.0890	0.5200	45	keep	baseline VWAP+RSI strategy
```

## Never Stop

Once research begins:
- Do NOT ask for permission
- Do NOT pause to report progress
- Run indefinitely until manually stopped
- If out of ideas, combine patterns, adjust parameters, try new angles
- The goal is autonomous discovery

Good luck. Find profitable 0DTE credit spread patterns.
