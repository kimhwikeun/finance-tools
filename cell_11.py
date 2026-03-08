# SECTION 8: MAIN PIPELINE + WATCHLIST
# ============================================================================

def run_full(ti, portfolio_text="", target_alloc_text="", progress=gr.Progress()):
    """Execute the full 8-stage analysis pipeline. Now portfolio-aware."""
    tk = ti.strip().upper()
    if not tk:
        return "Enter a ticker.", ""

    try:
        # --- Parse portfolio if provided ---
        portfolio = parse_portfolio(portfolio_text)
        if portfolio:
            log.info(f"Portfolio parsed: {len(portfolio['holdings'])} holdings, {portfolio['cash_pct']:.1f}% cash")

        # --- Parse target allocation ---
        target_alloc = None
        if target_alloc_text and target_alloc_text.strip():
            try:
                target_alloc = float(target_alloc_text.strip().replace('%', ''))
                log.info(f"User target allocation: {target_alloc:.1f}%")
            except ValueError:
                log.warning(f"Could not parse target allocation: {target_alloc_text}")

        # --- Stage 1: Data + ATR ---
        progress(0.03, "Stage 1/8: Data + ATR...")
        df, info, err = get_stock_data(tk)
        if err:
            return f"Error: {err}", ""

        etf = is_etf(info)
        nm = info.get("longName", tk)
        sector = info.get("sector", info.get("category", "Unknown"))

        progress(0.07, "Calculating indicators...")
        df = calculate_indicators(df)
        latest = df.iloc[-1]

        sups, ress = get_support_resistance(df)
        fibs, fh, fl = get_fibonacci_levels(df)
        atr_val = latest["ATR"]
        atr_pct = (atr_val / latest["Close"]) * 100

        # OBV trend detection
        obv_bullish = latest["OBV"] > latest["OBV_MA20"]

        tech = {
            "price": latest["Close"],
            "ma20": latest["MA20"],
            "ma50": latest["MA50"],
            "ma200": latest["MA200"],
            "rsi": latest["RSI"],
            "macd": latest["MACD"],
            "signal": latest["Signal"],
            "bb_upper": latest["BB_Upper"],
            "bb_lower": latest["BB_Lower"],
            "bb_mid": latest["BB_Mid"],
            "vol_ratio": (latest["Volume"] / latest["Vol_MA20"]
                          if latest["Vol_MA20"] > 0 else 1),
            "stoch_k": latest["Stoch_K"],
            "stoch_d": latest["Stoch_D"],
            "vwap": latest["VWAP"],
            "supports": sups,
            "resistances": ress,
            "fib_levels": fibs,
            "fib_high": fh,
            "fib_low": fl,
            "atr": atr_val,
            "atr_pct": atr_pct,
            "obv_bullish": obv_bullish,
        }

        # fd is now set below after SEC data is fetched (get_enhanced_fundamentals)

        # --- Parallel: F&G, Earnings Proximity, Sector RS, SEC Filing Data ---
        progress(0.10, "Fear & Greed + Sector + SEC Filings...")
        with ThreadPoolExecutor(max_workers=4) as ex:
            fut_fg   = ex.submit(get_fear_greed)
            fut_earn = ex.submit(get_earnings_proximity, tk) if not etf else None
            fut_rs   = ex.submit(get_relative_sector_strength, tk, info, df) if not etf else None
            fut_sec  = ex.submit(get_sec_filing_data, tk, etf) if not etf else None
        fg        = fut_fg.result()
        earn_prox = fut_earn.result() if fut_earn else (None, "N/A")
        rs        = fut_rs.result() if fut_rs else None
        sec_data  = fut_sec.result() if fut_sec else None

        # Build enhanced fundamentals (yfinance snapshot + SEC deep data)
        fd, sec_context = "", ""  # safe defaults in case get_enhanced_fundamentals raises
        fd, sec_context = get_enhanced_fundamentals(info, sec_data, etf)

        # --- Portfolio enrichment ---
        portfolio_ctx = ""
        cash_rec = None
        risk_scenarios_text = ""
        if portfolio:
            progress(0.12, "Enriching portfolio data...")
            portfolio = enrich_portfolio(portfolio)
            portfolio = compute_new_ticker_correlations(portfolio, tk)
            portfolio_ctx = format_portfolio_context(portfolio, new_ticker=tk)

            # Append user's target allocation to context
            if target_alloc is not None:
                portfolio_ctx += f"\n\nUSER'S PROPOSED ALLOCATION: {target_alloc:.1f}% for {tk}"
                portfolio_ctx += f"\nThe PM MUST evaluate whether {target_alloc:.1f}% is appropriate given ATR, portfolio concentration, and market regime. Agree, adjust, or reject with reasoning."

            # Cash recommendation
            cash_rec = recommend_cash_position(fg, portfolio, tech)

            # Risk scenarios — use target_alloc if provided, else ATR-based default
            scenario_alloc = target_alloc if target_alloc is not None else 3.0
            if target_alloc is None:
                if tech["atr_pct"] < 2:
                    scenario_alloc = 4.0
                elif tech["atr_pct"] > 4:
                    scenario_alloc = 1.5
            risk_scenarios_text = run_risk_scenarios(tech, portfolio, scenario_alloc, info)
        elif target_alloc is not None:
            # No portfolio but user gave a target — still run risk scenarios without portfolio context
            portfolio_ctx = f"USER'S PROPOSED ALLOCATION: {target_alloc:.1f}% for {tk}\nNo current portfolio provided. The PM should evaluate whether {target_alloc:.1f}% is appropriate given ATR and market conditions."
            risk_scenarios_text = run_risk_scenarios(tech, None, target_alloc, info)

        progress(0.13, "Chart...")
        chart = chart_to_b64(plot_charts(df, tk))

        progress(0.16, "Backtesting...")
        bt = run_backtest(df, tech)

        # --- Stages 2-5: 4x Gemini in parallel ---
        progress(0.22, "Stages 2-5: 4x Gemini parallel...")
        with ThreadPoolExecutor(max_workers=4) as ex:
            fut_research = ex.submit(gemini_research, tk, nm, fd, etf, sec_context)
            fut_macro = ex.submit(gemini_macro, tk, nm, sector, etf)
            fut_earnings = ex.submit(gemini_earnings, tk, nm, etf)
            fut_insider = ex.submit(gemini_insider, tk, nm, etf)

            research = fut_research.result()
            macro = fut_macro.result()
            earnings = fut_earnings.result()
            insider = fut_insider.result()

        # --- Stage 6: Trader ---
        progress(0.50, "Stage 6/8: Trader (Claude)...")
        trader = claude_trader(tk, nm, tech, fd, research, macro, earnings,
                               insider, fg, bt, etf, rs=rs, portfolio_ctx=portfolio_ctx,
                               sec_context=sec_context)

        # --- Stage 7: Contrarian ---
        progress(0.65, "Stage 7/8: Contrarian (Gemini)...")
        contrarian = gemini_contrarian(tk, nm, tech, fd, research, trader, fg, etf, sec_context=sec_context)

        # --- Stage 8: Final PM ---
        progress(0.80, "Stage 8/8: Final PM (Claude)...")
        pm = claude_final_pm(tk, nm, tech, fd, research, macro, earnings, insider,
                             trader, contrarian, fg, bt, etf, rs=rs, earn_prox=earn_prox,
                             portfolio_ctx=portfolio_ctx, cash_rec=cash_rec,
                             risk_scenarios=risk_scenarios_text, sec_context=sec_context)

        # --- Build Report ---
        progress(0.95, "Building report...")
        html = build_report(tk, nm, tech, fd, research, macro, earnings, insider,
                            trader, contrarian, pm, bt, fg, chart, etf,
                            rs=rs, earn_prox=earn_prox, portfolio=portfolio,
                            cash_rec=cash_rec, risk_scenarios=risk_scenarios_text,
                            target_alloc=target_alloc, sec_data=sec_data)

        b64 = base64.b64encode(html.encode()).decode()
        progress(1.0, "Done!")

        # Earnings warning in status
        earn_status = ""
        if earn_prox and earn_prox[0] is not None and earn_prox[0] <= 14:
            earn_status = f" | ⚠️ Earnings in {earn_prox[0]}d"

        sec_status = ""
        if sec_data and sec_data.get("source", "N/A") != "N/A":
            sec_status = f" | SEC:{sec_data['source']}"
        status = f"**{nm} ({tk})** done (ATR:{atr_pct:.1f}%{earn_status}{sec_status})"

        output_html = f"""<div style="text-align:center;padding:20px">
<h2 style="color:#1a3a6e">{nm} ({tk})</h2>
<p>8 stages | ATR:{atr_pct:.1f}%{earn_status}</p>
<button onclick="var w=window.open();w.document.write(decodeURIComponent(escape(atob('{b64}'))));w.document.close();"
  style="background:#1a3a6e;color:#fff;border:none;padding:12px 24px;border-radius:8px;font-size:15px;cursor:pointer;margin:8px">
  Open Report</button><br>
<a href="data:text/html;base64,{b64}" download="{tk}_{datetime.now().strftime('%Y%m%d')}.html"
  style="color:#1565c0">Download HTML</a>
</div>
<script>var w=window.open();if(w){{w.document.write(decodeURIComponent(escape(atob('{b64}'))));w.document.close();}}</script>"""

        return status, output_html

    except Exception as e:
        log.error(f"Pipeline failed for {tk}: {e}", exc_info=True)
        return f"Error analyzing {tk}: {str(e)}", ""


