# ====================
# Groww Cloud Algo Trading Strategy
# Midcap & Smallcap Scanner + Portfolio Review
# ====================

import time
from growwapi import GrowwAPI

# ====================
# CONFIGURATION
# ====================

user_api_key = "your_api_key"
user_secret = "your_secret_key"

CONFIG = {
    "volume_spike_multiplier": 2.0,
    "gap_up_threshold": 2.0,
    "max_capital_per_trade": 15000,
    "stop_loss_pct": 3.0,
    "target_profit_pct": 6.0,
    "max_trades_per_day": 5,
    "product_type": "CNC",
    "min_score_to_buy": 4,
}

# Sector themes based on govt policy & industry news
SECTOR_THEMES = {
    "defence": {"score": 5, "reason": "Defence budget & Make in India"},
    "railways": {"score": 5, "reason": "Railway modernization"},
    "infrastructure": {"score": 4, "reason": "PM Gati Shakti & NIP"},
    "renewable_energy": {"score": 4, "reason": "Green energy & PLI"},
    "electronics_mfg": {"score": 4, "reason": "Semiconductor & PLI"},
    "ev_auto": {"score": 4, "reason": "FAME subsidy & EV push"},
    "pharma": {"score": 3, "reason": "Healthcare expansion"},
    "fintech": {"score": 3, "reason": "Digital India"},
    "agriculture": {"score": 3, "reason": "MSP hikes & agri fund"},
    "tourism": {"score": 3, "reason": "Travel boom & schemes"},
    "power_energy": {"score": 4, "reason": "Power sector capex"},
    "metals": {"score": 3, "reason": "Infrastructure demand"},
}

# Stock -> Sector mapping
STOCK_SECTOR = {
    "HAL": "defence", "BEL": "defence", "BDL": "defence",
    "COCHINSHIP": "defence", "GRSE": "defence", "MAZAGON": "defence",
    "RVNL": "railways", "IRCTC": "railways", "TITAGARH": "railways",
    "RITES": "railways", "RAILTEL": "railways",
    "NCC": "infrastructure", "NBCC": "infrastructure", "IRB": "infrastructure",
    "KEC": "infrastructure", "JSWINFRA": "infrastructure",
    "NHPC": "renewable_energy", "SJVN": "renewable_energy",
    "TATAPOWER": "renewable_energy", "SUZLON": "renewable_energy",
    "DIXON": "electronics_mfg", "KAYNES": "electronics_mfg",
    "AMBER": "electronics_mfg", "SYRMA": "electronics_mfg", "NETWEB": "electronics_mfg",
    "TATAMOTORS": "ev_auto", "EXIDEIND": "ev_auto",
    "OLECTRA": "ev_auto", "OLAELEC": "ev_auto", "UNOMINDA": "ev_auto",
    "LAURUSLABS": "pharma", "AUROPHARMA": "pharma",
    "GRANULES": "pharma", "LALPATHLAB": "pharma",
    "PERSISTENT": "fintech", "COFORGE": "fintech",
    "MPHASIS": "fintech", "LTTS": "fintech",
    "UPL": "agriculture", "COROMANDEL": "agriculture",
    "DHANUKA": "agriculture", "RALLIS": "agriculture", "SUMICHEM": "agriculture",
    "INDIANHOTE": "tourism", "ITCHOTELS": "tourism",
    "RECLTD": "power_energy", "PFC": "power_energy",
    "POWERGRID": "power_energy", "IRFC": "railways",
    "TATASTEEL": "metals", "HINDCOPPER": "metals", "VEDL": "metals",
}

SCAN_UNIVERSE = list(STOCK_SECTOR.keys())

# ====================
# INITIALIZE
# ====================

access_token = GrowwAPI.get_access_token(api_key=user_api_key, secret=user_secret)
groww = GrowwAPI(access_token)
print("Connected to Groww API")

# ====================
# HELPER FUNCTIONS
# ====================

def get_sector_score(symbol):
    sector = STOCK_SECTOR.get(symbol)
    if sector and sector in SECTOR_THEMES:
        t = SECTOR_THEMES[sector]
        return t["score"], t["reason"]
    return 0, ""


