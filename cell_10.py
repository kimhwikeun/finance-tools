# SECTION 7: HTML REPORT BUILDER
# ============================================================================



def get_financial_statements_html(ticker, etf=False):
    """
    Pull 3 years of Income Statement, Balance Sheet, and Cash Flow from yfinance
    and return a formatted HTML section for the report.

    Uses yfinance .financials, .balance_sheet, .cashflow DataFrames —
    separate from SEC XBRL data that feeds the AI prompts.
    Returns empty string for ETFs (no standard corporate financials).
    No API cost — yfinance is free and already in use.
    """
    if etf:
        return ""

    try:
        stk = yf.Ticker(ticker)

        def _fmt_val(val):
            """Format a raw dollar value into readable billions/millions."""
            if val is None or (isinstance(val, float) and (val != val)):  # NaN check
                return "\u2014"
            try:
                v = float(val)
                if abs(v) >= 1e9:
                    return f"${v/1e9:.2f}B"
                elif abs(v) >= 1e6:
                    return f"${v/1e6:.0f}M"
                elif abs(v) >= 1e3:
                    return f"${v/1e3:.0f}K"
                else:
                    return f"${v:.2f}"
            except (TypeError, ValueError):
                return "\u2014"

        def _build_table(df, rows_to_show, title, color):
            """
            Build one HTML table from a yfinance financial DataFrame.
            df columns are dates (most recent first), index is metric names.
            rows_to_show: list of label substrings to match (case-insensitive).
            """
            if df is None or df.empty:
                return ""

            # Limit to 3 most recent annual periods
            cols = df.columns[:3]
            years = [str(c.year) if hasattr(c, 'year') else str(c)[:4] for c in cols]

            header = "".join([
                f'<th style="text-align:right;padding:7px 14px;background:#f0f4f8;'
                f'font-size:11px;color:#555">{y}</th>'
                for y in years
            ])

            data_rows = ""
            row_count = 0
            for metric in rows_to_show:
                # Case-insensitive partial match — resilient across yfinance versions
                match = None
                for idx in df.index:
                    if metric.lower() in str(idx).lower():
                        match = idx
                        break
                if match is None:
                    continue

                bg = "background:#f9fafb;" if row_count % 2 == 0 else ""
                cells = ""
                for col in cols:
                    try:
                        raw = df.loc[match, col]
                        cells += (
                            f'<td style="text-align:right;padding:6px 14px;'
                            f'font-size:12px;font-weight:600;{bg}">{_fmt_val(raw)}</td>'
                        )
                    except Exception:
                        cells += '<td style="text-align:right;padding:6px 14px">\u2014</td>'

                data_rows += (
                    f'<tr>'
                    f'<td style="padding:6px 14px;font-size:12px;color:#444;{bg}">{match}</td>'
                    f'{cells}</tr>'
                )
                row_count += 1

            if row_count == 0:
                return ""

            return (
                f'<div style="margin-bottom:20px">'
                f'<h4 style="color:{color};font-size:13px;font-weight:700;margin-bottom:8px;'
                f'text-transform:uppercase;letter-spacing:0.5px">{title}</h4>'
                f'<div style="overflow-x:auto">'
                f'<table style="width:100%;border-collapse:collapse;font-family:\'Segoe UI\',sans-serif">'
                f'<thead><tr>'
                f'<th style="text-align:left;padding:7px 14px;background:#f0f4f8;'
                f'font-size:11px;color:#555">Metric</th>{header}'
                f'</tr></thead>'
                f'<tbody>{data_rows}</tbody>'
                f'</table></div></div>'
            )

        # Key metrics to display per statement
        income_metrics = [
            "Total Revenue", "Gross Profit", "Operating Income",
            "EBITDA", "Net Income", "Diluted EPS",
        ]
        balance_metrics = [
            "Total Assets", "Total Liabilities", "Total Stockholder Equity",
            "Cash And Cash Equivalents", "Total Debt", "Net Debt",
        ]
        cashflow_metrics = [
            "Operating Cash Flow", "Capital Expenditure",
            "Free Cash Flow", "Repurchase Of Capital Stock", "Dividends Paid",
        ]

        income_html  = _build_table(stk.financials,    income_metrics,   "Income Statement", "#1565c0")
        balance_html = _build_table(stk.balance_sheet, balance_metrics,  "Balance Sheet",    "#2e7d32")
        cash_html    = _build_table(stk.cashflow,      cashflow_metrics, "Cash Flow",        "#6a1b9a")

        content = income_html + balance_html + cash_html
        if not content.strip():
            return ""

        return (
            '<div class="section">'
            '<div class="st" style="color:#0d47a1;border-color:#0d47a1">'
            'Financial Statements \u2014 Last 3 Years</div>'
            '<div class="sb">'
            '<p style="font-size:11px;color:#999;margin-bottom:15px">'
            'Source: yfinance&nbsp;|&nbsp;Annual figures</p>'
            f'{content}'
            '</div></div>'
        )

    except Exception as e:
        log.warning(f"Financial statements table failed for {ticker}: {e}")
        return ""

