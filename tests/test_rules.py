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
    assert abs(g["Change %"] - 6.0) < 1e-9 and abs(g["Stop (day low)"] - res["prices"]["Low"].at[day, "GOOD"]) < 1e-9
    assert g["Base days"] >= 10 and 0 < g["Score"] <= 100
    assert "R4 Price band 5% or less" in near.set_index("Symbol").loc["BAND5", "Failed rules"]
    print("part 1: textbook passes; each variant fails its rule:",
          {k: failed[f'R{k}'] for k in variants})
    print("textbook score", g["Score"], "base", g["Base days"], "days, depth", round(g["Base depth %"], 2), "%")
    return res


# ═══════════════════════════════════════════════════════════ part 2: slow version of every rule
def slow(d, i, band):
    """Every rule and measure for one stock on day i, from plain arrays."""
    O, H, L, C, V = (np.asarray(d[f], float) for f in ("Open", "High", "Low", "Close", "Volume"))
    R = H - L
    out = {}
    if i < 120:
        return None
    atr20, atr50 = R[i - 20:i].mean(), R[i - 50:i].mean()
    vavg, tv = V[i - 50:i].mean(), (C[i - 20:i] * V[i - 20:i]).mean()
    sma = C[i - 64:i + 1].mean()

    def trig(j):
        a20 = R[j - 20:j].mean()
        cr = (C[j] - L[j]) / R[j] if R[j] > 0 else 0.0
        return (C[j] / C[j - 1] - 1 >= 0.04 and V[j] > V[j - 1] and V[j] >= 1.5 * V[j - 50:j].mean()
                and cr >= 0.70 and C[j] > O[j] and R[j] >= 1.5 * a20)

    best = None
    for n in range(3, 21):
        hh, ll = H[i - n:i].max(), L[i - n:i].min()
        if hh / ll - 1 <= 0.15:
            best = (n, hh, hh / ll - 1)
    cr = (C[i] - L[i]) / R[i] if R[i] > 0 else 0.0
    out[2] = C[i] >= 50
    out[3] = tv >= 1e7
    out[4] = band > 5
    out[5] = C[i] / C[i - 1] - 1 >= 0.04
    out[6] = V[i] > V[i - 1] and V[i] >= 1.5 * vavg
    out[7] = cr >= 0.70
    out[8] = C[i] > O[i]
    out[9] = R[i] >= 1.5 * atr20
    out[10] = R[i - 1] < 0.8 * atr20 or C[i - 1] < C[i - 2]
    out[11] = best is not None
    out[12] = best is not None and C[i] > best[1]
    out[13] = R[i - 5:i].mean() <= 0.8 * atr50
    out[14] = C[i] > sma
    out[15] = sum(trig(j) for j in range(i - 30, i)) <= 1
    out[16] = C[i] <= sma * 1.25
    out[17] = sum(abs(C[j] / C[j - 1] - 1) >= 0.05 for j in range(i - 20, i)) <= 3
    y = np.log(C[i - 65:i])
    rr = np.corrcoef(np.arange(65), y)[0, 1]
    smooth = rr ** 2 if rr > 0 else 0.0
    body = np.mean(np.abs(C[i - 20:i] - O[i - 20:i]) / R[i - 20:i])
    gaps = sum(abs(O[j] / C[j - 1] - 1) >= 0.03 for j in range(i - 20, i))
    tight = 0.0 if best is None else min(1, max(0, (0.15 - best[2]) / 0.12))
    calm = min(1, max(0, (0.08 - atr20 / C[i - 1]) / 0.06))
    score = 30 * smooth + 20 * tight + 20 * body + 15 * max(0, 1 - gaps / 4) + 15 * calm
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
        assert row["Days since"] == len(after)
        assert abs(row["Change since %"] - (px["Close"].at[DAYS[-1], sym] / c0 - 1) * 100) < 1e-9
        if len(after):
            assert abs(row["High since %"] - (px["High"].loc[after, sym].max() / c0 - 1) * 100) < 1e-9
            assert bool(row["Stop hit"]) == (px["Low"].loc[after, sym].min() <= px["Low"].at[d, sym])
    assert br.first_usable_day(res) == DAYS[81]
    print(f"part 3: range scan {len(rp)} passed + {len(rn)} near misses over 41 days, matches day-by-day scans")


if __name__ == "__main__":
    part1()
    part2()
    part3()
    print("ALL CHECKS PASSED")
