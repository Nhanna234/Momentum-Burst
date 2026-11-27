import React from "react";
import PriceChart from "./PriceChart.jsx";
import { cap, fmtBar, inr, num, pct, tone } from "./util.js";

const partNames = (p) => ({
  smooth: ["Smooth trend", `how straight the last ${p.r2_window} closes are`],
  tight: ["Tight base", "shallower base scores more"],
  body: ["Small wicks", `candle bodies vs. their range, ${p.body_window} ${p.units}`],
  gaps: ["Few gaps", `opening gaps of ${Math.round(p.gap_size * 100)}%+ in ${p.gap_window} ${p.units}`],
  calm: ["Calm volatility", `average ${p.unit}'s range as % of price`],
});

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
  const PART_NAMES = partNames(meta.params);
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
            {row.company}{row.industry ? `, ${row.industry}` : ""}. Breakout{" "}
            {meta.unit === "day" ? `on ${fmtBar(row.date, "D")}` : meta.unit === "week"
              ? `in the week to ${fmtBar(row.date, "W").replace("Week to ", "")}` : `in ${fmtBar(row.date, "M")}`}.
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
        <Figure label={`${cap(meta.unit)}'s change`} value={pct(row.change)} toneClass={tone(row.change)} />
        <Figure label={`Stop (${meta.unit}'s low)`} value={inr(row.stop)}
                sub={riskRs != null ? `${inr(riskRs)} a share` : null} />
        <Figure label="Risk to stop" value={pct(row.risk, 1, false)} />
        <Figure label="Volume" value={`${num(row.volRatio, 1)}×`}
                sub={`${meta.params.vol_avg_window}-${meta.unit} average`} />
        <Figure label="Base" value={row.baseDays ? `${row.baseDays} ${meta.units}` : "–"}
                sub={row.baseDepth != null ? `${num(row.baseDepth, 1)}% deep` : null} />
        {period && row.daysSince > 0 && (
          <Figure label={`Since, ${row.daysSince} ${row.daysSince === 1 ? meta.unit : meta.units}`}
                  value={pct(row.changeSince)}
                  toneClass={tone(row.changeSince)} sub={`high ${pct(row.highSince)}`} />
        )}
      </dl>

      <PriceChart chart={chart} theme={theme} />
      <p className="chart-note">
        {cap(meta.unit === "day" ? "daily" : `${meta.unit}ly`)} candles. Orange line: the base high. Red dotted line: the
        stop. Grey dashed line: {meta.params.sma_window}-{meta.unit} SMA.
        {period ? ` Up to 30 ${meta.units} after the breakout are shown.` : ""}
      </p>

      <div className="why">
        {chart ? <Checklist checks={chart.checks} meta={meta} /> : <div className="checklist loading">Loading the rules…</div>}
        <ScoreParts row={row} meta={meta} />
      </div>
      {period && row.daysSince > 0 && (
        <p className="caveat">
          "Since" figures run from the breakout {meta.unit}'s close to the latest close. They are not trade results: no exit
          rule or costs are applied, and older breakouts have had longer to move.
        </p>
      )}
    </section>
  );
}