def t2h(text):
    """Convert markdown-ish text to HTML paragraphs."""
    out = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            out.append('<br>')
        elif line.startswith('# '):
            out.append(f'<h3 style="color:#0d1b3e;margin:18px 0 8px">{line[2:]}</h3>')
        elif line.startswith('## '):
            out.append(f'<h4 style="color:#1a3a6e;margin:14px 0 6px">{line[3:]}</h4>')
        elif line.startswith(('- ', '* ')):
            inner = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line[2:])
            out.append(f'<p style="margin:3px 0 3px 24px">&bull; {inner}</p>')
        else:
            inner = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            out.append(f'<p style="margin:5px 0;line-height:1.7">{inner}</p>')
    return '\n'.join(out)


def build_report(tk, nm, tech, fd, research, macro, earnings, insider,
                 trader, contrarian, pm, bt, fg, chart, etf, rs=None, earn_prox=None,
                 portfolio=None, cash_rec=None, risk_scenarios="", target_alloc=None, sec_data=None):
    """Build the final HTML report. Now includes portfolio, risk, and cash sections."""
    d = tech

    # Color coding
    rsi_color = "#c62828" if d['rsi'] > 70 else "#2e7d32" if d['rsi'] < 30 else "#555"
    macd_color = "#2e7d32" if d['macd'] > d['signal'] else "#c62828"
    ma_color = "#2e7d32" if d['ma50'] > d['ma200'] else "#c62828"
    vwap_color = "#2e7d32" if d['price'] > d['vwap'] else "#c62828"
    atr_color = "#2e7d32" if d['atr_pct'] < 2 else "#e65100" if d['atr_pct'] < 4 else "#c62828"

    # Fear & Greed badge
    fg_html = ""
    if fg and fg["score"]:
        fgc = ("#c62828" if fg["score"] <= 25 else "#e65100" if fg["score"] <= 45
               else "#555" if fg["score"] <= 55 else "#2e7d32" if fg["score"] <= 75
               else "#1565c0")
        fg_html = (
            f'<div style="background:#f5f5f5;padding:15px;border-radius:10px;'
            f'margin:15px 0;text-align:center">'
            f'<span style="font-size:28px">{fg["emoji"]}</span>'
            f'<span style="font-size:22px;font-weight:700;color:{fgc};margin-left:10px">'
            f'{fg["score"]}/100</span>'
            f'<span style="font-size:14px;color:#666;margin-left:8px">{fg["label"]}</span>'
            f'</div>'
        )

    # NEW: Earnings proximity warning badge
    earn_badge = ""
    if earn_prox and earn_prox[0] is not None and earn_prox[0] <= 14:
        earn_badge = (
            f'<div style="background:#fff3e0;border:2px solid #e65100;padding:12px;'
            f'border-radius:10px;margin:10px 0;text-align:center;font-weight:700;'
            f'color:#e65100">⚠️ EARNINGS IN {earn_prox[0]} DAYS — {earn_prox[1]}</div>'
        )

    # Target allocation badge
    alloc_badge = ""
    if target_alloc is not None:
        alloc_badge = (
            f'<div style="background:#e3f2fd;border:2px solid #1565c0;padding:12px;'
            f'border-radius:10px;margin:10px 0;text-align:center;font-weight:700;'
            f'color:#1565c0">🎯 USER TARGET: {target_alloc:.1f}% allocation for {tk} — PM will evaluate below</div>'
        )

    # NEW: Relative Sector Strength badge
    rs_badge = ""
    if rs and rs.get("verdict", "N/A") != "N/A" and rs.get("sector_etf", "N/A") != "N/A":
        rs_badge = (
            f'<div style="background:#f5f5f5;padding:10px;border-radius:8px;'
            f'margin:8px 0;text-align:center;font-size:13px">'
            f'<strong>Sector RS vs {rs["sector_etf"]}:</strong> '
            f'20d {rs.get("rs_20d","N/A")} | 60d {rs.get("rs_60d","N/A")} | '
            f'120d {rs.get("rs_120d","N/A")} — {rs["verdict"]}</div>'
        )

    # SEC Filing badge
    sec_badge = ""
    if sec_data and sec_data.get("source", "N/A") != "N/A":
        sec_badge = (
            f'<div style="background:#f3e5f5;padding:10px;border-radius:8px;'
            f'margin:8px 0;text-align:center;font-size:13px">'
            f'<strong>SEC Filing Data:</strong> {sec_data["source"]} '
            f'(filed {sec_data.get("filing_date", "N/A")}) — '
            f'Multi-year financials + MD&A narrative included in AI analysis</div>'
        )

    # Financial statements tables (Income / Balance Sheet / Cash Flow)
    # Built from yfinance DataFrames; no extra API cost
    fin_statements_html = get_financial_statements_html(tk, etf)

    # Fundamentals data grid
    fund_rows = ""
    items = list(fd.items())
    for i in range(0, len(items), 3):
        for j in range(3):
            if i + j < len(items):
                k, v = items[i + j]
                bg = "background:#f8f9fb;" if (i // 3) % 2 == 1 else ""
                fund_rows += (
                    f'<div class="dc" style="{bg}">'
                    f'<div class="dl">{k}</div><div class="dv">{v}</div></div>'
                )

    # Portfolio context section
    portfolio_html = ""
    if portfolio and portfolio.get("holdings"):
        pf_rows = ""
        for ticker, pct in portfolio["holdings"].items():
            sec = portfolio.get("sectors", {}).get(ticker, "?")
            beta = portfolio.get("betas", {}).get(ticker)
            beta_str = f"β={beta:.2f}" if beta else ""
            pf_rows += (
                f'<div class="dc"><div class="dl">{ticker}</div>'
                f'<div class="dv">{pct:.1f}% <span style="font-size:10px;color:#888">{sec} {beta_str}</span></div></div>'
            )
        pf_rows += f'<div class="dc" style="background:#e8f5e9"><div class="dl">CASH</div><div class="dv">{portfolio["cash_pct"]:.1f}%</div></div>'

        if portfolio.get("portfolio_beta"):
            pf_rows += f'<div class="dc" style="background:#fff3e0"><div class="dl">Portfolio Beta</div><div class="dv">{portfolio["portfolio_beta"]:.2f}</div></div>'

        # Sector concentration
        sector_html = ""
        if portfolio.get("sector_weights"):
            sector_items = sorted(portfolio["sector_weights"].items(), key=lambda x: -x[1])
            for sec, wt in sector_items:
                color = "#c62828" if wt > 30 else "#e65100" if wt > 20 else "#333"
                sector_html += f'<span style="margin-right:12px;color:{color};font-weight:600">{sec}: {wt:.0f}%</span>'

        # Correlation with new ticker
        corr_html = ""
        if portfolio.get("correlations_with_new"):
            high_corrs = {k: v for k, v in portfolio["correlations_with_new"].items() if abs(v) > 0.6}
            if high_corrs:
                corr_items = []
                for pair, corr in sorted(high_corrs.items(), key=lambda x: -abs(x[1])):
                    color = "#c62828" if abs(corr) > 0.8 else "#e65100"
                    corr_items.append(f'<span style="color:{color};font-weight:600">{pair}: {corr:.2f}</span>')
                corr_html = f'<div style="margin-top:8px;font-size:12px">Correlation with {tk}: {" | ".join(corr_items)}</div>'

        portfolio_html = f"""
        <div class="section">
          <div class="st" style="color:#1565c0;border-color:#1565c0">Current Portfolio</div>
          <div class="sb">
            <div class="dg">{pf_rows}</div>
            <div style="margin-top:10px;font-size:12px">{sector_html}</div>
            {corr_html}
          </div>
        </div>"""

    # Cash recommendation section
    cash_html = ""
    if cash_rec:
        rec_cash, regime, trims = cash_rec
        current_cash = portfolio["cash_pct"] if portfolio else 0
        cash_color = "#2e7d32" if abs(rec_cash - current_cash) < 5 else "#e65100"

        trim_html = ""
        if trims:
            trim_items = "".join([
                f'<div style="padding:4px 0;font-size:13px">'
                f'<strong>{t["ticker"]}</strong>: {t["current_pct"]:.1f}% → {t["new_pct"]:.1f}% '
                f'<span style="color:#c62828">(trim {t["trim_pct"]:.1f}%)</span></div>'
                for t in trims
            ])
            trim_html = f'<div style="margin-top:10px;padding:10px;background:#fff3e0;border-radius:6px"><strong>Suggested Trims:</strong>{trim_items}</div>'

        cash_html = f"""
        <div class="section">
          <div class="st" style="color:#00695c;border-color:#00695c">Cash Management</div>
          <div class="sb">
            <div style="display:flex;gap:20px;align-items:center;flex-wrap:wrap">
              <div><span style="font-size:10px;color:#888;text-transform:uppercase">Current Cash</span><br>
                <span style="font-size:22px;font-weight:700">{current_cash:.0f}%</span></div>
              <div style="font-size:24px;color:#888">→</div>
              <div><span style="font-size:10px;color:#888;text-transform:uppercase">Recommended</span><br>
                <span style="font-size:22px;font-weight:700;color:{cash_color}">{rec_cash:.0f}%</span></div>
            </div>
            <div style="margin-top:8px;font-size:13px;color:#555">{regime}</div>
            {trim_html}
          </div>
        </div>"""

    # Risk scenarios section
    # SEC Filing narrative section (MD&A + Risk Factors from actual filings)
    sec_filing_html = ""
    if sec_data and (sec_data.get("mda_text") or sec_data.get("risk_factors_text")):
        sec_parts = []
        if sec_data.get("mda_text"):
            # Clean up for HTML display
            mda_display = sec_data["mda_text"][:3000].replace("\n", "<br>")
            sec_parts.append(f'<h4 style="color:#6a1b9a;margin:10px 0 5px">Management Discussion & Analysis</h4><p style="font-size:13px;line-height:1.6">{mda_display}</p>')
        if sec_data.get("risk_factors_text"):
            risk_display = sec_data["risk_factors_text"][:2000].replace("\n", "<br>")
            sec_parts.append(f'<h4 style="color:#b71c1c;margin:10px 0 5px">Key Risk Factors</h4><p style="font-size:13px;line-height:1.6">{risk_display}</p>')
        sec_filing_html = f"""
        <div class="section">
          <div class="st" style="color:#6a1b9a;border-color:#6a1b9a">SEC Filing — {sec_data.get('source', 'N/A')} (Filed {sec_data.get('filing_date', 'N/A')})</div>
          <div class="sb">{''.join(sec_parts)}</div>
        </div>"""

    risk_html = ""
    if risk_scenarios:
        risk_html = f"""
        <div class="section">
          <div class="st" style="color:#880e4f;border-color:#880e4f">Risk Scenarios</div>
          <div class="sb" style="font-family:monospace;font-size:12px;white-space:pre-wrap;background:#f9f9f9;padding:15px">{risk_scenarios}</div>
        </div>"""

    def section(title, css_class, body):
        return (
            f'<div class="section"><div class="st {css_class}">{title}</div>'
            f'<div class="sb">{t2h(body)}</div></div>'
        )

    css = """
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',Roboto,Oxygen,Ubuntu,Cantarell,sans-serif;background:#f4f7f9;color:#2c3e50}
    .ctr{max-width:1100px;margin:40px auto;background:#fff;box-shadow:0 12px 36px rgba(0,0,0,0.08);border-radius:16px;overflow:hidden}
    .hdr{background:linear-gradient(135deg,#1e3c72,#2a5298);color:#fff;padding:36px 45px}
    .hdr h1{font-size:30px;font-weight:800;letter-spacing:-0.5px;margin-bottom:6px}
    .hdr .s{opacity:.85;font-size:14px;font-weight:500;letter-spacing:0.5px}
    .section{background:#fff;padding:35px 45px;border-bottom:1px solid #edf2f7}
    .st{font-size:19px;font-weight:700;padding-bottom:12px;margin-bottom:20px;border-bottom:3px solid;letter-spacing:-0.2px}
    .sb{font-size:15px;line-height:1.75;color:#34495e}
    .res{color:#2980b9;border-color:#2980b9}
    .mac{color:#8e44ad;border-color:#8e44ad}
    .ear{color:#16a085;border-color:#16a085}
    .ins{color:#d35400;border-color:#d35400}
    .bkt{color:#27ae60;border-color:#27ae60}
    .trd{color:#009432;border-color:#009432}
    .con{color:#c0392b;border-color:#c0392b}
    .pm{color:#e67e22;border-color:#e67e22}
    .snap{background:#fcfcfd;padding:30px 45px;border-bottom:1px solid #edf2f7}
    .pr{display:flex;align-items:center;gap:15px;margin-top:15px;flex-wrap:wrap}
    .price{font-size:44px;font-weight:800;color:#1e3c72;letter-spacing:-1.5px}
    .badge{font-size:12px;font-weight:700;padding:6px 14px;border-radius:8px;text-transform:uppercase;letter-spacing:0.5px;box-shadow:0 2px 4px rgba(0,0,0,0.05)}
    .dg{display:grid;grid-template-columns:repeat(3,1fr);margin-top:25px;border:1px solid #edf2f7;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.02)}
    .dc{padding:14px 20px;border-bottom:1px solid #edf2f7;border-right:1px solid #edf2f7;background:#fff}
    .dl{font-size:11px;color:#7f8c8d;text-transform:uppercase;font-weight:700;letter-spacing:0.5px}
    .dv{font-size:14px;font-weight:700;color:#2c3e50;margin-top:6px}
    .cht{background:#fff;padding:35px 45px;border-bottom:1px solid #edf2f7;text-align:center}
    .cht img{max-width:100%;border-radius:12px;box-shadow:0 4px 16px rgba(0,0,0,0.06)}
    .pms{background:linear-gradient(to bottom,#fffaf0,#fff)}
    .cons{background:linear-gradient(to bottom,#fdf2f2,#fff)}
    .ftr{text-align:center;color:#95a5a6;font-size:12px;padding:25px;background:#f8f9fa}
    .pip{display:flex;justify-content:center;align-items:center;gap:8px;margin:20px 0 30px;flex-wrap:wrap}
    .pip span{background:#edf2f7;color:#4a5568;padding:8px 16px;border-radius:24px;font-size:11px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;box-shadow:inset 0 1px 2px rgba(255,255,255,0.5)}
    .pip .final{background:#fffaf0;border:1px solid #e67e22;color:#e67e22;box-shadow:0 2px 6px rgba(230,126,34,0.15)}
    .pip .devil{background:#fdf2f2;border:1px solid #c0392b;color:#c0392b;box-shadow:0 2px 6px rgba(192,57,43,0.15)}
    .pb{position:fixed;bottom:30px;right:30px;background:#1e3c72;color:#fff;border:none;padding:14px 28px;border-radius:30px;font-weight:600;font-size:15px;cursor:pointer;z-index:1000;box-shadow:0 6px 20px rgba(30,60,114,0.4);transition:transform 0.2s, box-shadow 0.2s}
    .pb:hover{transform:translateY(-2px);box-shadow:0 8px 25px rgba(30,60,114,0.5)}
    @media print{.pb,.ctr{box-shadow:none;margin:0}.hdr{border-radius:0}}
    """

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{tk} Analysis</title>
<style>{css}</style></head><body>
<button class="pb" onclick="window.print()">Print</button>
<div class="ctr">
  <div class="hdr">
    <h1>AI Stock Analyzer</h1>
    <div class="s">{nm} ({tk}) &mdash; {datetime.now().strftime('%B %d, %Y')}</div>
  </div>
  <div class="snap">
    <div class="pip">
      <span>Data+ATR</span><span>&#8594;</span><span>Research</span><span>&#8594;</span>
      <span>Macro</span><span>&#8594;</span><span>Earnings</span><span>&#8594;</span>
      <span>Insider</span><span>&#8594;</span><span>Trader</span><span>&#8594;</span>
      <span class="devil">Contrarian</span><span>&#8594;</span><span class="final">Final PM</span>
    </div>
    <div class="pr">
      <span class="price">${d['price']:.2f}</span>
      <span class="badge" style="background:{ma_color}15;color:{ma_color}">{"Golden" if d['ma50']>d['ma200'] else "Death"}</span>
      <span class="badge" style="background:{rsi_color}15;color:{rsi_color}">RSI {d['rsi']:.0f}</span>
      <span class="badge" style="background:{macd_color}15;color:{macd_color}">MACD {"Bull" if d['macd']>d['signal'] else "Bear"}</span>
      <span class="badge" style="background:{atr_color}15;color:{atr_color}">ATR {d['atr_pct']:.1f}%</span>
    </div>
    {earn_badge}
    {alloc_badge}
    {fg_html}
    {rs_badge}
    {sec_badge}
    <div class="dg">{fund_rows}</div>
  </div>
  <div class="cht"><img src="data:image/png;base64,{chart}"></div>
  {fin_statements_html}
  {portfolio_html}
  {cash_html}
  {risk_html}
  {sec_filing_html}
  <div class="section"><div class="st bkt">Backtest 2yr</div>
    <div class="sb" style="font-family:monospace;font-size:12px;white-space:pre-wrap;background:#f9f9f9;padding:15px">{bt}</div>
  </div>
  {section("Equity Researcher — Gemini", "res", research)}
  {section("Macro Analyst — Gemini", "mac", macro)}
  {section("Earnings Scout — Gemini", "ear", earnings)}
  {section("Insider Flow — Gemini", "ins", insider)}
  {section("Trader — Claude Sonnet 4.5", "trd", trader)}
  <div class="section cons">
    <div class="st con">Contrarian — Gemini (Fatal Flaw Check)</div>
    <div class="sb">{t2h(contrarian)}</div>
  </div>
  <div class="section pms">
    <div class="st pm">Final PM — Claude Sonnet 4.5 (Portfolio-Aware)</div>
    <div class="sb">{t2h(pm)}</div>
  </div>
  <div class="ftr">AI Stock Analyzer — Educational only. Not financial advice.</div>
</div></body></html>"""


# ============================================================================