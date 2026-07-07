"""
Fetches portfolio data from Groww API and saves as JSON for the static dashboard.
Runs via GitHub Actions on a schedule.
"""

import json
import os
import time
from datetime import datetime

import requests
from growwapi import GrowwAPI

# Config
SECTOR_THEMES = {
    "defence": {"score": 5, "reason": "Defence budget & Make in India"},
    "railways": {"score": 5, "reason": "Railway modernization"},
    "infrastructure": {"score": 4, "reason": "PM Gati Shakti & NIP"},
    "renewable_energy": {"score": 4, "reason": "Green energy & PLI"},
    "electronics_mfg": {"score": 4, "reason": "Semiconductor & PLI"},
    "ev_auto": {"score": 4, "reason": "FAME subsidy & EV push"},
    "pharma": {"score": 3, "reason": "Healthcare expansion"},
    "fintech": {"score": 3, "reason": "Digital India"},
    "power_energy": {"score": 4, "reason": "Power sector capex"},
    "metals": {"score": 3, "reason": "Infrastructure demand"},
    "fmcg": {"score": 2, "reason": "Consumption growth"},
    "auto": {"score": 3, "reason": "Auto demand recovery"},
    "agriculture": {"score": 3, "reason": "MSP hikes & agri fund"},
    "tourism": {"score": 3, "reason": "Travel boom"},
}

STOCK_SECTOR = {
    "TATAPOWER": "renewable_energy", "SUZLON": "renewable_energy",
    "RECLTD": "power_energy", "PFC": "power_energy",
    "POWERGRID": "power_energy", "IRFC": "railways",
    "TATASTEEL": "metals", "HINDCOPPER": "metals", "VEDL": "metals",
    "EXIDEIND": "ev_auto", "OLAELEC": "ev_auto", "UNOMINDA": "ev_auto",
    "JSWINFRA": "infrastructure", "NETWEB": "electronics_mfg",
    "ITCHOTELS": "tourism", "ITC": "fmcg", "GODREJCP": "fmcg",
    "HDFCBANK": "fintech", "BAJAJFINSV": "fintech", "IIFL": "fintech",
    "TATAMOTORS": "auto", "HYUNDAI": "auto", "TITAN": "fmcg",
    "TRENT": "fmcg", "COROMANDEL": "agriculture", "SUMICHEM": "agriculture",
    "ONGC": "power_energy", "IOC": "power_energy",
}

GENZ_THEMES = [
    {
        "theme": "AI & Semiconductors",
        "emoji": "🤖",
        "global_trigger": "NVIDIA rally, ChatGPT boom, global AI capex surge",
        "stocks": ["NETWEB", "DIXON", "KAYNES", "PERSISTENT", "LTTS"]
    },
    {
        "theme": "EV & Clean Mobility",
        "emoji": "⚡",
        "global_trigger": "Tesla expansion, EU ICE ban 2035, lithium demand",
        "stocks": ["OLAELEC", "EXIDEIND", "TATAMOTORS", "OLECTRA", "UNOMINDA"]
    },
    {
        "theme": "Green Energy & Climate",
        "emoji": "🌍",
        "global_trigger": "COP targets, US IRA spending, green hydrogen push",
        "stocks": ["SUZLON", "TATAPOWER", "NHPC", "SJVN"]
    },
    {
        "theme": "Digital Payments & Fintech",
        "emoji": "💳",
        "global_trigger": "UPI global expansion, CBDC rollouts, cashless economy",
        "stocks": ["BAJAJFINSV", "IIFL", "IDFCFIRSTB"]
    },
    {
        "theme": "Space & Defence Tech",
        "emoji": "🚀",
        "global_trigger": "SpaceX launches, geopolitical tensions, drone warfare",
        "stocks": ["HAL", "BEL", "MAZAGON", "BDL", "COCHINSHIP"]
    },
    {
        "theme": "Digital Health & Pharma",
        "emoji": "🧬",
        "global_trigger": "GLP-1 drug boom, telemedicine growth, AI diagnostics",
        "stocks": ["LALPATHLAB", "MAXHEALTH", "LAURUSLABS", "AUROPHARMA"]
    },
    {
        "theme": "Creator Economy & Digital",
        "emoji": "🎮",
        "global_trigger": "YouTube India #1, gaming boom, D2C brands",
        "stocks": ["SAGILITY", "ETERNAL", "SWIGGY", "VBL"]
    },
    {
        "theme": "Infrastructure & Smart Cities",
        "emoji": "🏗️",
        "global_trigger": "India fastest growing G20, urbanization, $1.5T infra plan",
        "stocks": ["JSWINFRA", "NCC", "NBCC", "RVNL", "IRFC"]
    },
]


def get_sector_info(symbol):
    sector = STOCK_SECTOR.get(symbol, "")
    if sector in SECTOR_THEMES:
        return sector, SECTOR_THEMES[sector]["score"], SECTOR_THEMES[sector]["reason"]
    return "", 0, ""


