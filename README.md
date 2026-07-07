# Groww Cloud Algo Strategy - Midcap & Smallcap Scanner

Automated stock scanner and trader that combines **sector/news sentiment** with **technical indicators** to find buy opportunities in midcap and smallcap stocks, plus reviews your existing portfolio for exit signals.

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│  PHASE 1: Portfolio Review                              │
│  - Check your holdings for stop-loss / target hits      │
│  - Auto-sell if stop loss breached                      │
│  - Flag stocks not aligned with current sector themes   │
├─────────────────────────────────────────────────────────┤
│  PHASE 2: Market Scan                                   │
│  - Scan 50+ midcap/smallcap stocks                     │
│  - Score each using technical + sector signals          │
│  - Rank by combined signal strength                     │
├─────────────────────────────────────────────────────────┤
│  PHASE 3: Execute Trades                                │
│  - Buy top-ranked stocks (score >= 4)                  │
│  - Set GTT stop-loss automatically                     │
│  - Respect max trades/day limit                        │
└─────────────────────────────────────────────────────────┘
```

## Signals Used

### Technical Indicators
| Signal | Condition | Score |
|--------|-----------|-------|
| Volume Spike | Current volume > 2x average | +2 |
| Gap Up | Open > 2% above prev close | +2 |
| Price Momentum | Trading above open & prev close | +1 |
| Near Day Low | Price in bottom 30% of day range (reversal) | +1 |
| Bullish Candle | Green candle body > 60% of range | +1 |

### Sector/News Scoring
| Sector | Score | Reason |
|--------|-------|--------|
| Defence | 5 | Increased defence budget & Make in India |
| Railways | 5 | Modernization & Vande Bharat expansion |
| Infrastructure | 4 | PM Gati Shakti & NIP spending |
| Renewable Energy | 4 | Green energy targets & PLI schemes |
| Electronics Mfg | 4 | PLI for electronics & semiconductor mission |
| EV / Auto | 4 | FAME subsidy & EV adoption |
| Pharma | 3 | Healthcare infra & export demand |
| Fintech / Digital | 3 | Digital India push |
| Agriculture | 3 | MSP hikes & agri-infra fund |
| Tourism | 3 | Post-covid boom & govt schemes |

A stock needs a **combined score of 4+** to trigger a buy.

## Setup Instructions

### Step 1: Get Your API Key

1. Log in to [Groww](https://groww.in)
2. Go to Profile → Settings (gear icon)
3. Navigate to **API Keys** section
4. Click **Generate API Key**
5. Copy your `API Key` and `Secret Key`

### Step 2: Deploy on Groww Cloud

1. Go to [Groww Trade API Strategies](https://groww.in/trade-api/strategies)
2. Click **"Add new strategy"**
3. Copy the entire contents of `strategy.py`
4. Paste it into the script editor
5. Replace these values at the top:
   ```python
   user_api_key = "your_actual_api_key"
   user_secret = "your_actual_secret_key"
   ```
6. Update `MY_PORTFOLIO` with your actual holdings:
   ```python
   MY_PORTFOLIO = [
       {"symbol": "IDEA", "buy_price": 14.5, "quantity": 100},
       {"symbol": "TATAPOWER", "buy_price": 420.0, "quantity": 25},
       # Add all your holdings
   ]
   ```
7. Click **Save**
8. Toggle from **Inactive** → **Active**

### Step 3: Configure Parameters

Edit the `CONFIG` dictionary to match your risk appetite:

```python
CONFIG = {
    "max_capital_per_trade": 15000,   # Increase/decrease per trade
    "stop_loss_pct": 3.0,            # Tighter = safer, wider = more room
    "target_profit_pct": 6.0,        # When to book profit
    "max_trades_per_day": 5,         # Safety limit
    "product_type": "MIS",           # "MIS" for intraday, "CNC" for delivery
}
```

## Customization

### Add/Remove Stocks from Scan Universe

Edit `MIDCAP_SMALLCAP_UNIVERSE` list in the script:

```python
MIDCAP_SMALLCAP_UNIVERSE = [
    "HAL", "BEL", "RVNL",   # Add symbols you want to track
    "NEWSTOCK1", "NEWSTOCK2",
]
```

### Update Sector Themes (Important!)

When new policies, budgets, or industry news break, update `SECTOR_THEMES`:

```python
SECTOR_THEMES = {
    "new_theme": {
        "keywords": ["keyword1", "keyword2"],
        "score": 4,
        "reason": "Why this sector is hot right now"
    },
}
```

### Switch to Delivery (Positional) Trading

Change product type to hold stocks overnight:

```python
CONFIG["product_type"] = "CNC"  # Instead of "MIS"
```

## Risk Warnings

- **This is not financial advice.** Use at your own risk.
- **Start small.** Test with minimal capital first.
- **Monitor actively.** Don't rely 100% on automation without oversight.
- **Static IP required** for API orders (or use Groww Cloud which handles this).
- **Market hours only.** Strategy should run between 9:15 AM - 3:15 PM IST.
- **Paper trade first.** Test your strategy logic before using real money.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Access token expired" | Regenerate token from API Keys page |
| "Insufficient funds" | Reduce `max_capital_per_trade` |
| "Symbol not found" | Check exact NSE trading symbol |
| "Order rejected" | Check market hours, verify symbol is tradeable |
| "Rate limit" | Increase `time.sleep()` between API calls |

## File Structure

```
groww-strategy/
├── strategy.py   # Main strategy (paste into Groww Cloud)
└── README.md     # This file
```