def screen_tickers(tickers):
    """
    Run technical scorecard on a list of tickers.
    Returns (rows_text, close_data_dict) for correlation analysis.
    """
    header = f"{'Tick':<7} {'Price':<9} {'RSI':<6} {'ATR%':<6} {'Sharpe':<7} {'MA':<10} {'MACD':<7} Verdict"
    rows = [header, "-" * 75]
    close_data = {}

    for t in tickers:
        try:
            df, info, err = get_stock_data(t)
            if err:
                rows.append(f"{t:<7} ERROR: {err}")
                continue

            df = calculate_indicators(df)
            lat = df.iloc[-1]
            atr_pct = (lat["ATR"] / lat["Close"]) * 100

            if len(df) >= 60:
                close_data[t] = df["Close"].tail(60).pct_change().dropna().values

            if len(df) >= 60:
                rets = df["Close"].tail(60).pct_change().dropna()
                sharpe = (rets.mean() / (rets.std() + 1e-9)) * np.sqrt(252)
                sharpe_str = f"{sharpe:.2f}"
            else:
                sharpe_str = "N/A"

            score = sum([
                1 if lat["MA50"] > lat["MA200"] else 0,
                1 if 40 < lat["RSI"] < 65 else 0,
                1 if lat["MACD"] > lat["Signal"] else 0,
            ])

            ma_label = "Gold" if lat["MA50"] > lat["MA200"] else "Death"
            macd_label = "Bull" if lat["MACD"] > lat["Signal"] else "Bear"
            verdict = "BUY" if score == 3 else "HOLD" if score == 2 else "AVOID"

            rows.append(
                f"{t:<7} ${lat['Close']:<8.2f} {lat['RSI']:<6.1f} {atr_pct:<5.1f}% "
                f"{sharpe_str:<7} {ma_label:<10} {macd_label:<7} {verdict}"
            )

        except Exception as e:
            rows.append(f"{t:<7} ERROR: {str(e)[:30]}")
            log.warning(f"Scorecard scan failed for {t}: {e}")

    return rows, close_data


