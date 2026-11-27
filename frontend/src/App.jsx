import React, { useEffect, useMemo, useRef, useState } from "react";
import { connect, embedded, sendValue, setFrameHeight } from "./streamlit.js";
import { downloadBase64, fmtBar, readPref, writePref } from "./util.js";
import TopBar from "./TopBar.jsx";
import Summary from "./Summary.jsx";
import CandidateList from "./CandidateList.jsx";
import Detail from "./Detail.jsx";
import RulesPage from "./RulesPage.jsx";

const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

export default function App() {
  const [args, setArgs] = useState(null);
  const [req, setReq] = useState(null);
  const [busy, setBusy] = useState(false);
  const [theme, setTheme] = useState(() => readPref("mb-theme", "light"));
  const [tab, setTab] = useState("scan");
  const [list, setList] = useState("passed");
  const [selectedId, setSelectedId] = useState(null);
  const asked = useRef(new Set());

  // data from Python
  useEffect(() => connect((a) => {
    setArgs(a);
    setBusy(false);
  }), []);

  // the request starts from what Python last sent
  useEffect(() => {
    if (!args || req) return;
    const r = args.result;
    setReq({ index: args.meta.index, tf: args.meta.tf, mode: r.mode, day: r.end, preset: 10, start: r.start,
             end: r.end });
  }, [args, req]);

  // keep the frame as tall as the content
  useEffect(() => {
    if (!embedded) return;
    const ro = new ResizeObserver(() => setFrameHeight(document.documentElement.scrollHeight));
    ro.observe(document.body);
    return () => ro.disconnect();
  }, []);

  useEffect(() => writePref("mb-theme", theme), [theme]);

  const result = args?.result;
  const rows = useMemo(() => (result ? { passed: result.passed, near: result.near } : { passed: [], near: [] }),
    [result]);

  // keep a sensible selection whenever the results change
  useEffect(() => {
    if (!result) return;
    const all = [...result.passed, ...result.near];
    if (!all.some((r) => r.id === selectedId)) {
      const first = result.passed[0] || result.near[0];
      setSelectedId(first ? first.id : null);
      setList(result.passed.length || !result.near.length ? "passed" : "near");
    }
  }, [result]); // eslint-disable-line react-hooks/exhaustive-deps

  const send = (next, need = []) => {
    setReq(next);
    setBusy(true);
    sendValue({ ...next, need, sent: Date.now() });
  };

  const selected = useMemo(() => [...rows.passed, ...rows.near].find((r) => r.id === selectedId) || null,
    [rows, selectedId]);
  const chart = selected && result ? result.charts[selected.id] : null;

  // a near miss far down the list has no chart yet: ask Python for it once
  useEffect(() => {
    if (!selected || chart || !req || asked.current.has(selected.id)) return;
    asked.current.add(selected.id);
    send(req, [selected.id]);
  }, [selected, chart]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!args || !req) {
    return <div className="boot">Loading the scanner…</div>;
  }
  const { meta, excel } = args;
  const period = result.mode === "period";
  const tfName = meta.tfs.find(([k]) => k === meta.tf)?.[1] || "Daily";
  const heading = period
    ? `${tfName} breakouts, ${fmtBar(result.start, meta.tf)} to ${fmtBar(result.end, meta.tf)}`
    : `${tfName} breakouts, ${fmtBar(result.end, meta.tf)}`;

  return (
    <div className={`app theme-${theme}`} data-busy={busy || undefined}>
      <TopBar
        meta={meta}
        req={req}
        onChange={(next) => send(next)}
        busy={busy}
        theme={theme}
        onTheme={() => setTheme(theme === "light" ? "dark" : "light")}
        tab={tab}
        onTab={setTab}
        onRefresh={() => send({ ...req, refresh: Date.now() })}
        onExcel={() => downloadBase64(excel.name, excel.data, XLSX)}
      />
      {busy && <div className="busy-bar" role="progressbar" aria-label="Updating" />}

      {tab === "rules" ? (
        <RulesPage meta={meta} />
      ) : (
        <main className="scan">
          {meta.warnings.length > 0 && (
            <div className="notices">
              {meta.warnings.map((w) => <p key={w}>{w}</p>)}
            </div>
          )}
          <section className="headline">
            <h1>{heading}</h1>
            <p className="source">
              {meta.index}, {meta.stocks} stocks, {meta.unit === "day" ? "daily" : meta.unit + "ly"} candles built from
              Yahoo Finance daily prices, downloaded {meta.fetchedAt}.
            </p>
          </section>
          <Summary result={result} meta={meta} />
          <div className="workspace">
            <CandidateList
              rows={rows}
              list={list}
              onList={setList}
              selectedId={selectedId}
              onSelect={setSelectedId}
              period={period}
              meta={meta}
            />
            <Detail row={selected} chart={chart} meta={meta} theme={theme} period={period} />
          </div>
        </main>
      )}
      <footer className="foot">
        Rule sheet v1. For research, not investment advice: check every chart yourself before trading.
      </footer>
    </div>
  );
}
