import React, { useEffect, useMemo, useState } from "react";
import { fmtDay, pct, tone } from "./util.js";

// One cell per rule (1-17), coloured by its layer when passed, hollow when failed.
export function RuleStrip({ rules, meta, size = "sm" }) {
  return (
    <span className={`strip ${size}`} aria-label={`${rules.filter(Boolean).length} of ${rules.length} rules passed`}>
      {rules.map((ok, i) => {
        const r = meta.rules[i];
        return (
          <i key={i} className={`c L${r.layer} ${ok ? "ok" : "no"}`}
             title={`${r.n}. ${r.name}: ${ok ? "passed" : "failed"}`} />
        );
      })}
    </span>
  );
}

const SORTS = {
  score: ["Clean-chart score", (a, b) => b.score - a.score],
  change: ["Day's change", (a, b) => b.change - a.change],
  risk: ["Lowest risk to stop", (a, b) => a.risk - b.risk],
  date: ["Newest first", (a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : b.score - a.score)],
  since: ["Change since breakout", (a, b) => (b.changeSince ?? -1e9) - (a.changeSince ?? -1e9)],
};

export default function CandidateList({ rows, list, onList, selectedId, onSelect, period, meta }) {
  const [sort, setSort] = useState(period ? "date" : "score");
  const [query, setQuery] = useState("");
  useEffect(() => setSort(period ? "date" : "score"), [period]);
  const sortKey = !period && (sort === "date" || sort === "since") ? "score" : sort;

  const shown = useMemo(() => {
    const q = query.trim().toUpperCase();
    const src = rows[list].filter((r) => !q || r.symbol.includes(q) || (r.company || "").toUpperCase().includes(q));
    return [...src].sort(SORTS[sortKey][1]);
  }, [rows, list, query, sortKey]);

  const onKey = (e) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const i = shown.findIndex((r) => r.id === selectedId);
    const next = shown[Math.min(shown.length - 1, Math.max(0, i + (e.key === "ArrowDown" ? 1 : -1)))];
    if (next) onSelect(next.id);
  };

  return (
    <section className="list" aria-label="Candidates">
      <div className="list-head">
        <div className="seg small" role="tablist">
          <button role="tab" aria-selected={list === "passed"} className={list === "passed" ? "on" : ""}
                  onClick={() => onList("passed")}>
            Passed <span className="n">{rows.passed.length}</span>
          </button>
          <button role="tab" aria-selected={list === "near"} className={list === "near" ? "on" : ""}
                  onClick={() => onList("near")}>
            Near misses <span className="n">{rows.near.length}</span>
          </button>
        </div>
        <div className="tools">
          <input type="search" placeholder="Find a stock" value={query} aria-label="Find a stock"
                 onChange={(e) => setQuery(e.target.value)} />
          <select aria-label="Sort" value={sortKey} onChange={(e) => setSort(e.target.value)}>
            {Object.entries(SORTS)
              .filter(([k]) => period || (k !== "date" && k !== "since"))
              .map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}
          </select>
        </div>
      </div>

      {shown.length === 0 ? (
        <div className="empty">
          {query
            ? "No stock in this list matches your search."
            : list === "passed"
              ? (rows.near.length ? "No stock passed every rule. Open Near misses to see what came closest."
                                  : "No breakout moves in this scan.")
              : "No near misses: no other stock made a 4% move on volume."}
        </div>
      ) : (
        <ul className="rows" role="listbox" tabIndex={0} onKeyDown={onKey} aria-label="Stocks">
          {shown.map((r) => (
            <li key={r.id} role="option" aria-selected={r.id === selectedId}
                className={r.id === selectedId ? "sel" : ""} onClick={() => onSelect(r.id)}>
              <div className="who">
                <span className="sym">{r.symbol}</span>
                <span className="co">{r.company}</span>
              </div>
              <div className="score" title="Clean-chart score out of 100">
                <span>{Math.round(r.score)}</span>
              </div>
              <div className={`chg ${tone(r.change)}`}>{pct(r.change)}</div>
              <div className="risk" title="Distance from the close to the stop">{pct(r.risk, 1, false)}</div>
              <div className="meta-line">
                <RuleStrip rules={r.rules} meta={meta} />
                {period && <span className="when">{fmtDay(r.date)}</span>}
                {period && r.daysSince > 0 && (
                  <span className={`since ${tone(r.changeSince)}`}>{pct(r.changeSince)} since</span>
                )}
                {r.stopHit && <span className="tag bad">stop hit</span>}
                {r.upperCircuit && <span className="tag warn">upper circuit</span>}
              </div>
              {list === "near" && r.failed && <div className="failed">{r.failed}</div>}
            </li>
          ))}
        </ul>
      )}
      <p className="list-foot">
        Columns: score, day's change, risk to the stop. The strip shows rules 1–17: filled = passed.
      </p>
    </section>
  );
}
