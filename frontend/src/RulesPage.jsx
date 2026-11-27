import React from "react";

const LAYER_NOTES = {
  A: "Which stocks are looked at.",
  B: "What happens on the breakout day.",
  C: "How the stock behaved before it.",
  D: "Gates that keep out late, stretched or jumpy stocks.",
};

const SCORE_ROWS = [
  ["Smooth trend", "R² of a straight line through the log of the last 65 closes (0 if it slopes down)", "smooth"],
  ["Tight base", "Base depth 3% scores full marks, 15% scores none, straight line between", "tight"],
  ["Small wicks", "Average body ÷ range of the last 20 candles", "body"],
  ["Few gaps", "Opening gaps of 3% or more in 20 days: none scores full, 4 or more score none", "gaps"],
  ["Calm volatility", "ATR20 ÷ price: 2% scores full, 8% scores none", "calm"],
];

export default function RulesPage({ meta }) {
  return (
    <main className="rules-page">
      <section className="intro">
        <h1>How a stock gets on the list</h1>
        <p>
          A momentum burst is a 3–5 day move that starts when a quiet stock breaks out of a tight base on a strong,
          high-volume day. These 17 rules translate that idea, from Stockbee's post on good momentum bursts, into
          exact checks on NSE daily candles. A stock is listed only if it passes all of them. The clean-chart
          score then ranks the stocks that pass.
        </p>
        <p className="small">
          Daily candles. "Today" is the breakout day. ATR20 is the average daily range (high minus low) over the 20
          days before it. Windows leave out the breakout day unless a rule says otherwise.
        </p>
      </section>

      <div className="layers">
        {["A", "B", "C", "D"].map((g) => (
          <section key={g} className={`layer L${g}`}>
            <h2>{meta.layers[g]}</h2>
            <p className="ln">{LAYER_NOTES[g]}</p>
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

      <section className="score-rules">
        <h2>Clean-chart score, out of 100</h2>
        <p className="ln">Used only to rank stocks that passed every rule.</p>
        <table>
          <thead><tr><th>Part</th><th>Measure</th><th className="r">Points</th></tr></thead>
          <tbody>
            {SCORE_ROWS.map(([name, how, k]) => (
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
