"""
Momentum burst scanner: Streamlit page.

Run on your PC:   streamlit run app.py
The rules are in burst_rules.py and the downloads in burst_data.py; this file only shows them.
The command-line version (python scan_burst.py) still works and gives the same results.
"""

import os
import tempfile
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

import burst_data as bd
import burst_rules as br
import scan_burst

st.set_page_config(page_title="Momentum Burst", page_icon="⚡", layout="wide")
CACHE_DIR = os.path.join(tempfile.gettempdir(), "momentum_burst_cache")
INDEXES = ["Nifty Total Market", "Nifty 500"]


# ════════════════════════════════════════════════════════════ data (cached)
@st.cache_data(ttl=24 * 3600, show_spinner=False)
def get_index(name):
    return bd.load_index(name)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_bands():
    return bd.load_bands()


@st.cache_data(ttl=bd.CACHE_MINUTES * 60, show_spinner=False)
def get_candles(name, symbols: tuple):
    bar = st.progress(0.0, text="Downloading daily candles from Yahoo Finance…")

    def progress(msg):
        try:
            done, total = [int(x) for x in msg.split()[1::2][:2]]
            bar.progress(done / total, text=msg)
        except Exception:  # noqa: BLE001  (other messages)
            pass

    panel, missing = bd.load_candles(list(symbols), CACHE_DIR, name, progress)
    bar.empty()
    return panel, missing, datetime.now(bd.IST)


@st.cache_data(ttl=bd.CACHE_MINUTES * 60, show_spinner=False, max_entries=4)
def get_result(name, fetched_at, _panel, _bands):
    """Rule values for every stock and day. Keyed by index and download time (the panel itself is not hashed)."""
    return br.compute(_panel, _bands)


# ════════════════════════════════════════════════════════════ chart
def candle_chart(res, sym, day, row, after=0):
    """Candles up to `after` sessions past the breakout day (0 = end at the breakout day)."""
    px = res["prices"]
    end = px["Close"].index.get_loc(day)
    last = min(len(px["Close"].index) - 1, end + after)
    idx = px["Close"].index[max(0, end - 119 + (last - end)): last + 1]
    df = pd.DataFrame({k: px[k].loc[idx, sym] for k in ("Open", "High", "Low", "Close", "Volume")})
    df["SMA65"] = res["m"]["sma65"].loc[idx, sym]
    df["Date"] = df.index
    df["up"] = df["Close"] >= df["Open"]
    base = alt.Chart(df).encode(x=alt.X("Date:T", axis=alt.Axis(format="%d %b", title=None)))
    color = alt.condition("datum.up", alt.value("#0b6b67"), alt.value("#c0392b"))
    wick = base.mark_rule().encode(y=alt.Y("Low:Q", scale=alt.Scale(zero=False), title="₹"), y2="High:Q",
                                   color=color)
    body = base.mark_bar(size=4).encode(y="Open:Q", y2="Close:Q", color=color,
                                        tooltip=[alt.Tooltip("Date:T", format="%d %b %Y"), "Open:Q", "High:Q",
                                                 "Low:Q", "Close:Q", alt.Tooltip("Volume:Q", format=",.0f")])
    sma = base.mark_line(color="#9aa5b1", strokeDash=[4, 3]).encode(y="SMA65:Q")
    layers = [wick, body, sma]
    marks = []
    if pd.notna(row.get("Base high")):
        n = int(row["Base days"])
        start = px["Close"].index[end - n]
        marks.append({"y": row["Base high"], "x0": start, "x1": day, "label": "Base high"})
    stop_from = px["Close"].index[max(0, end - 5)]           # stop line: a week before the breakout ...
    stop_to = px["Close"].index[last]                        # ... to the last candle shown
    marks.append({"y": row["Stop (day low)"], "x0": stop_from, "x1": stop_to, "label": "Stop"})
    mk = pd.DataFrame(marks)
    if last > end:                                          # breakout day marker when later candles are shown
        layers.append(alt.Chart(pd.DataFrame({"d": [day]})).mark_rule(color="#e6a23c", strokeDash=[2, 2])
                      .encode(x="d:T"))
    layers.append(alt.Chart(mk).mark_rule(strokeWidth=2, color="#e6a23c").encode(x="x0:T", x2="x1:T", y="y:Q"))
    layers.append(alt.Chart(mk).mark_text(align="left", dx=2, dy=-7, color="#b7791f", fontSize=11).encode(
        x="x0:T", y="y:Q", text="label"))
    price = alt.layer(*layers).properties(height=320, width="container")
    vol = base.mark_bar(size=4).encode(y=alt.Y("Volume:Q", title="Volume", axis=alt.Axis(format="~s")),
                                       color=color).properties(height=90, width="container")
    return alt.vconcat(price, vol).resolve_scale(x="shared")


