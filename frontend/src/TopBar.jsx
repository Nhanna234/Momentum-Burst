import React from "react";
import { fmtWeekday } from "./util.js";

const PRESETS = [5, 10, 20, 60];

function Segmented({ label, value, options, onChange }) {
  return (
    <div className="seg" role="radiogroup" aria-label={label}>
      {options.map(([v, text]) => (
        <button key={v} role="radio" aria-checked={value === v} className={value === v ? "on" : ""}
                onClick={() => value !== v && onChange(v)}>
          {text}
        </button>
      ))}
    </div>
  );
}

function DayPicker({ dates, day, onDay }) {
  const i = Math.max(0, dates.indexOf(day));
  const recent = dates.slice(-120).reverse();
  return (
    <div className="daypick">
      <button className="icon" aria-label="Previous trading day" disabled={i <= 0}
              onClick={() => onDay(dates[i - 1])}>‹</button>
      <select aria-label="Scan day" value={day} onChange={(e) => onDay(e.target.value)}>
        {recent.map((d) => <option key={d} value={d}>{fmtWeekday(d)}</option>)}
      </select>
      <button className="icon" aria-label="Next trading day" disabled={i >= dates.length - 1}
              onClick={() => onDay(dates[i + 1])}>›</button>
    </div>
  );
}

function PeriodPicker({ dates, req, onChange }) {
  const custom = req.preset === "custom";
  return (
    <div className="periodpick">
      <div className="chips" role="radiogroup" aria-label="Period">
        {PRESETS.map((n) => (
          <button key={n} role="radio" aria-checked={req.preset === n} className={req.preset === n ? "on" : ""}
                  onClick={() => onChange({ ...req, preset: n })}>
            {n} days
          </button>
        ))}
        <button role="radio" aria-checked={custom} className={custom ? "on" : ""}
                onClick={() => onChange({ ...req, preset: "custom",
                                          start: req.start || dates[Math.max(0, dates.length - 20)],
                                          end: req.end || dates[dates.length - 1] })}>
          Dates
        </button>
      </div>
      {custom && (
        <div className="range">
          <input type="date" aria-label="From" value={req.start} min={dates[0]} max={dates[dates.length - 1]}
                 onChange={(e) => e.target.value && onChange({ ...req, start: e.target.value })} />
          <span>to</span>
          <input type="date" aria-label="To" value={req.end} min={dates[0]} max={dates[dates.length - 1]}
                 onChange={(e) => e.target.value && onChange({ ...req, end: e.target.value })} />
        </div>
      )}
    </div>
  );
}

export default function TopBar({ meta, req, onChange, busy, theme, onTheme, tab, onTab, onRefresh, onExcel }) {
  const dates = meta.dates;
  return (
    <header className="topbar">
      <div className="brand">
        <svg className="spark" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M3 17h5l2-6 3 9 3-13 2 10h3" fill="none" strokeWidth="2.2" strokeLinecap="round"
                strokeLinejoin="round" />
        </svg>
        <span>Momentum Burst</span>
      </div>
      <nav className="tabs" aria-label="Pages">
        <button className={tab === "scan" ? "on" : ""} onClick={() => onTab("scan")}>Scanner</button>
        <button className={tab === "rules" ? "on" : ""} onClick={() => onTab("rules")}>Rules</button>
      </nav>

      {tab === "scan" && (
        <div className="controls">
          <Segmented label="Universe" value={req.index}
                     options={meta.indexes.map((x) => [x, x.replace("Nifty ", "")])}
                     onChange={(v) => onChange({ ...req, index: v })} />
          <Segmented label="View" value={req.mode} options={[["day", "One day"], ["period", "Period"]]}
                     onChange={(v) => onChange({ ...req, mode: v, day: v === "day" ? dates[dates.length - 1] : req.day })} />
          {req.mode === "day"
            ? <DayPicker dates={dates} day={req.day} onDay={(d) => onChange({ ...req, day: d })} />
            : <PeriodPicker dates={dates} req={req} onChange={onChange} />}
        </div>
      )}

      <div className="actions">
        {tab === "scan" && (
          <>
            <button className="ghost" onClick={onRefresh} disabled={busy}
                    title="Download prices again (useful just after 3:30 pm)">
              Refresh prices
            </button>
            <button className="ghost" onClick={onExcel}>Download Excel</button>
          </>
        )}
        <button className="icon theme" onClick={onTheme}
                aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}>
          {theme === "light" ? (
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" fill="currentColor" /></svg>
          ) : (
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><circle cx="12" cy="12" r="4.5" fill="currentColor" /><g stroke="currentColor" strokeWidth="2" strokeLinecap="round">{[0,45,90,135,180,225,270,315].map((a) => <line key={a} x1="12" y1="2.5" x2="12" y2="4.5" transform={`rotate(${a} 12 12)`} />)}</g></svg>
          )}
        </button>
      </div>
    </header>
  );
}
