"""
Momentum burst scanner: the web app.

Run on your PC:   streamlit run app.py
The screen is a React app (frontend/, built into frontend/dist). This file loads the data, builds daily, weekly
or monthly candles, runs the rules (burst_rules.py), packs the results (payload.py) and hands them to the React
app. The command-line version (python scan_burst.py --timeframe D/W/M) gives the same results.
"""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import burst_data as bd
import burst_rules as br
import payload as pl
import scan_burst

st.set_page_config(page_title="Momentum Burst", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
  header[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
  [data-testid="stToolbar"], [data-testid="stDecoration"], footer { display: none !important; }
  .stApp { background: #EDF1F3; }
  .block-container, [data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: 100% !important; }
  [data-testid="stVerticalBlock"] { gap: 0 !important; }
  iframe { display: block; }
  .mb-loading { font-family: system-ui, sans-serif; color: #13233A; padding: 2rem 1.5rem 0.5rem; }
</style>
""", unsafe_allow_html=True)

INDEXES = ["Nifty Total Market", "Nifty 500"]
CACHE_DIR = os.path.join(tempfile.gettempdir(), "momentum_burst_cache")
FRONTEND = Path(__file__).parent / "frontend" / "dist"
if not (FRONTEND / "index.html").exists():
    st.error("The screen files are missing (frontend/dist). Build them with: cd frontend && npm install && npm run build")
    st.stop()
dashboard = components.declare_component("momentum_burst", path=str(FRONTEND))


# ════════════════════════════════════════════════════════════ data, shared by every visitor for 15 minutes
@st.cache_resource
def shared():
    return {}


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def get_index(name):
    return bd.load_index(name)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_bands():
    return bd.load_bands()


def get_data(index: str, tf: str, symbols: list[str], fresh: bool, slot) -> dict:
    """Candles for an index (downloaded at most every 15 minutes unless `fresh`) and the rule results for one
    timeframe. Only the latest index is kept, to keep memory use modest on Streamlit Cloud."""
    store = shared()
    hit = store.get(index)
    now = datetime.now(bd.IST)
    if not hit or fresh or now - hit["at"] >= timedelta(minutes=bd.CACHE_MINUTES):
        pkl = os.path.join(CACHE_DIR, f"candles_{index.replace(' ', '_')}.pkl")
        if fresh and os.path.exists(pkl):
            os.remove(pkl)
        slot.markdown(f'<div class="mb-loading">Downloading about five years of daily prices for {len(symbols)} '
                      f'stocks. The first load takes a few minutes.</div>', unsafe_allow_html=True)
        bar = slot.progress(0.0)

        def progress(msg):
            try:
                done, total = [int(x) for x in msg.split()[1::2][:2]]
                bar.progress(min(1.0, done / total), text=msg)
            except Exception:  # noqa: BLE001  (other messages)
                pass

        panel, missing = bd.load_candles(symbols, CACHE_DIR, index, progress)
        store.clear()
        hit = store[index] = {"at": now, "panel": panel, "missing": missing, "res": {}}
    if tf not in hit["res"]:
        slot.markdown('<div class="mb-loading">Applying the rules…</div>', unsafe_allow_html=True)
        panel = hit["panel"]
        if tf == "D":
            panel = {f: x.iloc[-bd.DAILY_BARS:] for f, x in panel.items()}
        bands, _ = get_bands()
        hit["res"][tf] = br.compute(br.to_timeframe(panel, tf), bands, br.TIMEFRAMES[tf][1])
    slot.empty()
    return {"at": hit["at"], "res": hit["res"][tf], "missing": hit["missing"]}


# ════════════════════════════════════════════════════════════ what the screen asked for
req = st.session_state.get("mb") or {}
index = req.get("index") if req.get("index") in INDEXES else INDEXES[0]
mode = "period" if req.get("mode") == "period" else "day"
tf = req.get("tf") if req.get("tf") in br.TIMEFRAMES else "D"
fresh = bool(req.get("refresh")) and req.get("refresh") != st.session_state.get("last_refresh")
if fresh:
    st.session_state["last_refresh"] = req.get("refresh")

slot = st.empty()
try:
    uni, uni_note = get_index(index)
    bands, band_note = get_bands()
    data = get_data(index, tf, uni["Symbol"].tolist(), fresh, slot)
except Exception as e:  # noqa: BLE001
    slot.empty()
    st.error(f"Could not load the data: {e}")
    st.stop()
res = data["res"]

dates = res["score"].index
usable = dates[dates >= br.first_usable_day(res)]


def pick_day(s, fallback):
    try:
        d = pd.Timestamp(s)
    except Exception:  # noqa: BLE001
        return fallback
    earlier = usable[usable <= d]
    return earlier[-1] if len(earlier) else fallback


if mode == "day":
    start = end = pick_day(req.get("day"), usable[-1])
    passed, near = br.scan_day(res, end)
else:
    preset = req.get("preset", 10)
    if preset == "custom":
        start = pick_day(req.get("start"), usable[max(0, len(usable) - 20)])
        end = pick_day(req.get("end"), usable[-1])
        if start > end:
            start, end = end, start
    else:
        n = int(preset) if str(preset).isdigit() else 10
        start, end = usable[-min(n, len(usable))], usable[-1]
    passed, near = br.scan_range(res, start, end)

info = uni.set_index("Symbol")
for df in (passed, near):
    if len(df):
        df["Company"] = df["Symbol"].map(info["Company Name"])
        df["Industry"] = df["Symbol"].map(info["Industry"])
        df["Chart"] = df["Symbol"].map(scan_burst.tv_link)

warnings = []
partial_last = not br.bar_is_complete(dates[-1], tf, datetime.now(bd.IST).replace(tzinfo=None))
if end == dates[-1]:
    f = bd.freshness_note(dates[-1]) if tf == "D" else None
    if f:
        warnings.append(f)
    if partial_last:
        warnings.append(f"This {res['p']['unit']} is not over yet: its candle runs to {dates[-1]:%d %b %Y} and will "
                        f"change until the {res['p']['unit']} ends, so its list is provisional.")
if bands is None:
    warnings.append("The price band rule (rule 4) was not applied: " + band_note)
if data["missing"]:
    m = data["missing"]
    warnings.append(f"Yahoo Finance had no prices for {len(m)} stock{'s' if len(m) != 1 else ''}: "
                    f"{', '.join(m[:12])}" + (" …" if len(m) > 12 else ""))

extra = [tuple(x.split("|", 1)) for x in req.get("need", []) if isinstance(x, str) and "|" in x][:5]
result = pl.build(res, mode, start, end, passed, near, extra)
fun = (pd.DataFrame([(r["step"], r["left"]) for r in result["funnel"]], columns=["Step", "Stocks left"])
       if mode == "day" else pd.DataFrame(result["perDay"]))
xlsx = scan_burst.write_excel(os.path.join(tempfile.gettempdir(), "momentum_burst_out"), index, end, passed, near,
                              fun, warnings, uni_note, band_note, period=(start, end) if mode == "period" else None,
                              tf=tf)

dashboard(
    meta=pl.meta(res, index, INDEXES, len(uni), uni_note, band_note, data["at"], warnings, tf, partial_last),
    result=result,
    excel={"name": os.path.basename(xlsx), "data": pl.excel_b64(xlsx)},
    key="mb",
    default=None,
)
