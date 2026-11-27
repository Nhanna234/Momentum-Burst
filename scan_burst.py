"""
Momentum burst scanner: lists today's breakouts that pass rule sheet v1.

Run (in Command Prompt, in this folder):
    python scan_burst.py                          -> Nifty Total Market, latest day
    python scan_burst.py --index "Nifty 500"
    python scan_burst.py --date 2026-11-20        -> scan an earlier day (to check the rules on past charts)

Writes an Excel file to the output folder and prints a short summary.
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

import burst_data as bd
import burst_rules as br

HERE = os.path.dirname(os.path.abspath(__file__))


def tv_link(sym: str) -> str:
    return f"https://www.tradingview.com/chart/?symbol=NSE:{sym}"


def run(index: str, day: str | None, out_dir: str, progress=print, downloader=None,
        bands_loader=None, index_loader=None) -> dict:
    progress(f"Loading the {index} list…")
    uni, uni_note = (index_loader or bd.load_index)(index)
    progress(f"{len(uni)} stocks ({uni_note}). Loading NSE price bands…")
    bands, band_note = (bands_loader or bd.load_bands)()
    progress(band_note)
    panel, missing = bd.load_candles(uni["Symbol"].tolist(), os.path.join(HERE, "cache"), index, progress,
                                     downloader)
    res = br.compute(panel, bands)
    last = panel["Close"].index.max()
    scan_day = pd.Timestamp(day) if day else last
    if scan_day not in panel["Close"].index:
        earlier = panel["Close"].index[panel["Close"].index <= scan_day]
        if not len(earlier):
            raise SystemExit(f"No candles on or before {scan_day:%d %b %Y}.")
        progress(f"{scan_day:%d %b %Y} was not a trading day; using {earlier[-1]:%d %b %Y}.")
        scan_day = earlier[-1]
    passed, near = br.scan_day(res, scan_day)
    info = uni.set_index("Symbol")
    for df in (passed, near):
        if len(df):
            df.insert(1, "Company", df["Symbol"].map(info["Company Name"]))
            df.insert(2, "Industry", df["Symbol"].map(info["Industry"]))
            df["Chart"] = df["Symbol"].map(tv_link)
    warn = [w for w in [bd.freshness_note(last) if not day else None,
                        None if bands is not None else "Rule 4 (price band) was NOT applied: " + band_note,
                        f"No candles from Yahoo for {len(missing)} stocks: {', '.join(missing[:15])}"
                        + (" …" if len(missing) > 15 else "") if missing else None] if w]
    fun = br.funnel(res, scan_day)
    path = write_excel(out_dir, index, scan_day, passed, near, fun, warn, uni_note, band_note)
    return {"day": scan_day, "passed": passed, "near": near, "funnel": fun, "warnings": warn, "path": path,
            "res": res}


def settings_rows(index, day, uni_note, band_note):
    p = br.PARAMS
    rows = [("Index", index), ("Scan day", f"{day:%d %b %Y}"), ("Members", uni_note), ("Price bands", band_note),
            ("Candles", "Yahoo Finance daily, split-adjusted, not dividend-adjusted"), ("", "")]
    rows += [(k, str(v)) for k, v in p.items()]
    return pd.DataFrame(rows, columns=["Setting", "Value"])


def write_excel(out_dir, index, day, passed, near, fun, warn, uni_note, band_note, period=None) -> str:
    """period: (start, end) for a date-range scan; None for one day."""
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    os.makedirs(out_dir, exist_ok=True)
    tag = f"{period[0]:%Y-%m-%d}_to_{period[1]:%Y-%m-%d}" if period else f"{day:%Y-%m-%d}"
    when = f"{period[0]:%d %b %Y} to {period[1]:%d %b %Y}" if period else f"{day:%d %b %Y}"
    path = os.path.join(out_dir, f"burst_{index.replace(' ', '_')}_{tag}.xlsx")
    summary = pd.DataFrame({"": [f"Momentum burst scan: {index}, {when}",
                                 f"{len(passed)} stock(s) passed every rule; {len(near)} near miss(es).", ""]
                            + [f"Warning: {w}" for w in warn]})
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="Summary", index=False, header=False)
        fun.to_excel(xw, sheet_name="Summary", index=False, startrow=len(summary) + 1)
        (passed if len(passed) else pd.DataFrame({"Result": ["No stock passed every rule on this day."]})) \
            .to_excel(xw, sheet_name="Passed", index=False)
        (near if len(near) else pd.DataFrame({"Result": ["No near misses."]})).to_excel(xw, sheet_name="Near misses", index=False)
        settings_rows(index, day, uni_note, band_note).to_excel(xw, sheet_name="Settings", index=False)
        if period:
            xw.book["Settings"]["A3"], xw.book["Settings"]["B3"] = "Period", when
        head = PatternFill("solid", fgColor="0B6B67")
        for ws in xw.book.worksheets:
            name = ws.title
            for cell in ws[1 if name != "Summary" else len(summary) + 2]:
                if name != "Summary" or cell.value:
                    cell.font, cell.fill = Font(bold=True, color="FFFFFF"), head
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col[:60])
                ws.column_dimensions[get_column_letter(col[0].column)].width = min(48, max(9, width * 0.9))
            ws.freeze_panes = "B2" if name in ("Passed", "Near misses") else None
            if name in ("Passed", "Near misses") and ws.max_row > 1:
                hdr = [c.value for c in ws[1]]
                for j, h in enumerate(hdr, start=1):
                    fmt = None
                    if h == "Date":
                        fmt = "dd-mmm-yyyy"
                    elif h in ("Close", "Base high", "Stop (day low)", "Latest close"):
                        fmt = "#,##0.00"
                    elif h and ("%" in h or h.startswith("Score") or "x " in h or h in ("Smooth R2", "Body share")):
                        fmt = "0.0" if h != "Smooth R2" and h != "Body share" else "0.00"
                    elif h == "Traded value Rs cr":
                        fmt = "#,##0.0"
                    for i in range(2, ws.max_row + 1):
                        c = ws.cell(i, j)
                        if h == "Chart" and c.value:
                            c.hyperlink, c.value, c.font = c.value, "Open chart", Font(color="0563C1", underline="single")
                        elif fmt:
                            c.number_format = fmt
        xw.book["Summary"].column_dimensions["A"].width = 60
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Momentum burst scanner (rule sheet v1)")
    ap.add_argument("--index", default="Nifty Total Market", choices=["Nifty Total Market", "Nifty 500"])
    ap.add_argument("--date", default=None, help="scan an earlier day, e.g. 2026-11-20 (default: latest)")
    ap.add_argument("--out", default=os.path.join(HERE, "output"), help="folder for the Excel file")
    a = ap.parse_args(argv)
    try:
        out = run(a.index, a.date, a.out)
    except RuntimeError as e:
        print(f"\nStopped: {e}")
        sys.exit(1)
    print()
    for w in out["warnings"]:
        print("WARNING:", w)
    print(out["funnel"].to_string(index=False))
    p = out["passed"]
    print(f"\n{len(p)} stock(s) passed every rule on {out['day']:%d %b %Y}.")
    if len(p):
        cols = ["Symbol", "Score", "Close", "Change %", "Close range %", "Volume x 50d avg", "Base days",
                "Base depth %", "Stop (day low)", "Risk %"]
        print(p[cols].round(1).to_string(index=False))
    print(f"\nNear misses: {len(out['near'])}. Full details: {out['path']}")


if __name__ == "__main__":
    main()