NUM = st.column_config.NumberColumn


def column_config():
    cfg = {
        "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.0f"),
        "Close": NUM(format="%.2f"), "Change %": NUM(format="%+.1f"), "Close range %": NUM(format="%.0f"),
        "Volume x 50d avg": NUM("Vol x avg", format="%.1f"), "Range x ATR20": NUM(format="%.1f"),
        "Base days": NUM(format="%d"), "Base depth %": NUM(format="%.1f"), "Base high": NUM(format="%.2f"),
        "Stop (day low)": NUM("Stop", format="%.2f"), "Risk %": NUM(format="%.1f"),
        "Above SMA65 %": NUM(format="%.1f"), "Earlier bursts (30d)": NUM(format="%d"),
        "Erratic days (20d)": NUM(format="%d"), "Traded value Rs cr": NUM("Traded value ₹ cr", format="%.1f"),
        "Smooth R2": NUM(format="%.2f"), "Body share": NUM(format="%.2f"), "Gaps (20d)": NUM(format="%d"),
        "ATR %": NUM(format="%.1f"), "Price band %": NUM(format="%g"),
        "Chart": st.column_config.LinkColumn("Chart", display_text="TradingView"),
        "Date": st.column_config.DateColumn("Breakout day", format="DD MMM YYYY"),
        "Days since": NUM(format="%d"), "Latest close": NUM(format="%.2f"),
        "Change since %": NUM(format="%+.1f"), "High since %": NUM(format="%+.1f"),
        "Stop hit": st.column_config.CheckboxColumn("Stop hit since"),
    }
    for k in br.PARAMS["weights"]:
        cfg[f"Score: {k}"] = NUM(format="%.1f")
    return cfg


# ════════════════════════════════════════════════════════════ page
st.title("⚡ Momentum Burst Scanner")
st.caption("Stocks breaking out of a tight base on a strong, high-volume day. Rule sheet v1, daily candles, NSE.")
scan_tab, rules_tab = st.tabs(["Scan", "Rules"])

with st.sidebar:
    index = st.selectbox("Universe", INDEXES)
    st.caption("Candles are downloaded once and reused for 15 minutes. The first scan of an index takes "
               "one to three minutes.")
    refresh = st.button("Download fresh prices")

if refresh:
    get_candles.clear()
    get_result.clear()