def fetch_holdings(groww):
    """Fetch portfolio holdings."""
    print("Fetching holdings...")
    try:
        holdings = groww.get_holdings_for_user()
        if not holdings or "holdings" not in holdings:
            return []

        result = []
        for h in holdings["holdings"]:
            symbol = h.get("trading_symbol", "")
            qty = h.get("quantity", 0)
            avg_price = h.get("average_price", 0)
            invested = avg_price * qty
            sector, sec_score, sec_reason = get_sector_info(symbol)

            result.append({
                "symbol": symbol,
                "quantity": int(qty),
                "avg_price": round(avg_price, 2),
                "invested": round(invested, 2),
                "sector": sector,
                "sector_score": sec_score,
                "sector_reason": sec_reason,
                "exchanges": h.get("tradable_exchanges", []),
            })

        result.sort(key=lambda x: x["invested"], reverse=True)
        print(f"  Found {len(result)} holdings")
        return result

    except Exception as e:
        print(f"  Holdings error: {e}")
        return []


def fetch_analysis(groww, holdings):
    """Analyze holdings for buy/sell hints using historical data."""
    print("Running analysis...")
    buy_hints = []
    sell_hints = []
    neutral = []

    for h in holdings:
        symbol = h["symbol"]
        avg_price = h["avg_price"]
        qty = h["quantity"]
        exchanges = h.get("exchanges", ["NSE"])

        if qty <= 0 or avg_price <= 0:
            continue

        exchange = "NSE" if "NSE" in exchanges else "BSE"

        try:
            from datetime import timedelta
            end_date = datetime.now()
            start_date_1y = end_date - timedelta(days=365)

            candles = groww.get_historical_candles(
                trading_symbol=symbol,
                exchange=exchange,
                segment=groww.SEGMENT_CASH,
                interval=groww.CANDLE_INTERVAL_DAY,
                from_date=start_date_1y.strftime("%Y-%m-%d"),
                to_date=end_date.strftime("%Y-%m-%d")
            )

            if not candles or len(candles) < 20:
                neutral.append({
                    "symbol": symbol, "qty": qty, "avg_price": avg_price,
                    "hint": "NO DATA", "reason": "Insufficient data"
                })
                continue

            closes_1y = [c.get("close", c.get("ltp", 0)) for c in candles if c.get("close", c.get("ltp", 0)) > 0]
            closes_6m = closes_1y[len(closes_1y)//2:]

            if not closes_1y or not closes_6m:
                continue

            current_price = closes_1y[-1]
            high_1y = max(closes_1y)
            low_6m = min(closes_6m)
            avg_6m = sum(closes_6m) / len(closes_6m)

            pnl_pct = ((current_price - avg_price) / avg_price) * 100
            from_high_pct = ((current_price - high_1y) / high_1y) * 100
            from_low_pct = ((current_price - low_6m) / low_6m) * 100

            sector, sec_score, sec_reason = get_sector_info(symbol)

            stock_data = {
                "symbol": symbol,
                "qty": qty,
                "avg_price": avg_price,
                "current_price": round(current_price, 2),
                "pnl_pct": round(pnl_pct, 1),
                "high_1y": round(high_1y, 2),
                "low_6m": round(low_6m, 2),
                "from_high_pct": round(from_high_pct, 1),
                "from_low_pct": round(from_low_pct, 1),
                "sector": sector,
                "sector_score": sec_score,
            }

            # SELL hint: within 5% of 1-year high
            if from_high_pct >= -5:
                stock_data["hint"] = "SELL"
                stock_data["reason"] = f"Near 1Y high ({high_1y}). Only {abs(from_high_pct):.1f}% below peak."
                if pnl_pct > 10:
                    stock_data["reason"] += f" Up {pnl_pct:.1f}%!"
                sell_hints.append(stock_data)

            # BUY hint: within 10% of 6-month low
            elif from_low_pct <= 10 and current_price < avg_6m:
                stock_data["hint"] = "BUY"
                stock_data["reason"] = f"Near 6M low ({low_6m}). Only {from_low_pct:.1f}% above bottom."
                if sec_score >= 3:
                    stock_data["reason"] += f" Strong sector: {sec_reason}"
                buy_hints.append(stock_data)

            else:
                stock_data["hint"] = "HOLD"
                stock_data["reason"] = f"{from_high_pct:.1f}% from 1Y high, {from_low_pct:.1f}% from 6M low"
                neutral.append(stock_data)

        except Exception as e:
            neutral.append({
                "symbol": symbol, "qty": qty, "avg_price": avg_price,
                "hint": "ERROR", "reason": str(e)
            })

        time.sleep(0.3)

    print(f"  Sell hints: {len(sell_hints)}, Buy hints: {len(buy_hints)}, Hold: {len(neutral)}")
    return {
        "sell_hints": sell_hints,
        "buy_hints": buy_hints,
        "neutral": neutral,
        "summary": {
            "total": len(sell_hints) + len(buy_hints) + len(neutral),
            "sell_count": len(sell_hints),
            "buy_count": len(buy_hints),
            "hold_count": len(neutral),
        }
    }


def fetch_recommendations(groww):
    """Scan midcap/smallcap for recommendations."""
    print("Scanning recommendations...")
    scan_list = [
        "HAL", "BEL", "RVNL", "IRCTC", "DIXON", "KAYNES",
        "NCC", "NBCC", "NHPC", "SJVN", "OLECTRA",
        "PERSISTENT", "COFORGE", "LTTS", "LAURUSLABS",
    ]

    results = []
    for symbol in scan_list:
        try:
            quote = groww.get_quote(
                trading_symbol=symbol,
                exchange=groww.EXCHANGE_NSE,
                segment=groww.SEGMENT_CASH
            )

            ltp = quote.get("ltp", 0)
            open_p = quote.get("open", 0)
            close = quote.get("close", 0)
            high = quote.get("high", 0)
            low = quote.get("low", 0)

            if ltp == 0:
                continue

            score = 0
            signals = []

            if open_p > 0 and close > 0:
                gap = ((open_p - close) / close) * 100
                if gap >= 2:
                    score += 2
                    signals.append(f"Gap Up +{gap:.1f}%")

            if ltp > open_p > 0 and ltp > close > 0:
                score += 1
                signals.append("Momentum")

            if high > low > 0:
                body = abs(ltp - open_p)
                rng = high - low
                if ltp > open_p and rng > 0 and body > 0.6 * rng:
                    score += 1
                    signals.append("Bullish")

            sector, sec_score, sec_reason = get_sector_info(symbol)
            if sec_score > 0:
                score += sec_score
                signals.append(sec_reason)

            if score >= 3:
                results.append({
                    "symbol": symbol,
                    "ltp": round(ltp, 2),
                    "score": score,
                    "signals": signals,
                    "sector": sector,
                    "change_pct": round(((ltp - close) / close) * 100, 2) if close > 0 else 0,
                })

        except Exception:
            pass
        time.sleep(0.3)

    results.sort(key=lambda x: x["score"], reverse=True)
    print(f"  Found {len(results)} recommendations")
    return results[:10]


def fetch_genz_data(groww):
    """Get live prices for GenZ/Market Picks themes."""
    print("Fetching Market Picks data...")
    themes_data = []

    for theme in GENZ_THEMES:
        stocks = []
        for symbol in theme["stocks"]:
            stock_entry = {"symbol": symbol, "reason": "", "ltp": 0, "change_pct": 0}

            try:
                quote = groww.get_quote(
                    trading_symbol=symbol,
                    exchange=groww.EXCHANGE_NSE,
                    segment=groww.SEGMENT_CASH
                )
                stock_entry["ltp"] = quote.get("ltp", 0)
                close = quote.get("close", 0)
                if close > 0 and stock_entry["ltp"] > 0:
                    stock_entry["change_pct"] = round(((stock_entry["ltp"] - close) / close) * 100, 2)
            except Exception:
                pass

            # Add reason based on symbol
            _, _, reason = get_sector_info(symbol)
            stock_entry["reason"] = reason
            stocks.append(stock_entry)
            time.sleep(0.2)

        themes_data.append({
            "theme": theme["theme"],
            "emoji": theme["emoji"],
            "global_trigger": theme["global_trigger"],
            "stocks": stocks
        })

    print(f"  Fetched {len(themes_data)} themes")
    return themes_data


def main():
    api_key = os.environ.get("GROWW_API_KEY", "")
    secret = os.environ.get("GROWW_SECRET", "")

    if not api_key or not secret:
        print("ERROR: GROWW_API_KEY and GROWW_SECRET env vars required")
        return

    print("=" * 50)
    print("STOCKPULSEIND - DATA FETCHER")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 50)

    # Connect
    print("\nConnecting to Groww API...")
    access_token = GrowwAPI.get_access_token(api_key=api_key, secret=secret)
    groww = GrowwAPI(access_token)
    print("Connected!")

    # Fetch all data
    holdings = fetch_holdings(groww)
    analysis = fetch_analysis(groww, holdings)
    recommendations = fetch_recommendations(groww)
    genz = fetch_genz_data(groww)

    # Build output JSON
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "holdings": {"holdings": holdings, "count": len(holdings)},
        "analysis": analysis,
        "recommendations": {"recommendations": recommendations},
        "genz": {"themes": genz},
    }

    # Write to docs/ for GitHub Pages
    os.makedirs("docs", exist_ok=True)
    output_path = os.path.join("docs", "data.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nData written to {output_path}")
    print(f"Holdings: {len(holdings)}")
    print(f"Analysis: {analysis['summary']}")
    print(f"Recommendations: {len(recommendations)}")
    print(f"Market Picks themes: {len(genz)}")
    print("DONE")


if __name__ == "__main__":
    main()
