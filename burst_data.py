"""
Downloads for the scanner: index member lists (NSE Indices), NSE price bands, and daily candles (Yahoo Finance).
Nothing here applies a rule; burst_rules.py does that.
"""

from __future__ import annotations

import io
import os
import pickle
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

IST = timezone(timedelta(hours=5, minutes=30))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
INDEX_FILES = {"Nifty Total Market": "ind_niftytotalmarket_list.csv", "Nifty 500": "ind_nifty500list.csv",
               "Nifty Microcap 250": "ind_niftymicrocap250_list.csv"}
CONSTITUENT_MIRRORS = ["https://niftyindices.com/IndexConstituent/{f}",
                       "https://www.niftyindices.com/IndexConstituent/{f}",
                       "https://nsearchives.nseindia.com/content/indices/{f}"]
BAND_URLS = ["https://nsearchives.nseindia.com/content/equities/sec_list.csv",
             "https://nsearchives.nseindia.com/content/equities/sec_list_{d}.csv"]
HISTORY_DAYS = 2000             # calendar days of daily candles fetched (about 5.5 years), enough for monthly
                                # bars: the monthly rules need 37 months of history before their first scan
DAILY_BARS = 520                # the daily rules use only the last ~2 years, to keep memory use modest
CACHE_MINUTES = 15              # a download younger than this is reused


def now_ist() -> datetime:
    return datetime.now(IST)


