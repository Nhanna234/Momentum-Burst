import React from "react";

const layerNotes = (unit) => ({
  A: "Which stocks are looked at.",
  B: `What happens in the breakout ${unit}.`,
  C: "How the stock behaved before it.",
  D: "Gates that keep out late, stretched or jumpy stocks.",
});

const pc = (x) => `${Math.round(x * 1000) / 10}%`;
const scoreRows = (p) => [
  ["Smooth trend", `R² of a straight line through the log of the last ${p.r2_window} closes (0 if it slopes down)`,
   "smooth"],
  ["Tight base", `Base depth ${pc(p.base_depth_full)} scores full marks, ${pc(p.base_max_depth)} scores none, straight line between`, "tight"],
  ["Small wicks", `Average body ÷ range of the last ${p.body_window} candles`, "body"],
  ["Few gaps", `Opening gaps of ${pc(p.gap_size)} or more in ${p.gap_window} ${p.units}: none scores full, ${p.gaps_for_zero} or more score none`, "gaps"],
  ["Calm volatility", `ATR${p.atr_window} ÷ price: ${pc(p.atr_pct_full)} scores full, ${pc(p.atr_pct_zero)} scores none`, "calm"],
];

export default function RulesPage({ meta }) {
  const tfName = meta.tfs.find(([k]) => k === meta.tf)?.[1] || "Daily";
  return (
    <main className="rules-page">
      <section className="intro">
        <h1>How a stock gets on the list</h1>
        <p>
          A momentum burst is a 3–5 day move that starts when a quiet stock breaks out of a tight base on a strong,
          high-volume day. These 17 rules translate that idea, from Stockbee's post on good momentum bursts, into
          exact checks on NSE candles. A stock is listed only if it passes all of them. The clean-chart score then
          ranks the stocks that pass. Below are the rules for the {tfName.toLowerCase()} timeframe chosen on the
          Scanner page; the table further down compares all three.
        </p>
        <p className="small">
          "The {meta.unit}" is the breakout {meta.unit}. ATR{meta.params.atr_window} is the average range (high minus
          low) of the {meta.params.atr_window} {meta.units} before it. Windows leave out the breakout {meta.unit} unless
          a rule says otherwise.
        </p>
      </section>

      <div className="layers">
        {["A", "B", "C", "D"].map((g) => (
          <section key={g} className={`layer L${g}`}>
            <h2>{meta.layers[g]}</h2>
            <p className="ln">{layerNotes(meta.unit)[g]}</p>
            <ol>
              {meta.rules.filter((r) => r.layer === g).map((r) => (
                <li key={r.n} value={r.n}>
                  <b>{r.name}</b>
                  <span>{r.rule}</span>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>

      <section className="tf-table">
        <h2>Daily, weekly and monthly</h2>
        <p className="ln">
          Weekly and monthly candles are built from the daily prices: a week runs Monday to Friday, and each bar is
          dated by its last trading day. The same 17 rules apply, with windows counted in weeks or months and moves
          widened, because a week or a month moves more than a day. The weekly and monthly numbers are reasoned
          starting values, not yet tested by a backtest.
        </p>
        <div className="tf-scroll">
          <table>
            <thead><tr><th>Rule</th>{meta.tfs.map(([k, name]) => <th key={k}>{name}</th>)}</tr></thead>
            <tbody>
              {meta.ruleTable.filter((r) =>
                new Set(meta.tfs.map(([k]) => r[k])).size > 1).map((r) => (
                <tr key={r.n}>
                  <td><span className="rn">{r.n}</span> {r.name}</td>
                  {meta.tfs.map(([k]) => <td key={k} className={k === meta.tf ? "cur" : ""}>{r[k]}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="small">Rules not listed (in the index, price, price band, green candle, breakout) are the same
          on every timeframe.</p>
      </section>

      <section className="score-rules">
        <h2>Clean-chart score, out of 100 ({tfName.toLowerCase()})</h2>
        <p className="ln">Used only to rank stocks that passed every rule.</p>
        <table>
          <thead><tr><th>Part</th><th>Measure</th><th className="r">Points</th></tr></thead>
          <tbody>
            {scoreRows(meta.params).map(([name, how, k]) => (
              <tr key={k}><td>{name}</td><td>{how}</td><td className="r">{meta.weights[k]}</td></tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="limits">
        <h2>What the scan does not know</h2>
        <ul>
          <li>Index lists are today's, so a backtest would miss stocks that have since left the index.</li>
          <li>Price bands come from today's NSE list. Float is not used.</li>
          <li>Prices are split-adjusted but not dividend-adjusted, so the close and the stop are real traded prices.</li>
          <li>Stops, exits and position size are not tested yet. That is the backtest, the next stage.</li>
        </ul>
        <p className="small">Price bands: {meta.bandNote}. Index members: {meta.universeNote}.</p>
      </section>
    </main>
  );
}