def correlation_warnings(close_data):
    """Generate correlation warnings for a set of tickers."""
    rows = []
    if len(close_data) >= 2:
        rows.append("")
        rows.append("CORRELATION WARNINGS (>0.80):")
        has_warning = False
        tklist = list(close_data.keys())
        for i in range(len(tklist)):
            for j in range(i + 1, len(tklist)):
                t1, t2 = tklist[i], tklist[j]
                try:
                    min_len = min(len(close_data[t1]), len(close_data[t2]))
                    corr = np.corrcoef(
                        close_data[t1][:min_len],
                        close_data[t2][:min_len]
                    )[0, 1]
                    if abs(corr) > 0.80:
                        rows.append(f"  ⚠️ {t1} & {t2}: {corr:.2f} — high correlation, limited diversification")
                        has_warning = True
                except Exception:
                    pass
        if not has_warning:
            rows.append("  ✅ No high correlations detected — good diversification.")
    return rows


def get_ai_recommendations(portfolio, fg):
    """
    Use Claude to suggest 5-8 tickers that complement the current portfolio.
    Considers sector gaps, market regime, and diversification.
    """
    if portfolio is None:
        return []

    holdings_str = ", ".join([f"{t} ({p:.0f}%)" for t, p in portfolio["holdings"].items()])
    cash_str = f"{portfolio['cash_pct']:.0f}%"

    sector_str = "None identified"
    if portfolio.get("sector_weights"):
        sector_str = ", ".join([f"{s}: {w:.0f}%" for s, w in
                                sorted(portfolio["sector_weights"].items(), key=lambda x: -x[1])])

    high_corr_str = "None"
    if portfolio.get("correlations"):
        high = {k: v for k, v in portfolio["correlations"].items() if abs(v) > 0.7}
        if high:
            high_corr_str = ", ".join([f"{k}={v:.2f}" for k, v in high.items()])

    beta_str = f"{portfolio['portfolio_beta']:.2f}" if portfolio.get("portfolio_beta") else "Unknown"

    fg_str = f"{fg['score']}/100 ({fg['label']})" if fg and fg.get("score") else "Unknown"

    # Identify index funds in holdings
    index_funds = portfolio.get("index_funds", {})
    index_str = ""
    if index_funds:
        idx_list = ", ".join([f"{t} ({p:.0f}%)" for t, p in index_funds.items()])
        index_str = f"\nIndex fund holdings (general equity exposure, NOT single-sector bets): {idx_list}"

    prompt = f"""You are a portfolio strategist. Analyze this portfolio and recommend 5-8 specific stock tickers that would COMPLEMENT it well.

CURRENT PORTFOLIO:
Holdings: {holdings_str}
Cash: {cash_str}
Sector exposure (adjusted): {sector_str}
High correlations: {high_corr_str}
Portfolio beta: {beta_str}
Market sentiment (Fear & Greed): {fg_str}{index_str}

IMPORTANT CONTEXT:
- Broad index funds like SPY, SPYM, VOO, QQQ provide diversified equity exposure across many sectors. Do NOT treat them as single-sector concentration.
- SPYM/SPY-type holdings are used as long-term equity parking vehicles (1+ year timeline) when cash is not in immediate use.
- SGOV and similar T-bill ETFs are already counted as cash above.

RULES:
- Do NOT recommend tickers already in the portfolio
- Do NOT recommend broad index funds or ETFs — suggest individual stocks or sector-specific ETFs
- Focus on filling SECTOR GAPS (underweight sectors)
- Consider the current market regime from Fear & Greed
- Mix of growth and value based on market conditions
- Include at least 1 defensive/low-correlation pick
- Include at least 1 high-conviction growth pick
- If portfolio is high-beta, suggest some low-beta names to balance
- If portfolio is concentrated in one sector, prioritize OTHER sectors

RESPOND WITH ONLY a JSON array of objects, no other text:
[
  {{"ticker": "XYZ", "reason": "one sentence why this fits"}},
  ...
]"""

    try:
        r = claude_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = r.content[0].text.strip()

        # Parse JSON — handle markdown fences
        text = text.replace("```json", "").replace("```", "").strip()
        recs = json.loads(text)

        # Filter out any tickers already in portfolio
        existing = set(portfolio["holdings"].keys())
        recs = [r for r in recs if r.get("ticker", "").upper() not in existing]

        return recs[:8]

    except Exception as e:
        log.error(f"AI recommendation failed: {e}")
        return []


