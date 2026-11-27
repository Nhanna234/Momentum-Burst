import React from "react";
import { fmtDay } from "./util.js";

const STEP_NAMES = [
  ["Scanned", "stocks with a candle that day"],
  ["Liquid", "price, liquidity and price band (rules 2–4)"],
  ["Moved", "4%+ on volume, closing strong (rules 5–9)"],
  ["Set up", "quiet base, breakout, contraction (rules 10–13)"],
  ["Passed", "uptrend, early, not extended, orderly (rules 14–17)"],
];

function Funnel({ steps }) {
  const top = Math.max(1, steps[0]?.left || 1);
  return (
    <ol className="funnel" aria-label="How many stocks each layer of rules leaves">
      {steps.map((s, i) => {
        const [name, note] = STEP_NAMES[i] || [s.step, ""];
        // square-root scale, so 3 stocks out of 750 still shows as a bar
        const w = Math.max(2.5, Math.sqrt(s.left / top) * 100);
        return (
          <li key={s.step} className={i === steps.length - 1 ? "last" : ""}>
            <div className="count">{s.left.toLocaleString("en-IN")}</div>
            <div className="bar"><span style={{ width: `${w}%` }} /></div>
            <div className="label"><b>{name}</b> {note}</div>
          </li>
        );
      })}
    </ol>
  );
}

function PerDay({ days, passed, near }) {
  const max = Math.max(1, ...days.map((d) => d.passed + d.near));
  const distinct = new Set(passed.map((r) => r.symbol)).size;
  const stops = passed.filter((r) => r.stopHit).length;
  return (
    <div className="perday">
      <dl className="totals">
        <div><dt>Breakouts that passed</dt><dd>{passed.length}</dd></div>
        <div><dt>Different stocks</dt><dd>{distinct}</dd></div>
        <div><dt>Later fell to the stop</dt><dd>{stops}</dd></div>
        <div><dt>Near misses</dt><dd>{near.length}</dd></div>
      </dl>
      <div className="days" role="img"
           aria-label={`Breakouts per day over ${days.length} sessions`}>
        {days.map((d) => (
          <div key={d.date} className="day" title={`${fmtDay(d.date)}: ${d.passed} passed, ${d.near} near misses`}>
            <div className="stack">
              <span className="n" style={{ height: `${(d.near / max) * 100}%` }} />
              <span className="p" style={{ height: `${(d.passed / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
      <div className="days-axis">
        <span>{fmtDay(days[0]?.date)}</span>
        <span className="legend"><i className="p" /> passed <i className="n" /> near miss</span>
        <span>{fmtDay(days[days.length - 1]?.date)}</span>
      </div>
    </div>
  );
}

export default function Summary({ result }) {
  return (
    <section className="summary">
      {result.mode === "period"
        ? <PerDay days={result.perDay} passed={result.passed} near={result.near} />
        : <Funnel steps={result.funnel} />}
    </section>
  );
}
