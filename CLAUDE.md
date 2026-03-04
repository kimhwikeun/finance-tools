# Project Context

This is a financial analysis workspace. The user is an experienced investor
who is not a professional developer.

## Rules

- Always write clear, well-commented Python code
- Use pandas, numpy, matplotlib, yfinance, and plotly as primary libraries
- When creating notebooks, add markdown headers explaining each section
- Never give buy/sell recommendations — build tools for decision-making
- Always flag data limitations (survivorship bias, lookahead bias, etc.)
- If something needs an API key, say so upfront before writing the code
- Prioritize clear outputs: tables, charts, and summary metrics
- When using yfinance, note that free data may have delays and gaps

## Preferred Patterns

- For stock screening: return results as a sorted pandas DataFrame
- For backtests: always include a benchmark comparison (e.g., SPY)
- For charts: use plotly for interactive charts, matplotlib for static ones
- Date ranges: default to 5 years of history unless specified otherwise
```

Save it as **CLAUDE.md** in the root of your project folder (same level as the README, not inside any subfolder). Press `Ctrl+S`, name it `CLAUDE.md`.

Once that's saved, your project should look like this in the VS Code sidebar:
```
finance-tools/
├── data/
├── notebooks/
├── screeners/
├── strategies/
├── .gitignore
├── CLAUDE.md
└── README.md