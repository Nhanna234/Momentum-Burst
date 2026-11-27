"""
Momentum burst rules (rule sheet v1, approved 26 Nov 2026). No internet, no Streamlit: it only does sums
on daily candles, so it can be tested on its own.

Every number the rules use is in PARAMS below, with its rule number. Change a number there and nothing else.

Words used in the comments
  today      the breakout day being checked
  range      high - low of a day
  ATR20      average daily range over the 20 sessions before today (today not included)
  windows    exclude today unless the comment says otherwise
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PARAMS = {
    # A. Universe
    "min_price": 50.0,              # rule 2: close >= Rs 50
    "min_traded_value": 1e7,        # rule 3: 20-day average traded value >= Rs 1 crore
    "liq_window": 20,
    "max_excluded_band": 5.0,       # rule 4: price band must be above 5% (F&O stocks have no band)
    # B. Trigger
    "min_change": 0.04,             # rule 5: close >= 4% above yesterday's close
    "vol_mult": 1.5,                # rule 6: volume > yesterday's and >= 1.5 x the 50-day average
    "vol_avg_window": 50,
    "min_close_range": 0.70,        # rule 7: (close - low) / (high - low) >= 0.70
    "range_mult": 1.5,              # rule 9: today's range >= 1.5 x ATR20
    "atr_window": 20,
    # C. Setup
    "quiet_range_mult": 0.8,        # rule 10: yesterday's range < 0.8 x ATR20, or yesterday closed lower
    "base_min": 3,                  # rule 11: base of 3 to 20 days ...
    "base_max": 20,
    "base_max_depth": 0.15,         # ... whose highest high is at most 15% above its lowest low
    "contraction_days": 5,          # rule 13: average range of the last 5 days <= 0.8 x ATR50
    "contraction_mult": 0.8,
    "atr_long_window": 50,
    # D. Quality gates
    "sma_window": 65,               # rule 14: close above the 65-day SMA (today included in the SMA)
    "prior_trigger_window": 30,     # rule 15: at most 1 earlier trigger day in the last 30 sessions
    "max_prior_triggers": 1,
    "max_extension": 0.25,          # rule 16: close at most 25% above the 65-day SMA
    "erratic_move": 0.05,           # rule 17: at most 3 days with a move of 5% or more in the last 20
    "erratic_window": 20,
    "max_erratic_days": 3,
    # E. Clean-chart score
    "r2_window": 65,                # smooth trend: R-squared of a straight line through log prices, 65 days
    "body_window": 20,              # small wicks: average body / range over 20 days
    "gap_size": 0.03,               # few gaps: opening gaps of 3% or more in 20 days ...
    "gap_window": 20,
    "gaps_for_zero": 4,             # ... 0 gaps = full marks, 4 or more = zero
    "base_depth_full": 0.03,        # tight base: depth 3% or less = full marks, rule 11's 15% = zero
    "atr_pct_full": 0.02,           # calm volatility: ATR20 / price 2% or less = full marks ...
    "atr_pct_zero": 0.08,           # ... 8% or more = zero
    "weights": {"smooth": 30, "tight": 20, "body": 20, "gaps": 15, "calm": 15},
}

RULE_TEXT = {
    2: "Close below Rs {min_price:g}",
    3: "Traded value below Rs {tv_cr:g} crore",
    4: "Price band 5% or less",
    5: "Up less than {chg:g}%",
    6: "Volume not high enough",
    7: "Closed away from the high",
    8: "Red candle",
    9: "Range not expanded",
    10: "Day before not quiet",
    11: "No 3-20 day base",
    12: "Did not close above the base high",
    13: "No range contraction",
    14: "Below the 65-day SMA",
    15: "Too many recent bursts",
    16: "Extended above the 65-day SMA",
    17: "Erratic stock",
}
RULE_SHEET = [   # (number, layer, short name, full rule) as approved in rule sheet v1
    (1, "A", "In the index", "Constituent of Nifty Total Market or Nifty 500"),
    (2, "A", "Price", "Close at least ₹50"),
    (3, "A", "Liquidity", "20-day average traded value at least ₹1 crore"),
    (4, "A", "Price band", "Price band above 5%, or no band (F&O stocks)"),
    (5, "B", "Big move", "Close at least 4% above yesterday's close"),
    (6, "B", "Volume", "Volume above yesterday's and at least 1.5 x the 50-day average"),
    (7, "B", "Strong close", "Close in the top 30% of the day's range"),
    (8, "B", "Green candle", "Close above the open"),
    (9, "B", "Range expansion", "Day's range at least 1.5 x ATR20"),
    (10, "C", "Quiet day before", "Yesterday's range below 0.8 x ATR20, or yesterday closed lower"),
    (11, "C", "Base", "A 3-20 day base whose high is at most 15% above its low"),
    (12, "C", "Breakout", "Close above the base high"),
    (13, "C", "Contraction", "Average range of the last 5 days at most 0.8 x ATR50"),
    (14, "D", "Uptrend", "Close above the 65-day SMA"),
    (15, "D", "Early in the move", "At most 1 earlier breakout move in the last 30 sessions"),
    (16, "D", "Not extended", "Close at most 25% above the 65-day SMA"),
    (17, "D", "Not erratic", "At most 3 days with a 5%+ move in the last 20 sessions"),
]
LAYERS = {"A": "Universe", "B": "Trigger", "C": "Setup", "D": "Quality"}
UNIVERSE_RULES = (2, 3, 4)
TRIGGER_RULES = (5, 6, 7, 8, 9)
SETUP_RULES = (10, 11, 12, 13)
QUALITY_RULES = (14, 15, 16, 17)
ALL_RULES = UNIVERSE_RULES + TRIGGER_RULES + SETUP_RULES + QUALITY_RULES


def _clip01(x):
    return x.clip(lower=0.0, upper=1.0)


def compute(panel: dict, bands: pd.Series | None = None, p: dict | None = None) -> dict:
    """All rule values for every stock on every day.

    panel: {"Open", "High", "Low", "Close", "Volume"} -> DataFrame (dates x symbols), oldest date first.
    bands: price band of each symbol in % (np.inf for no band, i.e. F&O stocks); None = not checked.
    Returns a dict of DataFrames: the measures, one True/False frame per rule, and the score."""
    p = p or PARAMS
    O, H, L, C, V = (panel[k].astype("float64") for k in ("Open", "High", "Low", "Close", "Volume"))
    C1, C2, H1, L1, V1 = C.shift(1), C.shift(2), H.shift(1), L.shift(1), V.shift(1)
    rng = H - L
    atr20 = rng.rolling(p["atr_window"]).mean().shift(1)
    atr50 = rng.rolling(p["atr_long_window"]).mean().shift(1)
    vavg50 = V.rolling(p["vol_avg_window"]).mean().shift(1)
    tv20 = (C * V).rolling(p["liq_window"]).mean().shift(1)
    change = C / C1 - 1
    cr = (C - L).div(rng.where(rng > 0))
    cr = cr.where(rng > 0, 0.0).where(C.notna())
    sma65 = C.rolling(p["sma_window"]).mean()

    m = {"change": change, "close_range": cr, "vol_ratio": V / vavg50, "range_ratio": rng / atr20,
         "traded_value": tv20, "sma65": sma65, "atr20": atr20}

    # ---- base (rule 11): the longest run of 3..20 days before today with depth <= 15%
    base_len = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
    base_high = base_len.copy()
    base_depth = base_len.copy()
    Hp, Lp = H.shift(1), L.shift(1)
    for n in range(p["base_min"], p["base_max"] + 1):
        hh = Hp.rolling(n).max()
        ll = Lp.rolling(n).min()
        depth = hh / ll - 1
        ok = depth <= p["base_max_depth"]                 # depth only grows with n, so the last n that fits wins
        base_len = base_len.mask(ok, n)
        base_high = base_high.mask(ok, hh)
        base_depth = base_depth.mask(ok, depth)
    m.update(base_len=base_len, base_high=base_high, base_depth=base_depth)

    r = {}
    r[2] = C >= p["min_price"]
    r[3] = tv20 >= p["min_traded_value"]
    if bands is None:
        r[4] = pd.DataFrame(True, index=C.index, columns=C.columns)
    else:
        b = pd.to_numeric(bands.reindex(C.columns), errors="coerce")
        ok = (b > p["max_excluded_band"]).fillna(False)
        r[4] = pd.DataFrame(np.broadcast_to(ok.values, C.shape), index=C.index, columns=C.columns)
    r[5] = change >= p["min_change"]
    r[6] = (V > V1) & (V >= p["vol_mult"] * vavg50)
    r[7] = cr >= p["min_close_range"]
    r[8] = C > O
    r[9] = rng >= p["range_mult"] * atr20
    r[10] = ((H1 - L1) < p["quiet_range_mult"] * atr20) | (C1 < C2)
    r[11] = base_len.notna()
    r[12] = C > base_high
    r[13] = rng.shift(1).rolling(p["contraction_days"]).mean() <= p["contraction_mult"] * atr50
    trigger = r[5] & r[6] & r[7] & r[8] & r[9]
    prior = trigger.astype(float).shift(1).rolling(p["prior_trigger_window"]).sum()
    erratic = (change.abs() >= p["erratic_move"]).astype(float).where(change.notna()) \
        .shift(1).rolling(p["erratic_window"]).sum()
    r[14] = C > sma65
    r[15] = prior <= p["max_prior_triggers"]
    r[16] = C <= sma65 * (1 + p["max_extension"])
    r[17] = erratic <= p["max_erratic_days"]
    r = {k: v.fillna(False).astype(bool) for k, v in r.items()}
    m.update(prior_triggers=prior, erratic_days=erratic, yday_range_ratio=(H1 - L1) / atr20,
             contraction=rng.shift(1).rolling(p["contraction_days"]).mean() / atr50)

    # ---- clean-chart score
    w = p["weights"]
    logc = np.log(C.where(C > 0)).shift(1)
    t = pd.DataFrame(np.repeat(np.arange(len(C), dtype=float)[:, None], C.shape[1], axis=1),
                     index=C.index, columns=C.columns)
    corr = logc.rolling(p["r2_window"]).corr(t)
    smooth = (corr ** 2).where(corr > 0, 0.0).where(corr.notna())    # a straight line down scores nothing
    body = ((C - O).abs() / rng.where(rng > 0)).shift(1).rolling(p["body_window"], min_periods=10).mean()
    gaps = ((O / C1 - 1).abs() >= p["gap_size"]).astype(float).where(C1.notna()) \
        .shift(1).rolling(p["gap_window"]).sum()
    gap_s = _clip01(1 - gaps / p["gaps_for_zero"])
    tight = _clip01((p["base_max_depth"] - base_depth) / (p["base_max_depth"] - p["base_depth_full"]))
    atr_pct = atr20 / C1
    calm = _clip01((p["atr_pct_zero"] - atr_pct) / (p["atr_pct_zero"] - p["atr_pct_full"]))
    parts = {"smooth": smooth, "tight": tight, "body": body, "gaps": gap_s, "calm": calm}
    score = sum(w[k] * parts[k].fillna(0.0) for k in w)
    m.update(r2=corr ** 2, body_share=body, gaps=gaps, atr_pct=atr_pct)
    return {"m": m, "r": r, "trigger": trigger, "parts": parts, "score": score,
            "prices": {"Open": O, "High": H, "Low": L, "Close": C, "Volume": V}, "bands": bands, "p": p}


def scan_day(res: dict, day) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(stocks passing every rule, near misses) for one day.

    Near misses: the trigger (rules 5-9) and rules 2-3 passed, but at least one of rules 4 and 10-17 failed.
    Both tables carry every measure, the score and, for near misses, the rules that failed."""
    day = pd.Timestamp(day)
    if day not in res["score"].index:
        raise KeyError(f"No candles for {day:%d %b %Y}.")
    p, m, r, px = res["p"], res["m"], res["r"], res["prices"]
    syms = res["score"].columns
    ok = {k: r[k].loc[day] for k in ALL_RULES}
    passed_all = np.logical_and.reduce([ok[k].values for k in ALL_RULES])
    near_mask = (np.logical_and.reduce([ok[k].values for k in TRIGGER_RULES + (2, 3)]) & ~passed_all)

    def rows(mask):
        idx = syms[mask]
        if len(idx) == 0:
            return pd.DataFrame()
        C, L = px["Close"].loc[day, idx], px["Low"].loc[day, idx]
        df = pd.DataFrame({
            "Symbol": idx,
            "Score": res["score"].loc[day, idx].round(1).values,
            "Close": C.values, "Change %": (m["change"].loc[day, idx] * 100).values,
            "Close range %": (m["close_range"].loc[day, idx] * 100).values,
            "Volume x 50d avg": m["vol_ratio"].loc[day, idx].values,
            "Range x ATR20": m["range_ratio"].loc[day, idx].values,
            "Base days": m["base_len"].loc[day, idx].values,
            "Base depth %": (m["base_depth"].loc[day, idx] * 100).values,
            "Base high": m["base_high"].loc[day, idx].values,
            "Stop (day low)": L.values,
            "Risk %": ((C - L) / C * 100).values,
            "Above SMA65 %": ((C / m["sma65"].loc[day, idx] - 1) * 100).values,
            "Earlier bursts (30d)": m["prior_triggers"].loc[day, idx].values,
            "Erratic days (20d)": m["erratic_days"].loc[day, idx].values,
            "Traded value Rs cr": (m["traded_value"].loc[day, idx] / 1e7).values,
            "Smooth R2": m["r2"].loc[day, idx].values,
            "Body share": m["body_share"].loc[day, idx].values,
            "Gaps (20d)": m["gaps"].loc[day, idx].values,
            "ATR %": (m["atr_pct"].loc[day, idx] * 100).values,
        })
        if res["bands"] is not None:
            band = pd.to_numeric(res["bands"].reindex(idx), errors="coerce")
            df["Price band %"] = band.replace(np.inf, np.nan).values
            df["F&O (no band)"] = (band == np.inf).values
            chg = df["Change %"].values
            df["At upper circuit?"] = ((px["High"].loc[day, idx].values - C.values) <= 1e-9 * C.values) & \
                (band.values != np.inf) & (chg >= band.values - 0.1)
        for k, part in res["parts"].items():
            df[f"Score: {k}"] = (part.loc[day, idx] * p["weights"][k]).round(1).values
        return df

    passed = rows(passed_all)
    if len(passed):
        passed = passed.sort_values(["Score", "Close range %", "Volume x 50d avg"], ascending=False)
    near = rows(near_mask)
    if len(near):
        fmt = {"min_price": p["min_price"], "tv_cr": p["min_traded_value"] / 1e7, "chg": p["min_change"] * 100}
        reasons = []
        for s in near["Symbol"]:
            failed = [k for k in (4,) + SETUP_RULES + QUALITY_RULES if not ok[k][s]]
            reasons.append("; ".join(f"R{k} {RULE_TEXT[k].format(**fmt)}" for k in failed))
        near.insert(1, "Failed rules", reasons)
        near = near.sort_values("Score", ascending=False)
    return passed.reset_index(drop=True), near.reset_index(drop=True)


