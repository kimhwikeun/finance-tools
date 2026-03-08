# CLAUDE.md — AI Stock Analyzer

## What This Project Is

A personal AI-powered stock analysis tool that runs as a Jupyter notebook (`Dual_AI_Stock_Analyzer.ipynb`) in Google Colab or Antigravity. It combines multiple AI models and financial data sources into an 8-stage analysis pipeline with a Gradio web UI. Built for personal investment research and portfolio management — not a production app.

## Architecture

**Dual-AI pipeline:**
- **Claude Sonnet 4.5** — Deep analytical reasoning (Trader stage, Final PM stage, portfolio recommendations). ~$0.04 per call.
- **Gemini 2.5 Flash** (paid tier, billing enabled) — Data gathering with Google Search grounding (Research, Macro, Earnings, Insider stages). Grounding fees are the dominant cost per analysis.
- **Total cost:** ~$0.08–$0.30 per analysis, ~30–45 seconds with parallel execution.

**8-Stage Pipeline:**
| # | Stage | Model | Cost |
|---|-------|-------|------|
| 1 | Data + ATR + Chart + Backtest + Sector RS | Local (yfinance, pandas) | Free |
| 1b | Portfolio enrichment + correlations + risk scenarios | Local + yfinance | Free |
| 1c | SEC Filing data (10-K/10-Q financials + MD&A + Risk Factors) | edgartools + SEC EDGAR | Free |
| 2–5 | Research, Macro, Earnings, Insider (PARALLEL) | Gemini 2.5 Flash | Free* |
| 6 | Trader (portfolio-aware) | Claude Sonnet 4.5 | ~$0.04 |
| 7 | Contrarian + Fatal Flaw | Gemini 2.5 Flash | Free* |
| 8 | Final PM (portfolio + cash + risk aware) | Claude Sonnet 4.5 | ~$0.04 |

*Free within daily grounding quota; cached repeats same day = $0.

**Data Sources:**
- **yfinance** — Real-time prices, analyst targets, ratios, earnings dates
- **edgartools / SEC EDGAR** — Multi-year XBRL financials, MD&A narrative, Risk Factors from 10-K/10-Q filings (free, no API key)
- **Fear & Greed Index** — 3-layer fallback: PyPI package → CNN API → VIX proxy
- **Gemini Google Search grounding** — Live web research for each analysis stage

**UI:** Gradio with auth, `share=True` required for Colab (breaks external access without it). Three tabs: Full Analysis, Portfolio, Guide.

**Performance:** Stages 2–5 run in parallel via `ThreadPoolExecutor`. SEC data fetched in parallel with Fear & Greed, earnings proximity, and sector relative strength.

## Technical Indicators

RSI, Stochastic, VWAP, Bollinger Bands, Support/Resistance, Fibonacci Retracement, ATR (for position sizing), OBV (On-Balance Volume), Accumulation/Distribution, Sector Relative Strength (20/60/120 day), Earnings Proximity Warning (14-day window), Moving Averages (20/50/200).

## Portfolio Intelligence

- **Portfolio-aware analysis:** Enter holdings as `TICKER:PCT%` — AI sizes positions relative to existing exposure
- **Cash management:** Dynamic cash target based on Fear & Greed regime + portfolio beta + sector concentration
- **Trim recommendations:** Suggests which positions to trim to meet cash target
- **Risk scenarios:** Beta-adjusted stress tests (10%/20%/30% drawdowns)
- **AI recommendations:** Claude suggests 5–8 complementary tickers based on sector gaps, correlation, and market regime
- **Cross-correlation warnings:** Flags highly correlated pairs (>0.7)

## Portfolio Management Rules (Encoded in the Tool)

- **SGOV, BIL, SHV, TBIL, USFR** → Treated as cash equivalents, not equity positions
- **SPYM** → Long-term equity parking vehicle (1+ year horizon), not a tactical position
- **Broad index funds (SPY, SPYM, VOO, VTI, QQQ, etc.)** → Discounted to 25% weight in sector concentration analysis
- **Fear & Greed** → Contrarian framing: extreme fear = potential opportunity, extreme greed = caution signal. Treated as a factor for Claude to weigh, not a hard-coded rule