def analyze_stock(symbol):
    """Analyze a stock using get_quote and return score + signals"""
    signals = []
    score = 0

    try:
        quote = groww.get_quote(
            trading_symbol=symbol,
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_CASH
        )

        ltp = quote.get("ltp", 0)
        open_price = quote.get("open", 0)
        high = quote.get("high", 0)
        low = quote.get("low", 0)
        close = quote.get("close", 0)
        volume = quote.get("volume", 0)
        avg_volume = quote.get("avgVolume", volume * 0.7)

        if ltp == 0:
            return 0, [], 0

        # Volume Spike
        if avg_volume > 0 and volume > avg_volume * CONFIG["volume_spike_multiplier"]:
            score += 2
            signals.append(f"VOL SPIKE {volume:,.0f}")

        # Gap Up
        if open_price > 0 and close > 0:
            gap = ((open_price - close) / close) * 100
            if gap >= CONFIG["gap_up_threshold"]:
                score += 2
                signals.append(f"GAP UP +{gap:.1f}%")

        # Momentum (price above open and prev close)
        if ltp > open_price > 0 and ltp > close > 0:
            score += 1
            signals.append("MOMENTUM")

        # Bullish candle
        if high > low > 0:
            body = abs(ltp - open_price)
            rng = high - low
            if ltp > open_price and rng > 0 and body > 0.6 * rng:
                score += 1
                signals.append("BULLISH CANDLE")

        # Reversal from low
        if high > low > 0:
            pos = (ltp - low) / (high - low)
            if pos < 0.3 and ltp > open_price:
                score += 1
                signals.append("REVERSAL")

        # Sector score
        sec_score, reason = get_sector_score(symbol)
        if sec_score > 0:
            score += sec_score
            signals.append(f"SECTOR:{reason}(+{sec_score})")

        return score, signals, ltp

    except Exception as e:
        return 0, [str(e)], 0


# ====================
# PORTFOLIO REVIEW
# ====================

def review_portfolio():
    print("\n" + "=" * 50)
    print("PORTFOLIO REVIEW")
    print("=" * 50)

    try:
        holdings = groww.get_holdings_for_user()
    except Exception as e:
        print(f"Cannot fetch holdings: {e}")
        return

    if not holdings or "holdings" not in holdings:
        print("No holdings found")
        return

    sell_candidates = []
    hold_stocks = []

    for h in holdings["holdings"]:
        symbol = h.get("trading_symbol", "")
        qty = int(h.get("quantity", 0))
        avg_price = h.get("average_price", 0)

        if qty <= 0 or avg_price <= 0:
            continue

        # Try to get current price
        try:
            quote = groww.get_quote(
                trading_symbol=symbol,
                exchange=groww.EXCHANGE_NSE,
                segment=groww.SEGMENT_CASH
            )
            ltp = quote.get("ltp", 0)
        except Exception:
            # Try BSE if NSE fails
            try:
                quote = groww.get_quote(
                    trading_symbol=symbol,
                    exchange=groww.EXCHANGE_BSE,
                    segment=groww.SEGMENT_CASH
                )
                ltp = quote.get("ltp", 0)
            except Exception:
                ltp = 0

        if ltp == 0:
            continue

        pnl_pct = ((ltp - avg_price) / avg_price) * 100
        pnl_abs = (ltp - avg_price) * qty
        sec_score, sec_reason = get_sector_score(symbol)

        # Decision
        action = "HOLD"
        if pnl_pct <= -CONFIG["stop_loss_pct"]:
            action = "SELL (SL HIT)"
            sell_candidates.append({"symbol": symbol, "qty": qty, "reason": "Stop Loss"})
        elif pnl_pct >= CONFIG["target_profit_pct"]:
            action = "BOOK PROFIT"
        elif sec_score == 0 and pnl_pct < -1:
            action = "CONSIDER EXIT"

        status = f"{symbol:12s} | Avg:{avg_price:>8.1f} | LTP:{ltp:>8.1f} | P&L:{pnl_pct:>+6.1f}% ({pnl_abs:>+8.0f}) | {action}"

        if sec_score > 0:
            status += f" [{sec_reason}]"

        print(status)
        time.sleep(0.3)

    # Auto-sell stop loss hits
    if sell_candidates:
        print(f"\n--- AUTO SELL ({len(sell_candidates)} stocks hit stop loss) ---")
        for s in sell_candidates:
            execute_sell(s["symbol"], s["qty"], s["reason"])


# ====================
# MARKET SCANNER
# ====================

