import React from "react";
import PriceChart from "./PriceChart.jsx";
import { fmtDate, inr, num, pct, tone } from "./util.js";

const PART_NAMES = {
  smooth: ["Smooth trend", "how straight the last 65 closes are"],
  tight: ["Tight base", "shallower base scores more"],
  body: ["Small wicks", "candle bodies vs. their range, 20 days"],
  gaps: ["Few gaps", "opening gaps of 3%+ in 20 days"],
  calm: ["Calm volatility", "daily range as % of price"],
};

function Figure({ label, value, sub, toneClass = "" }) {
  return (
    <div className="fig">
      <dt>{label}</dt>
      <dd className={toneClass}>{value}</dd>
      {sub && <dd className="sub">{sub}</dd>}
    </div>
  );
}

function Checklist({ checks, meta }) {
  const groups = ["A", "B", "C", "D"];
  return (
    <div className="checklist">
      {groups.map((g) => (
        <div key={g} className={`group L${g}`}>
          <h4>{meta.layers[g]}</h4>
          <ul>
            {checks.filter((c) => c.layer === g).map((c) => (
              <li key={c.n} className={c.pass ? "ok" : "no"}>
                <span className="mark" aria-label={c.pass ? "passed" : "failed"}>{c.pass ? "✓" : "✕"}</span>
                <span className="rn">{c.n}</span>
                <span className="nm">{c.name}</span>
                <span className="val">{c.value}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function ScoreParts({ row, meta }) {
  return (
    <div className="parts">
      <div className="total">
        <span className="big">{Math.round(row.score)}</span>
        <span className="of">/ 100 clean-chart score</span>
      </div>
      <ul>
        {Object.entries(meta.weights).map(([k, w]) => {
          const v = row.parts?.[k] ?? 0;
          const [name, note] = PART_NAMES[k];
          return (
            <li key={k}>
              <div className="pl"><b>{name}</b><span>{num(v, 1)} / {w}</span></div>
              <div className="pbar"><span style={{ width: `${(v / w) * 100}%` }} /></div>
              <div className="pn">{note}</div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function Detail({ row, chart, meta, theme, period }) {
  if (!row) {
    return (
      <section className="detail empty-detail">
        <p>Pick a stock from the list to see its chart, the rules it passed and its score.</p>
      </section>
    );
  }
  const riskRs = row.close != null && row.stop != null ? row.close - row.stop : null;
  return (
    <section className="detail" aria-label={`${row.symbol} details`}>
      <header className="dhead">
        <div>
          <h2>{row.symbol}<span className={`kind ${row.kind}`}>{row.kind === "passed" ? "Passed" : "Near miss"}</span></h2>
          <p className="dsub">
            {row.company}{row.industry ? `, ${row.industry}` : ""}. Breakout on {fmtDate(row.date)}.
          </p>
        </div>
        <a className="ghost link" href={row.tvLink} target="_blank" rel="noreferrer">Open in TradingView</a>
      </header>

      {(row.upperCircuit || row.fno || row.failed) && (
        <div className="flags">
          {row.upperCircuit && <span className="tag warn">Closed at its upper circuit: a buy may not fill</span>}
          {row.fno && <span className="tag">F&amp;O stock, no price band</span>}
          {row.failed && <span className="tag bad">Failed: {row.failed}</span>}
        </div>
      )}

      <dl className="figs">
        <Figure label="Close" value={inr(row.close)} />
        <Figure label="Day's change" value={pct(row.change)} toneClass={tone(row.change)} />
        <Figure label="Stop (day's low)" value={inr(row.stop)} sub={riskRs != null ? `${inr(riskRs)} a share` : null} />
        <Figure label="Risk to stop" value={pct(row.risk, 1, false)} />
        <Figure label="Volume" value={`${num(row.volRatio, 1)}×`} sub="50-day average" />
        <Figure label="Base" value={row.baseDays ? `${row.baseDays} days` : "–"}
                sub={row.baseDepth != null ? `${num(row.baseDepth, 1)}% deep` : null} />
        {period && row.daysSince > 0 && (
          <Figure label={`Since, ${row.daysSince} sessions`} value={pct(row.changeSince)}
                  toneClass={tone(row.changeSince)} sub={`high ${pct(row.highSince)}`} />
        )}
      </dl>

      <PriceChart chart={chart} theme={theme} />
      <p className="chart-note">
        Daily candles. Orange line: the base high. Red dotted line: the stop. Grey dashed line: 65-day SMA.
        {period ? " Up to 30 sessions after the breakout are shown." : ""}
      </p>

      <div className="why">
        {chart ? <Checklist checks={chart.checks} meta={meta} /> : <div className="checklist loading">Loading the rules…</div>}
        <ScoreParts row={row} meta={meta} />
      </div>
      {period && row.daysSince > 0 && (
        <p className="caveat">
          "Since" figures run from the breakout day's close to the latest close. They are not trade results: no exit
          rule or costs are applied, and older breakouts have had longer to move.
        </p>
      )}
    </section>
  );
}
