import React, { useEffect, useRef } from "react";
import { createChart, CrosshairMode, LineStyle } from "lightweight-charts";

const PALETTE = {
  light: { bg: "#ffffff", text: "#5e6e80", grid: "#eef2f5", border: "#d5dde3", up: "#12805a", down: "#c2413a",
           volUp: "rgba(18,128,90,.28)", volDown: "rgba(194,65,58,.28)", sma: "#8a99aa", burst: "#d9861c" },
  dark: { bg: "#15233a", text: "#93a3b5", grid: "#1c2c45", border: "#26364d", up: "#2db37e", down: "#e0645b",
          volUp: "rgba(45,179,126,.30)", volDown: "rgba(224,100,91,.30)", sma: "#6d7f95", burst: "#f0a940" },
};

// Candles, volume, the 65-day SMA, the base high over the base, the stop, and a marker on the breakout day.
export default function PriceChart({ chart, theme }) {
  const host = useRef(null);

  useEffect(() => {
    if (!host.current || !chart || !chart.candles.length) return undefined;
    const c = PALETTE[theme] || PALETTE.light;
    const api = createChart(host.current, {
      autoSize: true,
      layout: { background: { type: "solid", color: c.bg }, textColor: c.text,
                fontFamily: "'IBM Plex Sans Condensed', 'IBM Plex Sans', system-ui, sans-serif", fontSize: 11 },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      rightPriceScale: { borderColor: c.border, scaleMargins: { top: 0.06, bottom: 0.26 } },
      timeScale: { borderColor: c.border, rightOffset: 3, barSpacing: 6 },
      crosshair: { mode: CrosshairMode.Normal },
      // no labels below zero: the space under the candles holds the volume bars
      localization: { priceFormatter: (p) => (p < 0 ? "" : "₹" + p.toLocaleString("en-IN", { maximumFractionDigits: 2 })) },
    });
    const candles = api.addCandlestickSeries({
      upColor: c.up, downColor: c.down, wickUpColor: c.up, wickDownColor: c.down, borderVisible: false,
      priceLineVisible: false,
    });
    candles.setData(chart.candles.map((k) => ({ time: k.t, open: k.o, high: k.h, low: k.l, close: k.c })));

    const vol = api.addHistogramSeries({ priceScaleId: "vol", priceFormat: { type: "volume" },
                                         priceLineVisible: false, lastValueVisible: false });
    api.priceScale("vol").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    vol.setData(chart.candles.map((k) => ({ time: k.t, value: k.v || 0, color: k.c >= k.o ? c.volUp : c.volDown })));

    const quiet = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false };
    const sma = api.addLineSeries({ color: c.sma, lineWidth: 1, lineStyle: LineStyle.Dashed, ...quiet });
    sma.setData(chart.candles.filter((k) => k.sma != null).map((k) => ({ time: k.t, value: k.sma })));

    const times = chart.candles.map((k) => k.t);
    const at = times.indexOf(chart.date);
    if (chart.base && chart.base.high != null) {
      const base = api.addLineSeries({ color: c.burst, lineWidth: 2, ...quiet, title: "Base high" });
      base.setData(times.filter((t) => t >= chart.base.from && t <= chart.date)
        .map((t) => ({ time: t, value: chart.base.high })));
    }
    if (chart.stop != null && at >= 0) {
      const stop = api.addLineSeries({ color: c.down, lineWidth: 1, lineStyle: LineStyle.Dotted, ...quiet,
                                       title: "Stop" });
      stop.setData(times.slice(Math.max(0, at - 5)).map((t) => ({ time: t, value: chart.stop })));
    }
    if (at >= 0) {
      candles.setMarkers([{ time: chart.date, position: "belowBar", color: c.burst, shape: "arrowUp",
                            text: "Breakout" }]);
    }
    api.timeScale().fitContent();
    return () => api.remove();
  }, [chart, theme]);

  if (!chart) return <div className="chart loading">Loading the chart…</div>;
  return <div className="chart" ref={host} aria-label={`Daily price chart of ${chart.symbol}`} role="img" />;
}