def _get(url: str, timeout: int = 25) -> str:
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/csv,*/*"}, timeout=timeout)
    r.raise_for_status()
    return r.text


def clean_symbol(s) -> str:
    s = str(s).strip().upper()
    return s.removeprefix("NSE:").removesuffix(".NS")


# ═══════════════════════════════════════════════════════════ index members
def _index_csv(fname: str) -> pd.DataFrame:
    errors = []
    for m in CONSTITUENT_MIRRORS:
        url = m.format(f=fname)
        try:
            df = pd.read_csv(io.StringIO(_get(url)))
            df.columns = [str(c).strip() for c in df.columns]
            if "Symbol" not in df.columns or df.empty:
                raise ValueError("no 'Symbol' column")
            return df
        except Exception as e:  # noqa: BLE001
            errors.append(f"{url}: {e}")
    raise RuntimeError("\n".join(errors))


def load_index(name: str) -> tuple[pd.DataFrame, str]:
    """(table with Symbol, Company Name, Industry; where it came from)."""
    try:
        df, note = _index_csv(INDEX_FILES[name]), "official NSE Indices list"
    except Exception as first:  # noqa: BLE001
        if name != "Nifty Total Market":
            raise RuntimeError(f"Could not download the {name} list.\n{first}") from None
        # NSE's own definition: Nifty Total Market = Nifty 500 + Nifty Microcap 250
        df = pd.concat([_index_csv(INDEX_FILES["Nifty 500"]), _index_csv(INDEX_FILES["Nifty Microcap 250"])])
        note = "built from the Nifty 500 and Nifty Microcap 250 lists"
    if "Series" in df.columns:
        df = df[df["Series"].astype(str).str.strip().isin(["EQ", "BE", "BZ"])]
    for c in ("Company Name", "Industry"):
        if c not in df.columns:
            df[c] = ""
    df = df.assign(Symbol=df["Symbol"].map(clean_symbol)).drop_duplicates("Symbol")
    return df[["Symbol", "Company Name", "Industry"]].reset_index(drop=True), note


# ═══════════════════════════════════════════════════════════ price bands
def parse_bands(text: str) -> pd.Series:
    """NSE's complete list of price bands -> {symbol: band %}; np.inf where there is no band (F&O stocks).
    Reads the columns by name, so a reordered file still works. Only EQ / BE / BZ rows are kept."""
    df = pd.read_csv(io.StringIO(text))
    df.columns = [str(c).strip().lower() for c in df.columns]
    sym = next((c for c in df.columns if c == "symbol"), None)
    band = next((c for c in df.columns if "band" in c), None)
    if sym is None or band is None:
        raise ValueError(f"unexpected columns: {list(df.columns)}")
    ser = next((c for c in df.columns if c == "series"), None)
    if ser:
        df = df[df[ser].astype(str).str.strip().isin(["EQ", "BE", "BZ"])]
    raw = df[band].astype(str).str.strip().str.lower()
    val = pd.to_numeric(raw.str.replace("%", "", regex=False), errors="coerce")
    val[raw.str.contains("no band")] = np.inf
    out = pd.Series(val.values, index=df[sym].map(clean_symbol))
    return out[~out.index.duplicated(keep="first")].dropna()


def load_bands() -> tuple[pd.Series | None, str]:
    """(bands or None, note). Tries today's file, then the last few weekdays' dated files."""
    tries = [BAND_URLS[0]]
    d = now_ist().date()
    for _ in range(6):
        tries.append(BAND_URLS[1].format(d=d.strftime("%d%m%Y")))
        d -= timedelta(days=1)
    errors = []
    for url in tries:
        try:
            s = parse_bands(_get(url))
            if len(s) > 500:
                return s, f"NSE price band list ({url.rsplit('/', 1)[-1]}, {len(s)} securities)"
            errors.append(f"{url}: only {len(s)} rows")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{url}: {e}")
    return None, "NOT CHECKED: the NSE price band list could not be downloaded (" + errors[0][:120] + ")"


# ═══════════════════════════════════════════════════════════ candles
def _yahoo(tickers: list[str], start: str) -> dict[str, pd.DataFrame]:
    import yfinance as yf
    raw = yf.download(tickers, start=start, auto_adjust=False, actions=False, progress=False, threads=True,
                      group_by="column")
    out = {}
    if raw is None or raw.empty:
        return out
    if not isinstance(raw.columns, pd.MultiIndex):
        raw.columns = pd.MultiIndex.from_product([raw.columns, tickers[:1]])
    raw.index = pd.to_datetime(raw.index).tz_localize(None).normalize()
    for t in tickers:
        try:
            df = raw.xs(t, level=1, axis=1)[["Open", "High", "Low", "Close", "Volume"]]
        except KeyError:
            continue
        df = df.dropna(subset=["Close"])
        if len(df):
            out[t.removesuffix(".NS")] = df.astype("float64")
    return out


def load_candles(symbols: list[str], cache_dir: str, label: str, progress=print,
                 downloader=None) -> tuple[dict, list[str]]:
    """Daily candles as traded (split-adjusted by Yahoo, not dividend-adjusted, so the close and the stop are
    real rupee prices). Returns ({field: DataFrame dates x symbols}, symbols with no data).
    A download younger than CACHE_MINUTES is reused."""
    downloader = downloader or _yahoo
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"candles_{label.replace(' ', '_')}.pkl")
    if os.path.exists(path):
        with open(path, "rb") as fh:
            saved = pickle.load(fh)
        if saved["at"] > now_ist() - timedelta(minutes=CACHE_MINUTES) and set(symbols) <= set(saved["asked"]):
            progress(f"Using candles downloaded at {saved['at']:%H:%M}.")
            return saved["panel"], saved["missing"]
    start = (now_ist().date() - timedelta(days=HISTORY_DAYS)).isoformat()
    got: dict[str, pd.DataFrame] = {}
    batch = 50
    for i in range(0, len(symbols), batch):
        chunk = [f"{s}.NS" for s in symbols[i:i + batch]]
        for attempt in range(3):
            try:
                got.update(downloader(chunk, start))
                break
            except Exception:  # noqa: BLE001
                time.sleep(2 * (attempt + 1))
        progress(f"Downloaded {min(i + batch, len(symbols))} of {len(symbols)} stocks")
        time.sleep(0.5)
    missing = [s for s in symbols if s not in got]
    if missing and len(missing) < len(symbols):                 # one slower retry for the gaps
        for i in range(0, len(missing), 20):
            try:
                got.update(downloader([f"{s}.NS" for s in missing[i:i + 20]], start))
            except Exception:  # noqa: BLE001
                pass
        missing = [s for s in symbols if s not in got]
    if not got:
        raise RuntimeError("Yahoo Finance returned no candles. It may be down or limiting requests; "
                           "wait a few minutes and run again.")
    panel = {f: pd.concat({s: df[f] for s, df in got.items()}, axis=1).sort_index()
             for f in ("Open", "High", "Low", "Close", "Volume")}
    with open(path, "wb") as fh:
        pickle.dump({"at": now_ist(), "asked": symbols, "panel": panel, "missing": missing}, fh)
    return panel, missing


def freshness_note(last_day: pd.Timestamp) -> str | None:
    """A warning when the latest candle is not today's final candle."""
    now = now_ist()
    today = pd.Timestamp(now.date())
    if now.weekday() >= 5:
        return None
    if last_day < today and (now.hour, now.minute) >= (15, 35):
        return (f"The latest candle is {last_day:%d %b %Y}: Yahoo has not published today's yet. "
                "Run again in a few minutes for today's scan.")
    if last_day == today and (now.hour, now.minute) < (15, 35):
        return ("The market is still open: today's candle is incomplete (volume especially), "
                "so today's list is provisional.")
    return None
