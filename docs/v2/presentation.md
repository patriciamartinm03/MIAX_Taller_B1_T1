# Presentation outline (5 minutes)

The presentation is worth 50 % of the grade. The assignment says the point of
the work is the **engineering decisions**, so spend the time on *why*, not on
listing features.

## Timing

| Time | Slide | Message | Show |
|---|---|---|---|
| 0:00–0:30 | 1. Problem | Quick scripts break when you combine APIs and currencies. We built a toolkit where ingestion is decoupled from analysis | One-line diagram from the README |
| 0:30–1:30 | 2. Architecture | Five layers, data only moves forward, standard objects between layers. A new API is one subclass and nothing else changes | [architecture.md §1](architecture.md#1-layers) and the class diagram §3 |
| 1:30–2:15 | 3. Standardisation and validation | Same `PriceSeries` from yfinance or Tiingo. Strict validation, because bad financial data still returns a number (task 4.5) | Table in [design_decisions D1](design_decisions.md#d1-input-validation-strict-at-every-boundary) |
| 2:15–3:00 | 4. Two key decisions | (a) Never fill prices, because filling invents 0 % returns and understates risk. (b) Measure in USD with FX kept separately, so returns split into local, FX and USD | D5, D6 |
| 3:00–4:15 | 5. Live demo | `demo.py` with Enter on everything: extraction, alignment, metrics, Monte Carlo, report | `output/report.md` (warnings section) and `output/plots_report.png` |
| 4:15–5:00 | 6. Limits and next steps | GBM is optimistic in the tails. Next: fat-tailed or bootstrap simulation, configurable base currency, more providers | README §11 |

## Before the session

- [ ] **Pre-generate the outputs.** Run `uv run --env-file .env python demo.py`
      the day before and keep `output/` locally (it is git-ignored). If Yahoo
      Finance rate-limits you or the network blocks it during the session, show
      the saved files instead of running live.
- [ ] Test the demo on the presentation laptop, on the presentation network,
      from a fresh `git clone` + `uv sync`. This also proves the plug-and-play
      requirement.
- [ ] Check that the Mermaid diagrams render on GitHub. Open
      `docs/architecture.md` in the browser.
- [ ] Run `uv run pytest`. A green test run is a strong ten-second slide.
- [ ] Decide who presents which slide. With three people, give each person two
      slides.
- [ ] Have answers ready for likely questions:
  - *Why not fill missing prices?* See D6.
  - *Why not accept any series?* See D1.
  - *How do you add Alpha Vantage?* Subclass `PriceProvider` and implement
    `_fetch_prices`. See architecture §7.
  - *Why simulate assets and not the portfolio?* To keep correlations and model
    rebalancing. See D10.
  - *Why are annual return and CAGR different?* Arithmetic versus geometric
    mean. See D9.
  - *Is the VaR reliable?* Only under the model's assumptions: normal shocks,
    independent days. The report states this. See D10.