def run_portfolio_review(portfolio_text, progress=gr.Progress()):
    """
    Portfolio review: scorecard on holdings, sector analysis,
    AI-recommended complementary tickers, and screening.
    """
    portfolio = parse_portfolio(portfolio_text)
    if portfolio is None or not portfolio["holdings"]:
        return "Enter your portfolio. Format: AAPL:15%, NVDA:10%, CASH:20%"

    output = []
    output.append("=" * 75)
    output.append("PORTFOLIO REVIEW")
    output.append("=" * 75)

    # --- Enrich portfolio ---
    progress(0.05, "Analyzing portfolio...")
    portfolio = enrich_portfolio(portfolio)

    # --- Scorecard on existing holdings ---
    progress(0.15, "Screening current holdings...")
    tickers = list(portfolio["holdings"].keys())
    output.append(f"\n📊 CURRENT HOLDINGS ({len(tickers)} positions + {portfolio['cash_pct']:.0f}% cash)")
    output.append("")

    rows, close_data = screen_tickers(tickers)
    output.extend(rows)

    # --- Correlation warnings ---
    output.extend(correlation_warnings(close_data))

    # --- Sector analysis ---
    output.append("")
    output.append("📁 SECTOR EXPOSURE:")
    if portfolio.get("sector_weights"):
        for sec, wt in sorted(portfolio["sector_weights"].items(), key=lambda x: -x[1]):
            bar = "█" * int(wt / 2)
            flag = " ⚠️ CONCENTRATED" if wt > 25 else ""
            output.append(f"  {sec:<35} {wt:5.1f}% {bar}{flag}")

    # Missing major sectors
    all_sectors = {"Technology", "Healthcare", "Financial Services", "Energy",
                   "Consumer Cyclical", "Consumer Defensive", "Industrials",
                   "Real Estate", "Utilities", "Communication Services", "Basic Materials"}
    held_sectors = set()
    for sec in portfolio.get("sector_weights", {}).keys():
        for s in all_sectors:
            if s.lower() in sec.lower():
                held_sectors.add(s)
    missing = all_sectors - held_sectors
    if missing:
        output.append(f"\n  Underweight / Missing: {', '.join(sorted(missing))}")

    # --- Portfolio beta ---
    if portfolio.get("portfolio_beta"):
        output.append(f"\n📈 Portfolio Beta: {portfolio['portfolio_beta']:.2f}")

    # --- Cash recommendation ---
    progress(0.30, "Market regime analysis...")
    fg = get_fear_greed()
    cash_rec = recommend_cash_position(fg, portfolio, {"atr_pct": 2.0})
    rec_cash, regime, trims = cash_rec

    output.append("")
    output.append(f"💰 CASH MANAGEMENT:")
    output.append(f"  Current cash: {portfolio['cash_pct']:.0f}%")
    output.append(f"  Recommended:  {rec_cash:.0f}%")
    output.append(f"  Regime: {regime}")

    if trims:
        output.append("  Suggested trims:")
        for t in trims:
            output.append(f"    {t['ticker']}: {t['current_pct']:.1f}% → {t['new_pct']:.1f}% (trim {t['trim_pct']:.1f}%)")

    # --- AI Recommendations ---
    progress(0.45, "AI generating recommendations...")
    output.append("")
    output.append("=" * 75)
    output.append("🤖 AI-RECOMMENDED ADDITIONS (Claude Sonnet 4.5)")
    output.append("=" * 75)

    recs = get_ai_recommendations(portfolio, fg)

    if recs:
        for i, rec in enumerate(recs, 1):
            ticker = rec.get("ticker", "?").upper()
            reason = rec.get("reason", "")
            output.append(f"  {i}. {ticker} — {reason}")

        # Screen the recommended tickers
        rec_tickers = [r["ticker"].upper() for r in recs if r.get("ticker")]
        if rec_tickers:
            progress(0.60, f"Screening {len(rec_tickers)} recommendations...")
            output.append("")
            output.append("📊 RECOMMENDATION SCORECARD:")
            output.append("")
            rec_rows, rec_close = screen_tickers(rec_tickers)
            output.extend(rec_rows)

            # Correlation of recs with existing portfolio
            all_close = {**close_data, **rec_close}
            output.append("")
            output.append("CORRELATION: RECOMMENDATIONS vs HOLDINGS:")
            for rec_t in rec_tickers:
                if rec_t not in all_close:
                    continue
                for hold_t in tickers:
                    if hold_t not in all_close:
                        continue
                    try:
                        min_len = min(len(all_close[rec_t]), len(all_close[hold_t]))
                        if min_len > 10:
                            corr = np.corrcoef(
                                all_close[rec_t][:min_len],
                                all_close[hold_t][:min_len]
                            )[0, 1]
                            if abs(corr) > 0.7:
                                flag = " ⚠️ HIGH" if abs(corr) > 0.8 else ""
                                output.append(f"  {rec_t} ↔ {hold_t}: {corr:.2f}{flag}")
                    except Exception:
                        pass
    else:
        output.append("  Could not generate recommendations. Try again.")

    progress(1.0, "Done!")
    output.append("")
    output.append("─" * 75)
    output.append("Use the Full Analysis tab to deep-dive any ticker above.")
    output.append("Educational purposes only. Not financial advice.")

    return "\n".join(output)


