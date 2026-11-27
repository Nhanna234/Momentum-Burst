# Momentum burst scanner (Indian market, daily)

Finds stocks breaking out of a tight base with a strong, high-volume day, following the momentum burst idea from Stockbee's post ["How to identify good momentum burst and..."](https://stockbee.blogspot.com/2014/01/how-to-identify-good-momentum-burst-and.html), translated into exact rules for NSE stocks. Rule sheet v1 was approved on 26 Nov 2026.

## Files

| File | What it is |
|---|---|
| `app.py` | The web app: loads prices, runs the rules, hands the results to the React screen |
| `payload.py` | Packs the results (rows, charts, rule checks) for the screen |
| `frontend/` | The React + Vite screen (`src/` is the code, `dist/` the built files Streamlit serves) |
| `scan_burst.py` | The same scan from the command line |
| `burst_rules.py` | All the rules and every number they use (the `PARAMS` table at the top). No internet |
| `burst_data.py` | Downloads: index lists (NSE Indices), price bands (NSE), daily candles (Yahoo Finance) |
| `tests/test_rules.py` | Checks the rules; needs no internet |
| `requirements.txt` | Libraries to install |

## Run it

1. Install Python 3.10 or newer (tick "Add Python to PATH" on Windows).
2. In Command Prompt, go to this folder and install the libraries once:
   ```
   pip install -r requirements.txt
   ```
3. Run:
   ```
   python scan_burst.py                         (Nifty Total Market, latest day)
   python scan_burst.py --index "Nifty 500"
   python scan_burst.py --date 2026-11-20       (an earlier day, to check past charts)
   ```
   The first run downloads about 14 months of daily candles for every stock (one to three minutes for Total Market). Runs within 15 minutes of each other reuse that download.
4. Open the Excel file in the `output` folder. The command window also prints a short summary.

**Timing for buying at the close.** Run it after 3:30 pm. If Yahoo already has today's final candle, buy in NSE's post-close session at the closing price. If the summary warns that today's candle isn't on Yahoo yet, run it again a few minutes later. Before 3:30 pm the list is provisional, because today's volume is incomplete.

## Web app

Live at https://umme-abdullah.streamlit.app (Streamlit Community Cloud, main file `app.py`, branch `main`). On your PC: `streamlit run app.py`.

The screen is a React app in `frontend/`, built with Vite into `frontend/dist`, which Streamlit shows as a custom component. `app.py` loads the prices, runs the rules and sends the results to it (`payload.py` packs them); the React app sends back what the user picked (index, day or period) and Python reruns the scan.

What it shows:
- **Top bar:** universe (Total Market or Nifty 500), **One day** or **Period** (last 5, 10, 20 or 60 sessions, or your own dates), previous/next day, Refresh prices, Download Excel, light/dark theme, and the Rules page.
- **Summary:** for one day, how many stocks survive each layer of rules; for a period, totals and a bar for each day.
- **List:** Passed and Near misses, searchable and sortable. Each row has the clean-chart score, the day's change, the risk to the stop, and a strip of 17 cells, one per rule (filled = passed), so you can see at a glance what a near miss failed.
- **Detail:** key figures, a TradingView-style candle chart (lightweight-charts) with the base high, the stop, the 65-day SMA and the breakout marked, the 17 rules with the value each was judged on, and the score broken into its five parts. In a period, the chart runs up to 30 sessions past the breakout and the row shows the change since.

**Changing the screen.** Streamlit Cloud does not build JavaScript, so the built files in `frontend/dist` are committed. After editing anything in `frontend/src`:
```
cd frontend
npm install        (first time only)
npm run build
```
then commit `frontend/dist` together with the source.

Vercel cannot host this app: Streamlit needs a server that stays running.

## The Excel file

- **Summary:** how many stocks are left after each layer of rules, and any warnings.
- **Passed:** stocks that pass all 17 rules, best clean-chart score first. Columns: score, close, % change, closing range, volume vs its 50-day average, range vs ATR20, base length, depth and high, **stop (the day's low)** with risk %, distance above the 65-day SMA, earlier bursts, erratic days, traded value, each score part, price band, an "At upper circuit?" flag (you may not get filled), and a TradingView chart link.
- **Near misses:** stocks that made the breakout move (rules 5–9) and are liquid, but failed one or more other rules. The rules they failed are listed. Look at these to judge whether a rule is too strict.
- **Settings:** every number used, so each file records the rules it was made with.

## Rule sheet v1

Daily candles. "Today" = the breakout day. Windows exclude today unless stated. ATR20 = average daily range (high − low) over the 20 days before today.

**A. Universe**
1. Constituents of Nifty Total Market or Nifty 500.
2. Close ≥ ₹50.
3. 20-day average traded value (close × volume) ≥ ₹1 crore.
4. Price band above 5%, or no band (F&O stocks).

**B. Trigger**
5. Close ≥ 4% above yesterday's close.
6. Volume > yesterday's, and ≥ 1.5 × the 50-day average.
7. (Close − low) ÷ (high − low) ≥ 0.70.
8. Close > open.
9. Today's range ≥ 1.5 × ATR20.

**C. Setup**
10. Yesterday's range < 0.8 × ATR20, or yesterday closed lower than the day before.
11. Base: the longest window of 3–20 days before today whose highest high is at most 15% above its lowest low.
12. Close above that base's highest high.
13. Average range of the last 5 days ≤ 0.8 × ATR50.

**D. Quality**
14. Close above the 65-day SMA (today included in the SMA).
15. At most 1 earlier trigger day (rules 5–9) in the last 30 sessions.
16. Close at most 25% above the 65-day SMA.
17. At most 3 days with a move of 5% or more (either way) in the last 20 sessions.

**E. Clean-chart score (0–100), used for ranking only**

| Part | How it is measured | Points |
|---|---|---|
| Smooth trend | R² of a straight line through the log of the last 65 closes (0 if the line slopes down) | 30 |
| Tight base | Base depth 3% → full, 15% → 0, straight line between | 20 |
| Small wicks | Average of body ÷ range over the last 20 days (0 to 1), times 20 | 20 |
| Few gaps | Opening gaps of 3% or more in the last 20 days: 0 → full, 4 or more → 0 | 15 |
| Calm volatility | ATR20 ÷ price: 2% → full, 8% → 0 | 15 |

## How it was checked

`python tests/test_rules.py`:
- A hand-built textbook breakout passes every rule. Versions of it built to break one rule each fail that rule.
- A separate, slow version of every rule was written one stock and one day at a time. It was compared with the fast version on 40 random charts: 51,200 rule checks plus every score and base length, with no differences.

The downloads (NSE and Yahoo) could not be tested where this was built: that machine had no access to those sites. The first real run is the test. If NSE's price-band file can't be read, the scan still runs, skips rule 4 and says so in the warnings.

## Known limitations

- **Survivorship bias:** today's index lists are used, so any later backtest misses stocks that left the index.
- **Price bands** come from today's NSE list.
- **Float** is not used.
- **Adjustments:** Yahoo's candles are split-adjusted but not dividend-adjusted, so the close and stop are real traded prices. A large dividend can look like a small fall.

## To review after the first real scans

- **Rule 11 counts a slow, steady climb as a "base"** if it stays within 15% over 20 days. The approved rule allows this; the tight-base score lowers its rank but does not exclude it. If the lists show trending stocks rather than flat bases, a tighter depth or a flatness test is the fix.
- Whether ₹1 crore, 15% depth and "1 earlier burst" are right. The Near misses sheet shows what each rule removes.
- Stops, exits and position size belong to the backtest, the next stage.