def scan_market():
    print("\n" + "=" * 50)
    print("SCANNING MIDCAP/SMALLCAP UNIVERSE")
    print("=" * 50)

    results = []

    for symbol in SCAN_UNIVERSE:
        score, signals, ltp = analyze_stock(symbol)
        if score >= CONFIG["min_score_to_buy"]:
            results.append({"symbol": symbol, "score": score, "signals": signals, "ltp": ltp})
        time.sleep(0.3)

    results.sort(key=lambda x: x["score"], reverse=True)

    print(f"\nTop picks (score >= {CONFIG['min_score_to_buy']}):")
    print("-" * 50)

    for i, r in enumerate(results[:10]):
        print(f"#{i+1} {r['symbol']:12s} | LTP:{r['ltp']:>8.1f} | Score:{r['score']}")
        print(f"    Signals: {', '.join(r['signals'])}")

    return results


# ====================
# ORDER EXECUTION
# ====================

trades_today = 0


def execute_buy(symbol, ltp):
    global trades_today

    if trades_today >= CONFIG["max_trades_per_day"]:
        print(f"  Max trades reached. Skip {symbol}")
        return

    quantity = int(CONFIG["max_capital_per_trade"] / ltp)
    if quantity < 1:
        print(f"  Price too high for allocation. Skip {symbol}")
        return

    product = groww.PRODUCT_CNC if CONFIG["product_type"] == "CNC" else groww.PRODUCT_MIS

    try:
        print(f"  BUY: {symbol} x {quantity} @ Market (Rs {ltp:.1f})")

        order = groww.place_order(
            trading_symbol=symbol,
            quantity=quantity,
            validity=groww.VALIDITY_DAY,
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_CASH,
            product=product,
            order_type=groww.ORDER_TYPE_MARKET,
            transaction_type=groww.TRANSACTION_TYPE_BUY
        )

        trades_today += 1
        print(f"  Order: {order}")

        # Set GTT stop loss
        sl_price = round(ltp * (1 - CONFIG["stop_loss_pct"] / 100), 2)
        try:
            groww.create_smart_order(
                smart_order_type=groww.SMART_ORDER_TYPE_GTT,
                segment=groww.SEGMENT_CASH,
                trading_symbol=symbol,
                quantity=quantity,
                product_type=product,
                exchange=groww.EXCHANGE_NSE,
                duration=groww.VALIDITY_GTC,
                trigger_price=str(sl_price),
                trigger_direction=groww.TRIGGER_DIRECTION_DOWN,
                transaction_type=groww.TRANSACTION_TYPE_SELL
            )
            print(f"  GTT SL set at {sl_price}")
        except Exception as e:
            print(f"  GTT failed: {e}")

    except Exception as e:
        print(f"  BUY FAILED {symbol}: {e}")


def execute_sell(symbol, quantity, reason):
    product = groww.PRODUCT_CNC if CONFIG["product_type"] == "CNC" else groww.PRODUCT_MIS

    try:
        print(f"  SELL: {symbol} x {quantity} ({reason})")

        order = groww.place_order(
            trading_symbol=symbol,
            quantity=quantity,
            validity=groww.VALIDITY_DAY,
            exchange=groww.EXCHANGE_NSE,
            segment=groww.SEGMENT_CASH,
            product=product,
            order_type=groww.ORDER_TYPE_MARKET,
            transaction_type=groww.TRANSACTION_TYPE_SELL
        )
        print(f"  Sell Order: {order}")

    except Exception as e:
        print(f"  SELL FAILED {symbol}: {e}")


# ====================
# MAIN STRATEGY
# ====================

def run():
    global trades_today
    trades_today = 0

    print("=" * 50)
    print("GROWW ALGO - MIDCAP/SMALLCAP + PORTFOLIO")
    print(f"Mode: {CONFIG['product_type']} | Max Trades: {CONFIG['max_trades_per_day']}")
    print(f"Capital/Trade: Rs {CONFIG['max_capital_per_trade']}")
    print(f"SL: {CONFIG['stop_loss_pct']}% | Target: {CONFIG['target_profit_pct']}%")
    print("=" * 50)

    # Phase 1: Review portfolio
    review_portfolio()

    # Phase 2: Scan market
    top_picks = scan_market()

    # Phase 3: Execute on top picks
    if top_picks:
        print("\n" + "=" * 50)
        print("EXECUTING TRADES")
        print("=" * 50)

        for pick in top_picks:
            if trades_today >= CONFIG["max_trades_per_day"]:
                break
            if pick["ltp"] > 0:
                print(f"\n>> {pick['symbol']} (Score: {pick['score']})")
                execute_buy(pick["symbol"], pick["ltp"])
                time.sleep(1)

    print("\n" + "=" * 50)
    print(f"DONE. Trades placed: {trades_today}")
    print("=" * 50)


# RUN
run()
