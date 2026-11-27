"""
Turns a scan into the data the React front end draws (no Streamlit, no internet, so it can be tested).
"""

from __future__ import annotations

import base64
import math

import numpy as np
import pandas as pd

import burst_rules as br

CHART_BEFORE = 120          # sessions shown before the breakout day
CHART_AFTER = 30            # sessions shown after it, in a period view
CHART_NEAR_LIMIT = 40       # near misses sent with their chart up front; others load when clicked

ROW_FIELDS = {              # column in the scan table -> key the front end uses
    "Symbol": "symbol", "Company": "company", "Industry": "industry", "Score": "score", "Close": "close",
    "Change %": "change", "Close range %": "closeRange", "Volume x avg": "volRatio",
    "Range x ATR": "rangeRatio", "Base length": "baseDays", "Base depth %": "baseDepth", "Base high": "baseHigh",
    "Stop (low)": "stop", "Risk %": "risk", "Above SMA %": "aboveSma", "Earlier bursts": "priorBursts",
    "Erratic bars": "erraticDays", "Traded value Rs cr": "tradedValue", "Price band %": "band",
    "F&O (no band)": "fno", "At upper circuit?": "upperCircuit", "Failed rules": "failed",
    "Bars since": "daysSince", "Latest close": "latestClose", "Change since %": "changeSince",
    "High since %": "highSince", "Stop hit": "stopHit", "Chart": "tvLink",
}


def _clean(v):
    """JSON-safe value: NaN/inf -> None, numpy -> Python."""
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return None if (math.isnan(v) or math.isinf(v)) else round(float(v), 4)
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    return v


def rows_of(df: pd.DataFrame, res: dict, day, kind: str) -> list[dict]:
    out = []
    for rec in df.to_dict("records"):
        d = pd.Timestamp(rec.get("Date", day))
        row = {ROW_FIELDS[k]: _clean(v) for k, v in rec.items() if k in ROW_FIELDS}
        row["date"] = d.strftime("%Y-%m-%d")
        row["kind"] = kind
        row["id"] = f"{row['symbol']}|{row['date']}"
        row["parts"] = {k: _clean(rec.get(f"Score: {k}")) for k in br.PARAMS["weights"]}
        row["rules"] = [c["pass"] for c in br.rule_checks(res, d, row["symbol"])]
        out.append(row)
    return out


def chart_of(res: dict, sym: str, day, after: int) -> dict:
    """Candles around one breakout, with the 65-day SMA, base, stop and every rule's value."""
    px, m = res["prices"], res["m"]
    idx = px["Close"].index
    day = pd.Timestamp(day)
    end = idx.get_loc(day)
    last = min(len(idx) - 1, end + after)
    sel = idx[max(0, end - CHART_BEFORE): last + 1]
    o, h, l, c, v = (px[k].loc[sel, sym].values for k in ("Open", "High", "Low", "Close", "Volume"))
    sma = m["sma"].loc[sel, sym].values      # the timeframe's SMA (65 days, 30 weeks or 12 months)
    r2 = lambda x: None if pd.isna(x) else round(float(x), 2)
    candles = [{"t": t.strftime("%Y-%m-%d"), "o": r2(o[i]), "h": r2(h[i]), "l": r2(l[i]), "c": r2(c[i]),
                "v": None if pd.isna(v[i]) else int(v[i]), "sma": r2(sma[i])}
               for i, t in enumerate(sel) if not (pd.isna(c[i]) or pd.isna(o[i]))]
    base_len = m["base_len"].at[day, sym]
    base = None
    if pd.notna(base_len):
        start = idx[end - int(base_len)]
        base = {"from": start.strftime("%Y-%m-%d"), "to": idx[end - 1].strftime("%Y-%m-%d"),
                "high": _clean(m["base_high"].at[day, sym]), "days": int(base_len),
                "depth": _clean(m["base_depth"].at[day, sym] * 100)}
    return {"symbol": sym, "date": day.strftime("%Y-%m-%d"), "candles": candles, "base": base,
            "stop": _clean(px["Low"].at[day, sym]), "checks": br.rule_checks(res, day, sym)}


def build(res: dict, mode: str, start, end, passed: pd.DataFrame, near: pd.DataFrame,
          extra: list[tuple[str, str]] | None = None) -> dict:
    """The result part of the payload: rows, charts, per-day counts or the funnel."""
    period = mode == "period"
    after = CHART_AFTER if period else 0
    p_rows = rows_of(passed, res, end, "passed")
    n_rows = rows_of(near, res, end, "near")
    charts = {}
    for r in p_rows + n_rows[:CHART_NEAR_LIMIT]:
        charts[r["id"]] = chart_of(res, r["symbol"], r["date"], after)
    for sym, d in extra or []:
        if sym in res["prices"]["Close"].columns and pd.Timestamp(d) in res["prices"]["Close"].index:
            charts[f"{sym}|{d}"] = chart_of(res, sym, d, after)
    out = {"mode": mode, "start": pd.Timestamp(start).strftime("%Y-%m-%d"),
           "end": pd.Timestamp(end).strftime("%Y-%m-%d"), "passed": p_rows, "near": n_rows, "charts": charts}
    if period:
        idx = res["score"].index
        days = idx[(idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end))]
        pc = passed["Date"].value_counts() if len(passed) else pd.Series(dtype=int)
        nc = near["Date"].value_counts() if len(near) else pd.Series(dtype=int)
        out["perDay"] = [{"date": d.strftime("%Y-%m-%d"), "passed": int(pc.get(d, 0)), "near": int(nc.get(d, 0))}
                         for d in days]
    else:
        f = br.funnel(res, end)
        out["funnel"] = [{"step": s, "left": int(n)} for s, n in zip(f["Step"], f["Stocks left"])]
    return out


def meta(res: dict, index: str, indexes: list[str], uni_count: int, uni_note: str, band_note: str,
         fetched_at, warnings: list[str], tf: str = "D", partial_last: bool = False) -> dict:
    idx = res["score"].index
    usable = idx[idx >= br.first_usable_day(res)]
    p = res["p"]
    sheets = {k: br.rule_sheet(pp) for k, (_, pp) in br.TIMEFRAMES.items()}
    return {
        "index": index, "indexes": indexes, "stocks": uni_count, "universeNote": uni_note, "bandNote": band_note,
        "fetchedAt": fetched_at.strftime("%d %b %Y, %H:%M IST"), "warnings": warnings,
        "tf": tf, "tfs": [[k, name] for k, (name, _) in br.TIMEFRAMES.items()],
        "unit": p["unit"], "units": p["units"], "partialLast": bool(partial_last),
        "dates": [d.strftime("%Y-%m-%d") for d in usable],
        "rules": [{"n": n, "layer": la, "name": nm, "rule": rule} for n, la, nm, rule in sheets[tf]],
        "ruleTable": [{"n": n, "name": nm, **{k: sheets[k][n - 1][3] for k in sheets}}
                      for n, la, nm, _ in sheets["D"]],
        "layers": br.LAYERS, "weights": p["weights"],
        "params": {k: (v if not isinstance(v, dict) else dict(v)) for k, v in p.items()},
    }


def excel_b64(path: str) -> str:
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")
