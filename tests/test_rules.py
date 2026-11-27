"""
Checks for the scanner rules. Run: python tests/test_rules.py (no internet needed).

Part 1  a hand-built chart that should pass every rule, and versions of it that break one rule each.
Part 2  a slow, one-stock-one-day version of every rule written separately, compared with the fast
        version on random charts (every rule, every measure, every day).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd

import burst_rules as br

P = br.PARAMS
DAYS = pd.bdate_range("2025-01-01", periods=200)


# ═══════════════════════════════════════════════════════════ part 1: a textbook burst
def textbook():
    """200 days: a steady orderly uptrend, then a tight 10-day base with narrow days, then a +6% breakout
    closing at the high on 3x volume."""
    n = len(DAYS)
    c = np.empty(n)
    c[0] = 400.0
    for i in range(1, n - 11):
        c[i] = c[i - 1] * (1.0015 + (0.004 if i % 2 else -0.004))      # +0.15% a day, small zigzag
    for i in range(n - 11, n - 1):                                      # base: flat, within about 1%
        c[i] = c[n - 12] * (1 + (0.003 if i % 2 else -0.003))
    o = np.roll(c, 1)
    o[0] = c[0]
    h = np.maximum(o, c) * 1.007
    l = np.minimum(o, c) * 0.993
    base_rows = slice(n - 11, n - 1)
    h[base_rows] = np.maximum(o, c)[base_rows] * 1.002                  # narrow days in the base
    l[base_rows] = np.minimum(o, c)[base_rows] * 0.998
    v = np.full(n, 100_000.0)
    # breakout day
    o[-1] = c[-2] * 1.002
    c[-1] = c[-2] * 1.06
    h[-1] = c[-1] * 1.001
    l[-1] = o[-1] * 0.997
    v[-1] = 300_000.0
    return {"Open": o, "High": h, "Low": l, "Close": c, "Volume": v}


def panel_of(stocks: dict) -> dict:
    return {f: pd.DataFrame({s: d[f] for s, d in stocks.items()}, index=DAYS) for f in
            ("Open", "High", "Low", "Close", "Volume")}


def variant(change):
    d = {k: v.copy() for k, v in textbook().items()}
    change(d)
    return d


def scale_prices(d, k):
    for f in ("Open", "High", "Low", "Close"):
        d[f] *= k


def set_close(d, mult):          # today's close = mult x yesterday's close, high just above it
    d["Close"][-1] = d["Close"][-2] * mult
    d["High"][-1] = max(d["Close"][-1], d["Open"][-1]) * 1.001


variants = {
    2: lambda d: (scale_prices(d, 0.05), d["Volume"].__imul__(20)),         # price ~Rs 27, same traded value
    3: lambda d: d["Volume"].__imul__(0.01),                                 # traded value ~Rs 0.05 crore
    5: lambda d: set_close(d, 1.03),
    6: lambda d: d["Volume"].__setitem__(-1, 120_000.0),                    # only 1.2x average
    7: lambda d: d["High"].__setitem__(-1, d["Close"][-1] * 1.04),          # long upper wick
    8: lambda d: d["Open"].__setitem__(-1, d["Close"][-1] * 1.0005),        # close below open (gap up, faded)
    9: lambda d: (d["Low"].__setitem__(-1, d["Close"][-1] * 0.999), d["Open"].__setitem__(-1, d["Close"][-1] * 0.9995),
                  d["High"].__setitem__(-1, d["Close"][-1] * 1.0005)),      # tiny range (a gap up)
    10: lambda d: (d["High"].__setitem__(-2, d["Close"][-2] * 1.03), d["Low"].__setitem__(-2, d["Close"][-2] * 0.99),
                   d["Close"].__setitem__(-2, d["Close"][-3] * 1.002)),     # wide, up day before
    11: lambda d: [d["High"].__setitem__(-k, d["Close"][-k] * (1.10 if k % 2 else 1.0))
                   or d["Low"].__setitem__(-k, d["Close"][-k] * (0.90 if k % 2 else 1.0)) for k in range(2, 5)],
    14: lambda d: d["Close"].__setitem__(slice(130, 189), d["Close"][130:189] * 1.6),  # SMA65 pushed far above
    15: lambda d: [_plant_burst(d, k) for k in (28, 20)],                    # two earlier bursts in 30 days
    16: lambda d: d["Close"].__setitem__(slice(0, 175), d["Close"][:175] * 0.6),   # SMA65 far below today
    17: lambda d: [d["Close"].__setitem__(-k, d["Close"][-k - 1] * (1.06 if k % 2 else 0.94)) for k in range(14, 19)],
}


def _plant_burst(d, back):
    i = len(DAYS) - back
    d["Open"][i] = d["Close"][i - 1]
    d["Close"][i] = d["Close"][i - 1] * 1.06
    d["High"][i] = d["Close"][i] * 1.001
    d["Low"][i] = d["Open"][i] * 0.995
    d["Volume"][i] = 400_000.0


def part1():
    stocks = {"GOOD": textbook(), **{f"R{k}": variant(f) for k, f in variants.items()}}
    bands = pd.Series({s: 20.0 for s in stocks} | {"BAND5": 5.0, "FNO": np.inf})
    stocks["BAND5"] = textbook()
    stocks["FNO"] = textbook()
    res = br.compute(panel_of(stocks), bands)
    day = DAYS[-1]
    failed = {s: [k for k in br.ALL_RULES if not res["r"][k].at[day, s]] for s in stocks}
    assert failed["GOOD"] == [], f"textbook chart failed {failed['GOOD']}"
    assert failed["FNO"] == [], "an F&O stock (no band) must pass rule 4"
    assert 4 in failed["BAND5"], "a 5% band stock must fail rule 4"
    for k in variants:
        assert k in failed[f"R{k}"], f"variant meant to break rule {k} failed only {failed[f'R{k}']}"
    passed, near = br.scan_day(res, day)
    assert set(passed["Symbol"]) == {"GOOD", "FNO"}, passed["Symbol"].tolist()
    g = passed.set_index("Symbol").loc["GOOD"]
    assert abs(g["Change %"] - 6.0) < 1e-9 and abs(g["Stop (low)"] - res["prices"]["Low"].at[day, "GOOD"]) < 1e-9
    assert g["Base length"] >= 10 and 0 < g["Score"] <= 100
    assert "R4 Price band 5% or less" in near.set_index("Symbol").loc["BAND5", "Failed rules"]
    print("part 1: textbook passes; each variant fails its rule:",
          {k: failed[f'R{k}'] for k in variants})
    print("textbook score", g["Score"], "base", g["Base length"], "days, depth", round(g["Base depth %"], 2), "%")
    return res


# ═══════════════════════════════════════════════════════════ part 2: slow version of every rule
def slow(d, i, band, p=None):
    """Every rule and measure for one stock on bar i, from plain arrays, using the numbers in p."""
    p = p or br.PARAMS
    O, H, L, C, V = (np.asarray(d[f], float) for f in ("Open", "High", "Low", "Close", "Volume"))
    R = H - L
    out = {}
    aw, lw, vw = p["atr_window"], p["atr_long_window"], p["vol_avg_window"]
    atr20, atr50 = R[i - aw:i].mean(), R[i - lw:i].mean()
    vavg, tv = V[i - vw:i].mean(), (C[i - p["liq_window"]:i] * V[i - p["liq_window"]:i]).mean()
    sma = C[i - p["sma_window"] + 1:i + 1].mean()

    def trig(j):
        a20 = R[j - aw:j].mean()
        cr = (C[j] - L[j]) / R[j] if R[j] > 0 else 0.0
        return (C[j] / C[j - 1] - 1 >= p["min_change"] and V[j] > V[j - 1] and V[j] >= p["vol_mult"] * V[j - vw:j].mean()
                and cr >= p["min_close_range"] and C[j] > O[j] and R[j] >= p["range_mult"] * a20)

    best = None
    for n in range(p["base_min"], p["base_max"] + 1):
        hh, ll = H[i - n:i].max(), L[i - n:i].min()
        if hh / ll - 1 <= p["base_max_depth"]:
            best = (n, hh, hh / ll - 1)
    cr = (C[i] - L[i]) / R[i] if R[i] > 0 else 0.0
    out[2] = C[i] >= p["min_price"]
    out[3] = tv >= p["min_traded_value"]
    out[4] = band > p["max_excluded_band"]
    out[5] = C[i] / C[i - 1] - 1 >= p["min_change"]
    out[6] = V[i] > V[i - 1] and V[i] >= p["vol_mult"] * vavg
    out[7] = cr >= p["min_close_range"]
    out[8] = C[i] > O[i]
    out[9] = R[i] >= p["range_mult"] * atr20
    out[10] = R[i - 1] < p["quiet_range_mult"] * atr20 or C[i - 1] < C[i - 2]
    out[11] = best is not None
    out[12] = best is not None and C[i] > best[1]
    out[13] = R[i - p["contraction_days"]:i].mean() <= p["contraction_mult"] * atr50
    out[14] = C[i] > sma
    out[15] = sum(trig(j) for j in range(i - p["prior_trigger_window"], i)) <= p["max_prior_triggers"]
    out[16] = C[i] <= sma * (1 + p["max_extension"])
    out[17] = sum(abs(C[j] / C[j - 1] - 1) >= p["erratic_move"]
                  for j in range(i - p["erratic_window"], i)) <= p["max_erratic_days"]
    k = p["r2_window"]
    y = np.log(C[i - k:i])
    rr = np.corrcoef(np.arange(k), y)[0, 1]
    smooth = rr ** 2 if rr > 0 else 0.0
    bw = p["body_window"]
    body = np.mean(np.abs(C[i - bw:i] - O[i - bw:i]) / R[i - bw:i])
    gaps = sum(abs(O[j] / C[j - 1] - 1) >= p["gap_size"] for j in range(i - p["gap_window"], i))
    span = p["base_max_depth"] - p["base_depth_full"]
    tight = 0.0 if best is None else min(1, max(0, (p["base_max_depth"] - best[2]) / span))
    calm = min(1, max(0, (p["atr_pct_zero"] - atr20 / C[i - 1]) / (p["atr_pct_zero"] - p["atr_pct_full"])))
    w = p["weights"]
    score = (w["smooth"] * smooth + w["tight"] * tight + w["body"] * body
             + w["gaps"] * max(0, 1 - gaps / p["gaps_for_zero"]) + w["calm"] * calm)
    out["score"] = score
    out["base_len"] = np.nan if best is None else best[0]
    return out


def random_chart(seed):
    rng = np.random.default_rng(seed)
    n = len(DAYS)
    r = rng.normal(0.001, 0.02, n)
    burst_days = rng.choice(np.arange(60, n), 8, replace=False)
    r[burst_days] = rng.uniform(0.04, 0.09, 8)                  # plant some big up days
    c = 300 * np.exp(np.cumsum(r))
    o = np.roll(c, 1) * np.exp(rng.normal(0, 0.006, n))
    o[0] = c[0]
    o[burst_days] = np.roll(c, 1)[burst_days] * 1.001
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.008, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.008, n)))
    h[burst_days] = c[burst_days] * 1.002
    v = rng.lognormal(11.5, 0.4, n)
    v[burst_days] *= 3
    return {"Open": o, "High": h, "Low": l, "Close": c, "Volume": v}


def part2():
    stocks = {f"S{k}": random_chart(k) for k in range(40)}
    bands = pd.Series({s: [2, 5, 10, 20, np.inf][k % 5] for k, s in enumerate(stocks)}, dtype=float)
    res = br.compute(panel_of(stocks), bands)
    checks = mism = 0
    hits = {k: 0 for k in br.ALL_RULES}
    for s, d in stocks.items():
        for i in range(120, len(DAYS)):
            ref = slow(d, i, bands[s])
            day = DAYS[i]
            for k in br.ALL_RULES:
                fast = bool(res["r"][k].at[day, s])
                checks += 1
                hits[k] += fast
                if fast != bool(ref[k]):
                    mism += 1
                    print("MISMATCH rule", k, s, day.date(), fast, ref[k])
            if abs(res["score"].at[day, s] - ref["score"]) > 1e-6:
                mism += 1
                print("MISMATCH score", s, day.date(), res["score"].at[day, s], ref["score"])
            bl = res["m"]["base_len"].at[day, s]
            if not ((np.isnan(bl) and np.isnan(ref["base_len"])) or bl == ref["base_len"]):
                mism += 1
                print("MISMATCH base", s, day.date(), bl, ref["base_len"])
    print(f"part 2: {checks} rule checks plus scores and bases on 40 random charts, mismatches: {mism}")
    print("days each rule passed:", hits)
    assert mism == 0
    per_rule = checks / len(br.ALL_RULES)
    assert all(0 < hits[k] < per_rule for k in br.ALL_RULES if k not in (2, 3)), \
        "rules 4-17 should pass on some days and fail on others (2 and 3 are covered by part 1)"


def part3():
    """scan_range: same rows as scan_day for each day, and correct after-the-breakout figures."""
    stocks = {f"S{k}": random_chart(k) for k in range(40)}
    res = br.compute(panel_of(stocks), None)
    start, end = DAYS[150], DAYS[190]
    rp, rn = br.scan_range(res, start, end)
    n_p = sum(len(br.scan_day(res, d)[0]) for d in DAYS[150:191])
    n_n = sum(len(br.scan_day(res, d)[1]) for d in DAYS[150:191])
    assert len(rp) == n_p and len(rn) == n_n and n_p + n_n > 0, (len(rp), n_p, len(rn), n_n)
    assert rp["Date"].between(start, end).all() if len(rp) else True
    px = res["prices"]
    for row in pd.concat([rp, rn]).to_dict("records"):
        d, sym = row["Date"], row["Symbol"]
        after = DAYS[DAYS > d]
        c0 = px["Close"].at[d, sym]
        assert row["Bars since"] == len(after)
        assert abs(row["Change since %"] - (px["Close"].at[DAYS[-1], sym] / c0 - 1) * 100) < 1e-9
        if len(after):
            assert abs(row["High since %"] - (px["High"].loc[after, sym].max() / c0 - 1) * 100) < 1e-9
            assert bool(row["Stop hit"]) == (px["Low"].loc[after, sym].min() <= px["Low"].at[d, sym])
    assert br.first_usable_day(res) == DAYS[81]
    print(f"part 3: range scan {len(rp)} passed + {len(rn)} near misses over 41 days, matches day-by-day scans")


def part4():
    """rule_checks agrees with the rule frames, and the screen's payload is valid JSON."""
    import json
    import payload as pl
    stocks = {"GOOD": textbook(), **{f"S{k}": random_chart(k) for k in range(20)}}
    res = br.compute(panel_of(stocks), pd.Series({s: 20.0 for s in stocks}))
    bad = sum(c["pass"] != bool(res["r"][c["n"]].at[d, s])
              for s in stocks for d in DAYS[100::5] for c in br.rule_checks(res, d, s)[1:])
    assert bad == 0, bad
    p, n = br.scan_range(res, DAYS[120], DAYS[-1])
    out = pl.build(res, "period", DAYS[120], DAYS[-1], p, n, extra=[("S3", str(DAYS[150].date()))])
    json.dumps(out, allow_nan=False)
    assert all(r["id"] in out["charts"] for r in out["passed"])
    assert all(len(r["rules"]) == 17 for r in out["passed"] + out["near"])
    print(f"part 4: rule checks agree; payload with {len(out['charts'])} charts is valid JSON")


