"""
Groww Portfolio Dashboard
Run: python3 dashboard.py
Open: http://localhost:5050
"""

import os
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
from growwapi import GrowwAPI

# Load .env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

app = Flask(__name__)
CORS(app)

# Groww API setup
api_key = os.environ.get("GROWW_API_KEY", "")
secret = os.environ.get("GROWW_SECRET", "")

# Sector themes
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


def get_groww_client():
    access_token = GrowwAPI.get_access_token(api_key=api_key, secret=secret)
    return GrowwAPI(access_token)


def get_sector_info(symbol):
    sector = STOCK_SECTOR.get(symbol, "")
    if sector in SECTOR_THEMES:
        return sector, SECTOR_THEMES[sector]["score"], SECTOR_THEMES[sector]["reason"]
    return "", 0, ""


# ==================== API ROUTES ====================

@app.route("/api/holdings")
def api_holdings():
    """Fetch portfolio holdings with P&L"""
    try:
        groww = get_groww_client()
        holdings = groww.get_holdings_for_user()

        if not holdings or "holdings" not in holdings:
            return jsonify({"error": "No holdings found"}), 404

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

        # Sort by invested amount descending
        result.sort(key=lambda x: x["invested"], reverse=True)
        return jsonify({"holdings": result, "count": len(result)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analysis")
def api_analysis():
    """Analyze holdings: 6-month low (BUY hint), 1-year high (SELL hint)"""
    try:
        groww = get_groww_client()
        holdings = groww.get_holdings_for_user()

        if not holdings or "holdings" not in holdings:
            return jsonify({"error": "No holdings"}), 404

        buy_hints = []  # Near 6-month low
        sell_hints = []  # Near 1-year high
        neutral = []

        for h in holdings["holdings"]:
            symbol = h.get("trading_symbol", "")
            qty = h.get("quantity", 0)
            avg_price = h.get("average_price", 0)
            exchanges = h.get("tradable_exchanges", [])

            if qty <= 0 or avg_price <= 0:
                continue

            # Get historical candle data
            exchange = "NSE" if "NSE" in exchanges else "BSE"

            try:
                # 1 year of daily candles
                end_date = datetime.now()
                start_date_1y = end_date - timedelta(days=365)
                start_date_6m = end_date - timedelta(days=180)

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
                        "symbol": symbol,
                        "qty": int(qty),
                        "avg_price": round(avg_price, 2),
                        "hint": "NO DATA",
                        "reason": "Insufficient historical data"
                    })
                    continue

                # Extract close prices
                closes_1y = [c.get("close", c.get("ltp", 0)) for c in candles if c.get("close", c.get("ltp", 0)) > 0]
                closes_6m = closes_1y[len(closes_1y)//2:]  # Approx last 6 months

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
                    "qty": int(qty),
                    "avg_price": round(avg_price, 2),
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
                        stock_data["reason"] += f" You're up {pnl_pct:.1f}%!"
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
                    "symbol": symbol,
                    "qty": int(qty),
                    "avg_price": round(avg_price, 2),
                    "hint": "ERROR",
                    "reason": str(e)
                })

            time.sleep(0.3)

        return jsonify({
            "sell_hints": sell_hints,
            "buy_hints": buy_hints,
            "neutral": neutral,
            "summary": {
                "total": len(sell_hints) + len(buy_hints) + len(neutral),
                "sell_count": len(sell_hints),
                "buy_count": len(buy_hints),
                "hold_count": len(neutral),
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommendations")
def api_recommendations():
    """New stock recommendations from scan universe"""
    try:
        groww = get_groww_client()
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
                high = quote.get("high", 0)
                low = quote.get("low", 0)
                close = quote.get("close", 0)
                volume = quote.get("volume", 0)

                if ltp == 0:
                    continue

                score = 0
                signals = []

                # Gap up
                if open_p > 0 and close > 0:
                    gap = ((open_p - close) / close) * 100
                    if gap >= 2:
                        score += 2
                        signals.append(f"Gap Up +{gap:.1f}%")

                # Momentum
                if ltp > open_p > 0 and ltp > close > 0:
                    score += 1
                    signals.append("Momentum")

                # Bullish candle
                if high > low > 0:
                    body = abs(ltp - open_p)
                    rng = high - low
                    if ltp > open_p and rng > 0 and body > 0.6 * rng:
                        score += 1
                        signals.append("Bullish")

                # Sector
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
        return jsonify({"recommendations": results[:10]})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/genz")
def api_genz():
    """
    GenZ Mature Picks - Global news & trend-driven stock suggestions.
    Themes based on worldwide trends: AI, EVs, space, crypto-adjacent,
    clean energy, digital health, gaming, creator economy, etc.
    """
    GENZ_THEMES = [
        {
            "theme": "AI & Semiconductors",
            "emoji": "\ud83e\udd16",
            "global_trigger": "NVIDIA rally, ChatGPT boom, global AI capex surge",
            "stocks": [
                {"symbol": "NETWEB", "reason": "AI server manufacturer, India's GPU infra play"},
                {"symbol": "DIXON", "reason": "Electronics EMS, potential AI hardware assembly"},
                {"symbol": "KAYNES", "reason": "Semiconductor packaging & PCB for AI chips"},
                {"symbol": "PERSISTENT", "reason": "AI/ML services for global enterprises"},
                {"symbol": "LTTS", "reason": "Engineering R&D for AI-edge devices"},
            ]
        },
        {
            "theme": "EV & Clean Mobility",
            "emoji": "\u26a1",
            "global_trigger": "Tesla expansion, EU ICE ban 2035, lithium demand",
            "stocks": [
                {"symbol": "OLAELEC", "reason": "India's EV two-wheeler leader"},
                {"symbol": "EXIDEIND", "reason": "Lithium-ion battery gigafactory planned"},
                {"symbol": "TATAMOTORS", "reason": "Tata EV market share leader"},
                {"symbol": "OLECTRA", "reason": "Electric bus manufacturer, govt contracts"},
                {"symbol": "UNOMINDA", "reason": "EV components & auto electronics"},
            ]
        },
        {
            "theme": "Green Energy & Climate",
            "emoji": "\ud83c\udf0d",
            "global_trigger": "COP targets, US IRA spending, green hydrogen push",
            "stocks": [
                {"symbol": "SUZLON", "reason": "Wind energy revival, order book surge"},
                {"symbol": "TATAPOWER", "reason": "Solar + EV charging + renewables"},
                {"symbol": "NHPC", "reason": "Hydropower + green energy certificates"},
                {"symbol": "SJVN", "reason": "Solar & wind expansion beyond hydro"},
            ]
        },
        {
            "theme": "Digital Payments & Fintech",
            "emoji": "\ud83d\udcb3",
            "global_trigger": "UPI global expansion, CBDC rollouts, cashless economy",
            "stocks": [
                {"symbol": "BAJAJFINSV", "reason": "Fintech + insurance super-app"},
                {"symbol": "IIFL", "reason": "Digital lending & wealth management"},
                {"symbol": "CCAVENUE", "reason": "Payment gateway infrastructure"},
                {"symbol": "IDFCFIRSTB", "reason": "Digital-first banking model"},
            ]
        },
        {
            "theme": "Space & Defence Tech",
            "emoji": "\ud83d\ude80",
            "global_trigger": "SpaceX launches, geopolitical tensions, drone warfare",
            "stocks": [
                {"symbol": "HAL", "reason": "Fighter jets + helicopter manufacturing"},
                {"symbol": "BEL", "reason": "Radar, EW systems, defense electronics"},
                {"symbol": "MAZAGON", "reason": "Submarine & warship builder"},
                {"symbol": "BDL", "reason": "Missile systems, guided munitions"},
            ]
        },
        {
            "theme": "Digital Health & Pharma",
            "emoji": "\ud83e\uddec",
            "global_trigger": "GLP-1 drug boom, telemedicine growth, AI diagnostics",
            "stocks": [
                {"symbol": "LALPATHLAB", "reason": "Diagnostic chain, preventive health trend"},
                {"symbol": "MAXHEALTH", "reason": "Hospital chain, medical tourism"},
                {"symbol": "LAURUSLABS", "reason": "API manufacturer, CDMO for global pharma"},
            ]
        },
        {
            "theme": "Creator Economy & Digital",
            "emoji": "\ud83c\udfae",
            "global_trigger": "YouTube India #1, gaming boom, D2C brands",
            "stocks": [
                {"symbol": "SAGILITY", "reason": "Digital services & tech outsourcing"},
                {"symbol": "ETERNAL", "reason": "Zomato - food delivery & quick commerce"},
                {"symbol": "SWIGGY", "reason": "Quick commerce & food-tech platform"},
                {"symbol": "VBL", "reason": "Varun Beverages - GenZ consumption"},
            ]
        },
        {
            "theme": "Infrastructure & Smart Cities",
            "emoji": "\ud83c\udfd7\ufe0f",
            "global_trigger": "India fastest growing G20, urbanization, $1.5T infra plan",
            "stocks": [
                {"symbol": "JSWINFRA", "reason": "Ports & logistics infrastructure"},
                {"symbol": "NCC", "reason": "Roads, buildings, metro construction"},
                {"symbol": "RVNL", "reason": "Railway infrastructure execution"},
                {"symbol": "IRFC", "reason": "Railway financing, stable dividend"},
            ]
        },
    ]

    # Try to get live prices
    try:
        groww = get_groww_client()
        for theme in GENZ_THEMES:
            for stock in theme["stocks"]:
                try:
                    quote = groww.get_quote(
                        trading_symbol=stock["symbol"],
                        exchange=groww.EXCHANGE_NSE,
                        segment=groww.SEGMENT_CASH
                    )
                    stock["ltp"] = quote.get("ltp", 0)
                    close = quote.get("close", 0)
                    if close > 0 and stock["ltp"] > 0:
                        stock["change_pct"] = round(((stock["ltp"] - close) / close) * 100, 2)
                    else:
                        stock["change_pct"] = 0
                except Exception:
                    stock["ltp"] = 0
                    stock["change_pct"] = 0
                time.sleep(0.15)
    except Exception:
        for theme in GENZ_THEMES:
            for stock in theme["stocks"]:
                stock["ltp"] = 0
                stock["change_pct"] = 0

    return jsonify({"themes": GENZ_THEMES})


# Old HTML removed - using templates/dashboard.html
_UNUSED = """
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f1117;
            color: #e1e5ea;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid #1e2330;
        }
        .header h1 {
            font-size: 24px;
            color: #00d09c;
        }
        .header .status {
            font-size: 13px;
            color: #6b7280;
        }
        .refresh-btn {
            background: #00d09c;
            color: #0f1117;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            font-size: 13px;
        }
        .refresh-btn:hover { background: #00b386; }

        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        .grid-full {
            grid-template-columns: 1fr;
        }

        .tile {
            background: #1a1f2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #2a3040;
        }
        .tile-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        .tile-header h2 {
            font-size: 16px;
            color: #9ca3af;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .tile-header .badge {
            font-size: 12px;
            padding: 3px 10px;
            border-radius: 12px;
            font-weight: 600;
        }
        .badge-sell { background: #ff4444; color: #fff; }
        .badge-buy { background: #00d09c; color: #0f1117; }
        .badge-hold { background: #3b4252; color: #9ca3af; }
        .badge-count { background: #2a3040; color: #e1e5ea; }

        .stock-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            border-radius: 8px;
            margin-bottom: 6px;
            transition: background 0.2s;
        }
        .stock-row:hover { background: #232838; }

        .stock-info { flex: 1; }
        .stock-symbol {
            font-weight: 600;
            font-size: 14px;
            color: #e1e5ea;
        }
        .stock-detail {
            font-size: 12px;
            color: #6b7280;
            margin-top: 2px;
        }
        .stock-hint {
            font-size: 11px;
            color: #9ca3af;
            margin-top: 3px;
            max-width: 300px;
        }

        .stock-values { text-align: right; }
        .stock-price {
            font-weight: 600;
            font-size: 14px;
        }
        .stock-pnl {
            font-size: 12px;
            margin-top: 2px;
        }
        .positive { color: #00d09c; }
        .negative { color: #ff4444; }

        .score-bar {
            display: inline-block;
            width: 40px;
            height: 6px;
            background: #2a3040;
            border-radius: 3px;
            overflow: hidden;
            margin-left: 8px;
        }
        .score-fill {
            height: 100%;
            border-radius: 3px;
            transition: width 0.3s;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #6b7280;
        }
        .spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #2a3040;
            border-top-color: #00d09c;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-right: 8px;
            vertical-align: middle;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .error-msg {
            background: #2a1a1a;
            border: 1px solid #ff4444;
            padding: 12px;
            border-radius: 8px;
            color: #ff6b6b;
            font-size: 13px;
        }

        .summary-cards {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }
        .summary-card {
            background: #1a1f2e;
            padding: 16px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid #2a3040;
        }
        .summary-card .value {
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .summary-card .label {
            font-size: 12px;
            color: #6b7280;
            text-transform: uppercase;
        }

        .sector-tag {
            display: inline-block;
            font-size: 10px;
            background: #2a3040;
            color: #9ca3af;
            padding: 2px 6px;
            border-radius: 4px;
            margin-left: 6px;
        }

        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
            .summary-cards { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Groww Portfolio Dashboard</h1>
        <div>
            <span class="status" id="last-updated"></span>
            <button class="refresh-btn" onclick="loadAll()">Refresh</button>
        </div>
    </div>

    <div class="summary-cards" id="summary-cards">
        <div class="summary-card"><div class="value" id="total-stocks">-</div><div class="label">Total Stocks</div></div>
        <div class="summary-card"><div class="value positive" id="buy-signals">-</div><div class="label">Buy Hints</div></div>
        <div class="summary-card"><div class="value negative" id="sell-signals">-</div><div class="label">Sell Hints</div></div>
        <div class="summary-card"><div class="value" id="hold-count">-</div><div class="label">Hold</div></div>
    </div>

    <div class="grid">
        <!-- SELL HINTS TILE -->
        <div class="tile">
            <div class="tile-header">
                <h2>Sell Hints (Near 1Y High)</h2>
                <span class="badge badge-sell" id="sell-badge">0</span>
            </div>
            <div id="sell-list"><div class="loading"><span class="spinner"></span>Loading...</div></div>
        </div>

        <!-- BUY HINTS TILE -->
        <div class="tile">
            <div class="tile-header">
                <h2>Buy Hints (Near 6M Low)</h2>
                <span class="badge badge-buy" id="buy-badge">0</span>
            </div>
            <div id="buy-list"><div class="loading"><span class="spinner"></span>Loading...</div></div>
        </div>
    </div>

    <div class="grid">
        <!-- MY PORTFOLIO TILE -->
        <div class="tile">
            <div class="tile-header">
                <h2>My Portfolio</h2>
                <span class="badge badge-count" id="portfolio-badge">0</span>
            </div>
            <div id="portfolio-list"><div class="loading"><span class="spinner"></span>Loading...</div></div>
        </div>

        <!-- RECOMMENDATIONS TILE -->
        <div class="tile">
            <div class="tile-header">
                <h2>New Recommendations</h2>
                <span class="badge badge-count" id="reco-badge">0</span>
            </div>
            <div id="reco-list"><div class="loading"><span class="spinner"></span>Loading...</div></div>
        </div>
    </div>

    <script>
        function renderStockRow(stock, type) {
            let priceHtml = '';
            let detailHtml = '';
            let hintHtml = '';

            if (type === 'portfolio') {
                const pnlClass = stock.pnl_pct >= 0 ? 'positive' : 'negative';
                priceHtml = `<div class="stock-price">&#8377;${stock.avg_price.toLocaleString()}</div>
                             <div class="stock-pnl ${pnlClass}">Qty: ${stock.quantity}</div>`;
                detailHtml = `Invested: &#8377;${stock.invested.toLocaleString()}`;
                if (stock.sector) detailHtml += ` <span class="sector-tag">${stock.sector}</span>`;
            }
            else if (type === 'sell' || type === 'buy') {
                const pnlClass = stock.pnl_pct >= 0 ? 'positive' : 'negative';
                priceHtml = `<div class="stock-price">&#8377;${stock.current_price}</div>
                             <div class="stock-pnl ${pnlClass}">${stock.pnl_pct > 0 ? '+' : ''}${stock.pnl_pct}%</div>`;
                detailHtml = `Avg: &#8377;${stock.avg_price} | Qty: ${stock.qty}`;
                hintHtml = stock.reason || '';
            }
            else if (type === 'reco') {
                const changeClass = stock.change_pct >= 0 ? 'positive' : 'negative';
                priceHtml = `<div class="stock-price">&#8377;${stock.ltp}</div>
                             <div class="stock-pnl ${changeClass}">${stock.change_pct > 0 ? '+' : ''}${stock.change_pct}%</div>`;
                detailHtml = `Score: ${stock.score}`;
                if (stock.sector) detailHtml += ` <span class="sector-tag">${stock.sector}</span>`;
                hintHtml = stock.signals ? stock.signals.join(', ') : '';
            }

            return `
                <div class="stock-row">
                    <div class="stock-info">
                        <div class="stock-symbol">${stock.symbol}</div>
                        <div class="stock-detail">${detailHtml}</div>
                        ${hintHtml ? `<div class="stock-hint">${hintHtml}</div>` : ''}
                    </div>
                    <div class="stock-values">${priceHtml}</div>
                </div>
            `;
        }

        async function loadHoldings() {
            try {
                const res = await fetch('/api/holdings');
                const data = await res.json();
                if (data.error) throw new Error(data.error);

                document.getElementById('portfolio-badge').textContent = data.count;
                document.getElementById('total-stocks').textContent = data.count;

                const html = data.holdings.map(s => renderStockRow(s, 'portfolio')).join('');
                document.getElementById('portfolio-list').innerHTML = html || '<p>No holdings</p>';
            } catch(e) {
                document.getElementById('portfolio-list').innerHTML = `<div class="error-msg">${e.message}</div>`;
            }
        }

        async function loadAnalysis() {
            try {
                const res = await fetch('/api/analysis');
                const data = await res.json();
                if (data.error) throw new Error(data.error);

                // Summary
                document.getElementById('buy-signals').textContent = data.summary.buy_count;
                document.getElementById('sell-signals').textContent = data.summary.sell_count;
                document.getElementById('hold-count').textContent = data.summary.hold_count;
                document.getElementById('sell-badge').textContent = data.summary.sell_count;
                document.getElementById('buy-badge').textContent = data.summary.buy_count;

                // Sell hints
                if (data.sell_hints.length > 0) {
                    document.getElementById('sell-list').innerHTML =
                        data.sell_hints.map(s => renderStockRow(s, 'sell')).join('');
                } else {
                    document.getElementById('sell-list').innerHTML = '<p style="color:#6b7280;padding:20px;">No stocks near 1-year high</p>';
                }

                // Buy hints
                if (data.buy_hints.length > 0) {
                    document.getElementById('buy-list').innerHTML =
                        data.buy_hints.map(s => renderStockRow(s, 'buy')).join('');
                } else {
                    document.getElementById('buy-list').innerHTML = '<p style="color:#6b7280;padding:20px;">No stocks near 6-month low</p>';
                }

            } catch(e) {
                document.getElementById('sell-list').innerHTML = `<div class="error-msg">${e.message}</div>`;
                document.getElementById('buy-list').innerHTML = `<div class="error-msg">${e.message}</div>`;
            }
        }

        async function loadRecommendations() {
            try {
                const res = await fetch('/api/recommendations');
                const data = await res.json();
                if (data.error) throw new Error(data.error);

                document.getElementById('reco-badge').textContent = data.recommendations.length;

                if (data.recommendations.length > 0) {
                    document.getElementById('reco-list').innerHTML =
                        data.recommendations.map(s => renderStockRow(s, 'reco')).join('');
                } else {
                    document.getElementById('reco-list').innerHTML = '<p style="color:#6b7280;padding:20px;">No recommendations (market may be closed)</p>';
                }
            } catch(e) {
                document.getElementById('reco-list').innerHTML = `<div class="error-msg">${e.message}</div>`;
            }
        }

        function loadAll() {
            document.getElementById('last-updated').textContent = 'Refreshing...';
            loadHoldings();
            loadAnalysis();
            loadRecommendations();
            setTimeout(() => {
                const now = new Date().toLocaleTimeString();
                document.getElementById('last-updated').textContent = `Last updated: ${now}`;
            }, 2000);
        }

        // Load on page open
        loadAll();

        // Auto-refresh every 5 minutes
        setInterval(loadAll, 5 * 60 * 1000);
    </script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    return render_template_string(open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "dashboard.html")
    ).read())


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  GROWW PORTFOLIO DASHBOARD")
    print("  Open: http://localhost:5050")
    print("=" * 50 + "\n")
    app.run(host="0.0.0.0", port=5050, debug=True)
