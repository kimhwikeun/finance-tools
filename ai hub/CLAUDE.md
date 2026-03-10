# CLAUDE.md — Personal AI Hub

## What This Project Is

A Python notebook (`AI_Hub.ipynb`) that acts as an intelligent multi-model AI query router. Instead of picking a model manually, the system analyzes each question and routes it to the best model automatically — similar to Perplexity, but with full control over routing logic. Includes a Gradio web UI with cost tracking.

**Environments:** Google Colab and Google Antigravity (VS Code fork). The notebook must run identically in both without code changes.

---

## Models & Providers

| Display Name   | Model ID                        | Provider   | SDK Import                        |
|----------------|--------------------------------|------------|-----------------------------------|
| GPT-latest     | `gpt-5-mini` (configurable)    | OpenAI     | `from openai import OpenAI`       |
| Claude Sonnet  | `claude-sonnet-4-6`            | Anthropic  | `from anthropic import Anthropic` |
| Claude Haiku   | `claude-haiku-4-5-20251001`    | Anthropic  | (same client)                     |
| Gemini Flash   | `gemini-2.5-flash`             | Google     | `from google import genai`        |
| Gemini Pro     | `gemini-2.0-pro-exp`           | Google     | (same client)                     |

All three providers require API keys stored in `.env` (Antigravity/local) or Colab's Secrets panel.

---

## Routing Logic (Auto mode)

The `auto_detect_model()` function in Cell 3 uses keyword matching on the user's message:

1. **File upload** (PDF attached) → Claude Sonnet — best long-context reading
2. **Real-time / news** (`today`, `current price`, `latest news`, etc.) → Gemini Flash — live Google Search grounding
3. **Finance deep-analysis** (`10-k`, `dcf`, `valuation`, `balance sheet`, etc.) → Claude Sonnet — careful with financial details
4. **Code / programming** (`write a function`, `debug this`, `refactor`, etc.) → GPT-latest — strong code model
5. **Default fallback** → GPT-latest — strong general-purpose model

The routing map is a set of keyword lists in `auto_detect_model()`, not a separate dictionary. To change routing, edit the keyword lists and return values in that function.

---

## Notebook Structure (5 cells)

| Cell | Purpose | Key Details |
|------|---------|-------------|
| **1** | Install & Imports | Auto-installs missing packages (`anthropic`, `google-genai`, `openai`, `gradio`, `python-dotenv`, `PyMuPDF`). Uses `importlib` detection — no redundant installs. |
| **2** | Configuration | Loads API keys (Colab userdata → env vars → direct paste fallback). Initializes all three API clients. Defines `MODELS` dict with pricing, `SYSTEM_PROMPTS` dict, and `session_stats`. |
| **3** | Core Functions | `auto_detect_model()`, `resolve_model()`, `needs_web_search()`, `extract_file_text()`, `calculate_cost()`, provider call functions (`call_claude`, `call_gemini`, `call_openai`), and the master `route_and_call()` router. |
| **4** | Gradio Interface | Builds the chat UI with model selector (Auto + all models), context dropdown (General / Finance Research / Code Helper), PDF upload, cost tracker, and live model preview. |
| **5** | Launch | Detects Colab vs local, sets `share=True/False` accordingly, launches with auth from env vars (default: `user` / `hub123`). |

---

## Web Search Behavior

Search is **on by default** (like Perplexity), suppressed only when:
- A PDF file is uploaded (the document is the data source)
- The query is pure code generation (self-contained, no external data needed)

Each provider uses its own search mechanism:
- **Claude** → `web_search_20250305` tool via beta API
- **Gemini** → `GoogleSearch` grounding tool
- **OpenAI** → `gpt-4o-mini-search-preview` model variant

---

## File Structure

```
ai hub/
├── AI_Hub.ipynb              ← Main notebook (the entire project)
├── .env                      ← API keys (never commit)
└── CLAUDE.md                 ← This file
```

### `.env` format
```
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=sk-ant-...
GRADIO_USERNAME=user
GRADIO_PASSWORD=hub123
```

---

## Key Patterns & Conventions

- **Error handling:** Every provider call is wrapped so one failing doesn't crash the system. Errors surface in the chat UI as `Error calling API: ...`.
- **Cost tracking:** `session_stats` dict accumulates total cost and call count across the session. Pricing is per-million-tokens, defined in the `MODELS` dict in Cell 2.
- **Token limits:** PDFs are capped at 80K characters. API responses use `max_tokens=4096`.
- **Gradio version:** Built for Gradio 6 (`type=` parameter removed from `Chatbot`, `theme=` moved to `launch()`).
- **Message format:** Gradio messages format (`{'role': '...', 'content': '...'}` dicts), converted to each provider's native format in the call functions.

---

## System Prompts

Three contexts available via the UI dropdown:

- **General** — Helpful, accurate, concise
- **Finance Research** — Expert financial analyst persona. Data-driven analysis, cite sources, never make buy/sell recommendations
- **Code Helper** — Expert Python programmer. Clean commented code, prefers pandas/numpy/plotly

---

## Common Modifications

| Task | What to Change |
|------|---------------|
| **Change GPT model** | Edit `GPT_MODEL_ID` in Cell 2 (one line) |
| **Change routing** | Edit keyword lists and return values in `auto_detect_model()` in Cell 3 |
| **Add a model** | Add entry to `MODELS` dict in Cell 2, create a `call_<provider>()` function in Cell 3, add provider branch in `route_and_call()` |
| **Add a system prompt** | Add entry to `SYSTEM_PROMPTS` dict in Cell 2 — it auto-appears in the Gradio dropdown |
| **Change pricing** | Edit `'in'` / `'out'` values in the `MODELS` dict (USD per 1M tokens) |

---

## Guardrails

- Never give specific buy/sell recommendations — the system builds tools for the user's own decisions
- Flag data source limitations
- Flag common backtest pitfalls (survivorship bias, lookahead bias) when relevant
- Finance Research system prompt enforces these constraints at the model level

---

## Future Enhancements (from project instructions)

- **Consensus mode** — Ask all models the same question, synthesize answers
- **Response caching** — Avoid redundant API calls for repeated queries
- **Cost tracker upgrades** — Persistent logging across sessions
- **Chat memory** — Multi-turn conversation history management
- **Grok integration** — Add xAI's Grok as a fourth provider
- **Upgraded classifier** — Replace keyword matching with LLM-based classification (Gemini Flash) for better accuracy