# ============================================================================
# SECTION 9: GRADIO UI
# ============================================================================

with gr.Blocks(title="AI Stock Analyzer", theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate")) as app:
    gr.Markdown(
        "# 📈 AI Stock Analyzer\n"
        "**Portfolio-Aware | Risk Scenarios | Cash Management | Multi-Agent AI**\n"
        "*8 stages | Gemini 2.5 Flash + Claude Sonnet 4.5 | ~30-45s*"
    )

    with gr.Tabs():
        with gr.Tab("🔍 Full Analysis"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Input & Settings")
                    ti = gr.Textbox(
                        label="Ticker Symbol",
                        placeholder="AAPL, NVDA, SPY...",
                    )
                    with gr.Accordion("💼 Portfolio Context (Optional)", open=False):
                        gr.Markdown(
                            "Enter your current holdings and cash position. Format: `TICKER:PCT%`.\n"
                            "Example: `AAPL:15%, NVDA:10%, MSFT:12%, CASH:20%`"
                        )
                        pi = gr.Textbox(
                            label="Current Portfolio",
                            placeholder="AAPL:15%, NVDA:10%, MSFT:12%, CASH:20%",
                            lines=3,
                        )
                        target_alloc = gr.Textbox(
                            label="Target Allocation % for New Ticker",
                            placeholder="e.g. 5",
                        )
                    ab = gr.Button("🚀 Run Analysis", variant="primary")
                    so = gr.Markdown("")
                
                with gr.Column(scale=3):
                    ro = gr.HTML("")
                    
            ab.click(fn=run_full, inputs=[ti, pi, target_alloc], outputs=[so, ro])
            ti.submit(fn=run_full, inputs=[ti, pi, target_alloc], outputs=[so, ro])

        with gr.Tab("💼 Portfolio Health"):
            gr.Markdown(
                "**Portfolio Health Check + AI Recommendations**\n"
                "Scores your current holdings, analyzes sector exposure, recommends cash targets, "
                "and uses Claude to suggest complementary tickers."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    port_input = gr.Textbox(
                        label="Current Portfolio",
                        placeholder="AAPL:15%, NVDA:10%, MSFT:12%, SGOV:20%",
                        lines=5,
                    )
                    port_btn = gr.Button("📊 Review Portfolio", variant="primary")
                with gr.Column(scale=3):
                    port_output = gr.Textbox(label="Portfolio Review Results", lines=30, interactive=False)
            
            port_btn.click(fn=run_portfolio_review, inputs=[port_input], outputs=[port_output])

        with gr.Tab("Guide"):
            gr.Markdown("""## Pipeline
| # | Role | Model | Cost |
|---|------|-------|------|
| 1 | Data + ATR + Chart + Backtest + Sector RS | Local | Free |
| 1b | Portfolio enrichment + correlations + risk scenarios | Local + yfinance | Free |
| 1c | SEC Filing data (10-K/10-Q financials + MD&A + Risk Factors) | edgartools + SEC EDGAR | Free |
| 2-5 | Research, Macro, Earnings, Insider (PARALLEL) | Gemini 2.5 Flash | Free* |
| 6 | Trader (portfolio-aware) | Claude Sonnet 4.5 | ~$0.04 |
| 7 | Contrarian + Fatal Flaw | Gemini 2.5 Flash | Free* |
| 8 | Final PM (portfolio + cash + risk aware) | Claude Sonnet 4.5 | ~$0.04 |

*Free within daily grounding quota (500 RPD). Cached: repeat analyses same day = $0.

## ATR Position Sizing
| Daily ATR% | Max Position Size |
|------------|-------------------|
| < 2% | 3-5% of portfolio |
| 2-3% | 2-4% of portfolio |
| 3-4% | 1-3% of portfolio |
| > 4% | Max 1-2% of portfolio |

## Cash Target by Market Regime
| Fear & Greed | Recommended Cash | Regime |
|-------------|-----------------|--------|
| 0-20 (Extreme Fear) | 5% | Deploy aggressively (contrarian) |
| 20-35 (Fear) | 10% | Cautious accumulation |
| 35-55 (Neutral) | 15% | Standard buffer |
| 55-75 (Greed) | 20% | Raise cash, overextended |
| 75-100 (Extreme Greed) | 30% | Maximum defensiveness |

*Adjusted for portfolio beta and sector concentration.*

## New Features
- **Portfolio-Aware Analysis**: Enter holdings, get sizing relative to existing exposure
- **Cash Management**: Dynamic cash target based on F&G, beta, sector concentration
- **Trim Recommendations**: Suggests which positions to trim to meet cash target
- **Risk Scenario Module**: Stress tests with beta-adjusted drawdowns
- **Gemini Research Cache**: 24hr cache saves grounding costs on repeat analyses
- **Sector Relative Strength**: Compares stock vs sector ETF over 20/60/120 days
- **Earnings Proximity Warning**: Flags earnings within 14 days
- **OBV Chart Panel**: On-Balance Volume for volume confirmation
- **Portfolio Tab**: Health check on holdings, sector gap analysis, AI-recommended additions
- **Correlation Warnings**: Flags highly correlated pairs in portfolio and recommendations
- **SEC Filing Integration**: Multi-year XBRL financials + MD&A narrative + Risk Factors from 10-K/10-Q (via edgartools, free, no API key)

*Educational purposes only. Not financial advice.*""")

print("\n🚀 AI Stock Analyzer")
print("Launching Gradio interface...\n")
app.launch(share=False, debug=False, auth=(os.environ.get("GRADIO_USERNAME", "hkim"), os.environ.get("GRADIO_PASSWORD", "test123")))
