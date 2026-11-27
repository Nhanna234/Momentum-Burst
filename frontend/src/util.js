// Number and date formatting used across the screen.

const DATE_FMT = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" });
const DATE_SHORT = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short" });
const WEEKDAY = new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "2-digit", month: "short", year: "numeric" });

const asDate = (s) => new Date(`${s}T00:00:00`);
export const fmtDate = (s) => (s ? DATE_FMT.format(asDate(s)) : "–");
export const fmtDay = (s) => (s ? DATE_SHORT.format(asDate(s)) : "–");
export const fmtWeekday = (s) => (s ? WEEKDAY.format(asDate(s)) : "–");
const MONTH = new Intl.DateTimeFormat("en-IN", { month: "short", year: "numeric" });

// How one bar is named: the day, the week (by its last trading day) or the month.
export function fmtBar(s, tf, short = false) {
  if (!s) return "–";
  if (tf === "M") return MONTH.format(asDate(s));
  if (tf === "W") return `${short ? "wk to" : "Week to"} ${(short ? DATE_SHORT : DATE_FMT).format(asDate(s))}`;
  return short ? DATE_SHORT.format(asDate(s)) : WEEKDAY.format(asDate(s));
}

export const cap = (w) => (w ? w[0].toUpperCase() + w.slice(1) : w);

const isNum = (x) => typeof x === "number" && Number.isFinite(x);

// Indian digit grouping: 12,34,567.89
export function inr(x, nd = 2) {
  if (!isNum(x)) return "–";
  return "₹" + x.toLocaleString("en-IN", { minimumFractionDigits: nd, maximumFractionDigits: nd });
}

export function num(x, nd = 1) {
  if (!isNum(x)) return "–";
  return x.toLocaleString("en-IN", { minimumFractionDigits: nd, maximumFractionDigits: nd });
}

export function pct(x, nd = 1, sign = true) {
  if (!isNum(x)) return "–";
  const s = x.toFixed(nd);
  return (sign && x > 0 ? "+" : "") + s + "%";
}

export const tone = (x) => (!isNum(x) ? "" : x > 0 ? "up" : x < 0 ? "down" : "");

export function downloadBase64(name, b64, mime) {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function readPref(key, fallback) {
  try {
    const v = window.localStorage.getItem(key);
    return v === null ? fallback : v;
  } catch {
    return fallback;
  }
}

export function writePref(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage can be blocked inside the Streamlit frame; the choice then lasts for this visit only */
  }
}