with scan_tab:
    try:
        with st.spinner(f"Loading the {index} list…"):
            uni, uni_note = get_index(index)
            bands, band_note = get_bands()
        panel, missing, fetched_at = get_candles(index, tuple(uni["Symbol"]))
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not load the data: {e}")
        st.stop()
    with st.spinner("Applying the rules…"):
        res = get_result(index, fetched_at, panel, bands)
    dates = res["score"].index
    first_ok = br.first_usable_day(res)
    usable = dates[dates >= first_ok]
    with st.sidebar:
        mode = st.radio("Show", ["One day", "A period"], horizontal=True,
                        help="A period lists every breakout on any day in it, with what each stock did afterwards.")
        if mode == "One day":
            recent = [d.strftime("%Y-%m-%d") for d in usable[-60:][::-1]]
            pick = st.selectbox("Scan day", recent, format_func=lambda d: pd.Timestamp(d).strftime("%a %d %b %Y"),
                                help="The latest trading day first. Pick an earlier day to check past charts.")
            start = end = pd.Timestamp(pick)
        else:
            preset = st.selectbox("Period", ["Last 5 sessions", "Last 10 sessions", "Last 20 sessions",
                                             "Last 60 sessions", "Custom dates"], index=1)
            if preset == "Custom dates":
                rng = st.date_input("From – to", value=(usable[-20].date(), usable[-1].date()),
                                    min_value=usable[0].date(), max_value=usable[-1].date(), format="DD/MM/YYYY")
                if not isinstance(rng, (tuple, list)) or len(rng) != 2:
                    st.info("Pick the end date too.")
                    st.stop()
                start, end = pd.Timestamp(rng[0]), pd.Timestamp(rng[1])
            else:
                n = int(preset.split()[1])
                start, end = usable[-min(n, len(usable))], usable[-1]
            st.caption(f"Earliest day with enough history: {usable[0]:%d %b %Y}.")
    period = mode == "A period"
    day = end
    if period:
        passed, near = br.scan_range(res, start, end)
    else:
        passed, near = br.scan_day(res, day)
    info = uni.set_index("Symbol")
    for df in (passed, near):
        if len(df):
            pos = 2 if period else 1
            df.insert(pos, "Company", df["Symbol"].map(info["Company Name"]))
            df.insert(pos + 1, "Industry", df["Symbol"].map(info["Industry"]))
            df["Chart"] = df["Symbol"].map(scan_burst.tv_link)

    warns = []
    if day == dates[-1]:
        f = bd.freshness_note(dates[-1])
        if f:
            warns.append(f)
    if bands is None:
        warns.append("Rule 4 (price band) was not applied: " + band_note)
    if missing:
        warns.append(f"No candles from Yahoo for {len(missing)} stocks: {', '.join(missing[:12])}"
                     + (" …" if len(missing) > 12 else ""))
    for w in warns:
        st.warning(w)

    if period:
        counts = pd.DataFrame({"Day": [d for d in usable if start <= d <= end]})
        counts["Passed"] = counts["Day"].map(passed["Date"].value_counts() if len(passed) else {}).fillna(0).astype(int)
        counts["Near misses"] = counts["Day"].map(near["Date"].value_counts() if len(near) else {}).fillna(0).astype(int)
        fun = counts.assign(Day=counts["Day"].dt.strftime("%d %b %Y")).rename(columns={"Day": "Step"})
        c = st.columns(4)
        c[0].metric("Sessions", len(counts))
        c[1].metric("Breakouts that passed", len(passed))
        c[2].metric("Different stocks", passed["Symbol"].nunique() if len(passed) else 0)
        c[3].metric("Stop hit since", int(passed["Stop hit"].sum()) if len(passed) else 0,
                    help="Breakouts whose stock later traded at or below the breakout day's low")
    else:
        fun = br.funnel(res, day)
        c = st.columns(5)
        c[0].metric("Stocks scanned", int(fun.iloc[0, 1]))
        c[1].metric("Liquid universe", int(fun.iloc[1, 1]))
        c[2].metric("Breakout move", int(fun.iloc[2, 1]), help="Rules 2–9 passed")
        c[3].metric("Passed every rule", len(passed))
        c[4].metric("Near misses", len(near), help="Made the breakout move but failed a setup or quality rule")
    st.caption(f"{index}: {len(uni)} stocks ({uni_note}). Prices: Yahoo Finance, downloaded "
               f"{fetched_at:%d %b %H:%M} IST. Price bands: {band_note}.")

    when = f"{start:%d %b %Y} to {end:%d %b %Y}" if period else f"{day:%d %b %Y}"
    st.subheader(f"Passed every rule, {when}")
    show = ["Symbol", "Company", "Industry", "Score", "Close", "Change %", "Close range %", "Volume x 50d avg",
            "Base days", "Base depth %", "Stop (day low)", "Risk %", "Above SMA65 %", "Chart"]
    if period:
        show = ["Date"] + show[:5] + ["Change %", "Stop (day low)", "Days since", "Latest close", "Change since %",
                                      "High since %", "Stop hit", "Base days", "Base depth %", "Chart"]
        show = list(dict.fromkeys(show))
    if "At upper circuit?" in passed.columns:
        show.insert(-1, "At upper circuit?")
    if len(passed):
        st.dataframe(passed[[c for c in show if c in passed]], hide_index=True, width="stretch",
                     column_config=column_config())
        if period:
            st.caption("Change since and high since run from the breakout day's close to the latest candle. They "
                       "are not trade results: no stop, exit rule or costs are applied, and older breakouts have had "
                       "longer to move.")
        with st.expander("All measures for these stocks"):
            st.dataframe(passed, hide_index=True, width="stretch", column_config=column_config())
    else:
        st.info("No stock passed every rule in this period." if period else
                "No stock passed every rule on this day. The near misses below show what came closest.")

    st.subheader("Near misses")
    if len(near):
        cols = ["Symbol", "Company", "Failed rules", "Score", "Close", "Change %", "Close range %",
                "Volume x 50d avg", "Base days", "Base depth %", "Risk %", "Chart"]
        if period:
            cols = ["Date"] + cols[:-1] + ["Change since %", "Stop hit", "Chart"]
        if period and len(near) > 15:
            with st.expander(f"{len(near)} near misses"):
                st.dataframe(near[[c for c in cols if c in near]], hide_index=True, width="stretch",
                             column_config=column_config())
        else:
            st.dataframe(near[[c for c in cols if c in near]], hide_index=True, width="stretch",
                         column_config=column_config())
    else:
        st.write("None.")

    pick_from = pd.concat([passed.assign(List="Passed"), near.assign(List="Near miss")], ignore_index=True) \
        if len(passed) or len(near) else pd.DataFrame()
    if len(pick_from):
        st.subheader("Chart")
        if period:
            labels = [f"{r.Symbol}  {r.Date:%d %b}  ({r.List})" for r in pick_from.itertuples()]
        else:
            labels = [f"{r.Symbol}  ({r.List})" for r in pick_from.itertuples()]
        choice = st.selectbox("Stock", labels)
        row = pick_from.iloc[labels.index(choice)]
        bday = row["Date"] if period else day
        st.altair_chart(candle_chart(res, row["Symbol"], bday, row, after=30 if period else 0), width="stretch")
        st.caption("Orange lines: the base high (rule 12) and the stop at the breakout day's low"
                   + (", dotted line: the breakout day, with up to 30 sessions after it" if period else "")
                   + ". Dashed grey line: 65-day SMA.")

    path = scan_burst.write_excel(os.path.join(tempfile.gettempdir(), "momentum_burst_out"), index, day,
                                  passed, near, fun, warns, uni_note, band_note,
                                  period=(start, end) if period else None)
    with open(path, "rb") as fh:
        st.download_button("Download this scan (Excel)", fh.read(), os.path.basename(path),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with st.expander("Breakouts per day" if period else "How many stocks each layer removed"):
        st.dataframe(fun.rename(columns={"Step": "Day"}) if period else fun, hide_index=True)

with rules_tab:
    readme = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")
    try:
        text = open(readme, encoding="utf-8").read()
        start = text.index("## Rule sheet v1")
        end = text.index("## How it was checked")
        st.markdown(text[start:end])
    except (OSError, ValueError):
        st.write("See README.md for the rule sheet.")
    st.subheader("Numbers in use")
    st.dataframe(pd.DataFrame([(k, str(v)) for k, v in br.PARAMS.items()], columns=["Setting", "Value"]),
                 hide_index=True)