## Cash Target by Market Regime

| Fear & Greed | Cash Target | Regime |
|-------------|-------------|--------|
| 0–20 | 5% | Extreme Fear — deploy aggressively (contrarian) |
| 20–35 | 10% | Fear — cautious accumulation |
| 35–55 | 15% | Neutral — standard buffer |
| 55–75 | 20% | Greed — raise cash, market overextended |
| 75–100 | 30% | Extreme Greed — maximum defensiveness |

Adjusted upward for high-beta portfolios (β > 1.3) and high sector concentration.

## Rules for Working on This Project

**Code style:**
- Always write clear, well-commented Python
- Use `except Exception as e:` with logging — never bare `except:`
- When checking values that could be 0 (like P/E), use `if v is not None` not `if v`
- Use pandas, numpy, matplotlib, yfinance as primary libraries
- Parallel data fetching via `ThreadPoolExecutor` for performance

**Iteration approach:**
- One feature or bug fix at a time — targeted changes with clear explanations of what changed and why
- Always produce a downloadable .py or .ipynb file — smart quotes from copy-paste break things in Colab
- Flag API cost implications for any new Claude/Gemini calls
- No version numbers in final filenames
- No redundancy between data sources (yfinance handles live data, SEC handles historical depth)

**Environment:**
- Must run in both Google Colab and Antigravity without manual changes
- Colab: requires `share=True` on Gradio launch + auth credentials via `google.colab.userdata`
- Antigravity: `share=False` is fine, secrets via `python-dotenv` / `.env` file
- Auto-detect environment for `share=` parameter (Colab vs Antigravity)

**Financial guardrails:**
- Never give specific buy/sell recommendations — build tools for decision-making
- Always flag data source limitations (yfinance delays/gaps, survivorship bias, lookahead bias)
- Silent failures in financial tools are dangerous — make errors visible
- Educational purposes only, not financial advice

## Known Quirks & Gotchas

- **yfinance:** Periodic endpoint breakage, inconsistent earnings data formats, unreliable `recommendationKey` (use `recommendationMean` instead), NoneType errors on delisted tickers — all require defensive error handling
- **edgartools:** Installs as `edgartools` but imports as `edgar` — requires special-case mapping in import-check logic
- **ETFs:** Bypass SEC filing fetches since they don't file 10-K/10-Q
- **Gemini grounding cost:** Dominant cost driver per run; document-processing stages (edgartools) add near-zero incremental cost since no grounding needed
- **Google Finance:** No official Python API — not suitable for pipelines (use yfinance)
- **Notebook JSON editing:** When using `str_replace` on `.ipynb` files, exact whitespace and escaped-quote matching against raw JSON `"source"` arrays is required
- **Gemini research cache:** 24-hour TTL keyed by ticker + stage name — reduces repeat API costs

## On the Horizon

- Colab/Antigravity auto-detection fix for Gradio `share=` parameter (proposed but not yet applied)
- Earnings transcript stage as a parallel Gemini call (prototyping offered, not yet built)
- Potential upgrade to paid data providers (Polygon.io, Alpha Vantage premium, Financial Modeling Prep) if free-tier reliability becomes a concern

## Preferred Patterns

- For stock screening: return results as a sorted pandas DataFrame
- For backtests: always include a benchmark comparison (e.g., SPY)
- For charts: matplotlib for static (current), plotly for interactive when needed
- Date ranges: default to 5 years of history unless specified otherwise
- Outputs should be actionable: tables, charts, and summary metrics

## Project Structure

```
finance-tools/
├── data/
├── notebooks/
│   └── Dual_AI_Stock_Analyzer.ipynb    ← main notebook
├── screeners/
├── strategies/
├── .gitignore
├── CLAUDE.md                           ← this file
└── README.md
```