def funnel(res: dict, day) -> pd.DataFrame:
    """How many stocks pass each layer on `day`, for a quick sense of what each rule removes."""
    day = pd.Timestamp(day)
    r = res["r"]
    have = res["prices"]["Close"].loc[day].notna()
    steps, mask = [], have.values.copy()
    steps.append(("Stocks with a candle that day", int(mask.sum())))
    for name, rules in (("A. Universe (rules 2-4)", UNIVERSE_RULES), ("B. Trigger (rules 5-9)", TRIGGER_RULES),
                        ("C. Setup (rules 10-13)", SETUP_RULES), ("D. Quality (rules 14-17)", QUALITY_RULES)):
        for k in rules:
            mask &= r[k].loc[day].values
        steps.append((f"after {name}", int(mask.sum())))
    return pd.DataFrame(steps, columns=["Step", "Stocks left"])


def scan_range(res: dict, start, end, near_misses: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every day's scan from `start` to `end` (both included), one row per stock per breakout day, newest first.

    Adds what happened after each breakout, up to the latest candle in the data:
      Days since       trading days from the breakout day to the latest candle
      Latest close     the latest close
      Change since %   latest close / breakout-day close - 1
      High since %     highest high after the breakout day / breakout-day close - 1
      Stop hit         a low after the breakout day at or below the stop (the breakout day's low)"""
    idx = res["score"].index
    days = idx[(idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end))]
    px = res["prices"]
    last = idx[-1]
    out_p, out_n = [], []
    for d in days:
        p, n = scan_day(res, d)
        for df, out in ((p, out_p), (n, out_n)):
            if not len(df):
                continue
            df = df.copy()
            df.insert(0, "Date", d)
            after = idx[idx > d]
            syms = df["Symbol"].values
            c0 = px["Close"].loc[d, syms].values
            df["Days since"] = len(after)
            df["Latest close"] = px["Close"].loc[last, syms].values
            df["Change since %"] = (df["Latest close"].values / c0 - 1) * 100
            if len(after):
                hi = px["High"].loc[after, syms].max().values
                lo = px["Low"].loc[after, syms].min().values
                df["High since %"] = (hi / c0 - 1) * 100
                df["Stop hit"] = lo <= df["Stop (day low)"].values
            else:
                df["High since %"] = np.nan
                df["Stop hit"] = False
            out.append(df)
    cat = lambda xs: (pd.concat(xs, ignore_index=True).sort_values(["Date", "Score"], ascending=[False, False])
                      .reset_index(drop=True) if xs else pd.DataFrame())
    return cat(out_p), (cat(out_n) if near_misses else pd.DataFrame())


def first_usable_day(res: dict):
    """The first day on which every rule and the score have enough history (the 65-day windows plus the
    30-day look-back over earlier trigger days, which itself needs 50 days)."""
    p = res["p"]
    need = max(p["sma_window"], p["r2_window"] + 1, p["atr_long_window"] + p["prior_trigger_window"] + 1,
               p["vol_avg_window"] + p["prior_trigger_window"] + 1)
    idx = res["score"].index
    return idx[min(need, len(idx) - 1)]


def rule_checks(res: dict, day, sym: str) -> list[dict]:
    """Rules 1-17 for one stock on one day: whether each passed and the value it was judged on."""
    day = pd.Timestamp(day)
    m, r, px, p = res["m"], res["r"], res["prices"], res["p"]

    def g(frame):
        v = frame.at[day, sym]
        return None if pd.isna(v) else float(v)

    def f(x, fmt):
        return "–" if x is None else fmt.format(x)

    C, O = g(px["Close"]), g(px["Open"])
    band = None
    if res["bands"] is not None:
        b = pd.to_numeric(res["bands"].get(sym), errors="coerce")
        band = "no band (F&O)" if b == np.inf else ("not listed" if pd.isna(b) else f"{b:g}%")
    tv = g(m["traded_value"])
    base_len, base_depth, base_high = g(m["base_len"]), g(m["base_depth"]), g(m["base_high"])
    sma = g(m["sma65"])
    vals = {
        1: "member",
        2: f(C, "close ₹{:,.2f}"),
        3: f(None if tv is None else tv / 1e7, "₹{:,.1f} crore a day"),
        4: band or "not checked",
        5: f(None if g(m["change"]) is None else g(m["change"]) * 100, "{:+.1f}%"),
        6: f(g(m["vol_ratio"]), "{:.1f} x average"),
        7: f(None if g(m["close_range"]) is None else g(m["close_range"]) * 100, "closed at {:.0f}% of range"),
        8: "green" if (C is not None and O is not None and C > O) else "red",
        9: f(g(m["range_ratio"]), "{:.1f} x ATR20"),
        10: f(g(m["yday_range_ratio"]), "range {:.2f} x ATR20"),
        11: "none" if base_len is None else f"{base_len:.0f} days, {base_depth * 100:.1f}% deep",
        12: "no base" if base_high is None or C is None else f"close {(C / base_high - 1) * 100:+.1f}% vs base high",
        13: f(g(m["contraction"]), "{:.2f} x ATR50"),
        14: "–" if sma is None or C is None else f"{(C / sma - 1) * 100:+.1f}% vs SMA65",
        15: f(g(m["prior_triggers"]), "{:.0f} earlier"),
        16: "–" if sma is None or C is None else f"{(C / sma - 1) * 100:+.1f}% vs SMA65",
        17: f(g(m["erratic_days"]), "{:.0f} days"),
    }
    out = []
    for n, layer, name, rule in RULE_SHEET:
        ok = True if n == 1 else (True if (n == 4 and res["bands"] is None) else bool(r[n].at[day, sym]))
        out.append({"n": n, "layer": layer, "name": name, "pass": ok, "value": vals[n]})
    return out