def part5():
    """Weekly and monthly: candles built correctly from daily ones, and every rule equal to the slow version."""
    days = pd.bdate_range("2020-01-01", periods=1500)
    rng = np.random.default_rng(7)
    stocks = {}
    for k in range(12):
        n = len(days)
        r = rng.normal(0.0008, 0.022, n)
        r[rng.choice(n, 40, replace=False)] = rng.uniform(0.04, 0.10, 40)
        c = 200 * np.exp(np.cumsum(r))
        o = np.roll(c, 1) * np.exp(rng.normal(0, 0.006, n))
        o[0] = c[0]
        h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.01, n)))
        l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.01, n)))
        v = rng.lognormal(12, 0.5, n)
        stocks[f"T{k}"] = {"Open": o, "High": h, "Low": l, "Close": c, "Volume": v}
    daily = {f: pd.DataFrame({s: d[f] for s, d in stocks.items()}, index=days) for f in
             ("Open", "High", "Low", "Close", "Volume")}
    daily["Close"].iloc[100:103, 0] = np.nan                       # a few missing days must not break bars
    for tf in ("W", "M"):
        p = br.TIMEFRAMES[tf][1]
        bars = br.to_timeframe(daily, tf)
        # candles: check two bars by hand
        key = daily["Close"].index.to_period("W-FRI" if tf == "W" else "M")
        for j in (5, len(bars["Close"]) - 1):
            per = bars["Close"].index[j].to_period("W-FRI" if tf == "W" else "M")
            rows = key == per
            assert bars["Close"].index[j] == daily["Close"].index[rows].max()
            assert np.isclose(bars["High"].iloc[j, 1], daily["High"].loc[rows].iloc[:, 1].max())
            assert np.isclose(bars["Low"].iloc[j, 1], daily["Low"].loc[rows].iloc[:, 1].min())
            assert np.isclose(bars["Open"].iloc[j, 1], daily["Open"].loc[rows].iloc[0, 1])
            assert np.isclose(bars["Close"].iloc[j, 1], daily["Close"].loc[rows].iloc[-1, 1])
            assert np.isclose(bars["Volume"].iloc[j, 1], daily["Volume"].loc[rows].iloc[:, 1].sum())
        res = br.compute(bars, pd.Series({s: 20.0 for s in stocks}), p)
        first = res["score"].index.get_loc(br.first_usable_day(res))
        mism = checks = 0
        hits = {k: 0 for k in br.ALL_RULES}
        for s in stocks:
            arr = {f: bars[f][s].values for f in bars}
            if np.isnan(arr["Close"]).any():
                continue
            for i in range(first, len(bars["Close"])):
                ref = slow(arr, i, 20.0, p)
                day = bars["Close"].index[i]
                for k in br.ALL_RULES:
                    fast = bool(res["r"][k].at[day, s])
                    checks += 1
                    hits[k] += fast
                    mism += fast != bool(ref[k])
                mism += abs(res["score"].at[day, s] - ref["score"]) > 1e-6
        assert mism == 0, (tf, mism)
        print(f"part 5 {tf}: {len(bars['Close'])} bars, {checks} rule checks against the slow version, "
              f"no differences; rules 5 and 12 passed {hits[5]} and {hits[12]} times")


if __name__ == "__main__":
    part1()
    part2()
    part3()
    part4()
    part5()
    print("ALL CHECKS PASSED")
