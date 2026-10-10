import { useEffect, useRef, useState } from "react";
import { money, shortDate } from "../api.js";

// Measure the container so labels stay a readable size on phones.
function useWidth(fallback = 640) {
  const ref = useRef(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    if (!ref.current || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) => setW(Math.max(280, Math.round(entry.contentRect.width))));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

// Simple, dependency-free SVG line chart for the balance forecast.
export default function LineChart({ series, threshold }) {
  const [ref, W] = useWidth();
  if (!series?.length) return null;
  const H = W < 500 ? 200 : 240;
  const pad = { l: 8, r: 8, t: 16, b: 26 };
  const values = series.map((p) => p.balance).concat(threshold ?? []);
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (max === min) {
    max += 1;
    min -= 1;
  }
  const span = max - min;
  min -= span * 0.08;
  max += span * 0.08;
  const x = (i) => pad.l + (i / (series.length - 1)) * (W - pad.l - pad.r);
  const y = (v) => pad.t + (1 - (v - min) / (max - min)) * (H - pad.t - pad.b);
  const path = series.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.balance).toFixed(1)}`).join(" ");
  const area = `${path} L${x(series.length - 1)},${H - pad.b} L${x(0)},${H - pad.b} Z`;
  const ticks = [0, 29, 59, 89].filter((i) => i < series.length);
  const lowIdx = series.reduce((best, p, i) => (p.balance < series[best].balance ? i : best), 0);

  return (
    <figure className="chart" ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Balance forecast from ${money(series[0].balance, { cents: false })} to ${money(series.at(-1).balance, { cents: false })}`}>
        {threshold != null && (
          <g>
            <rect x={pad.l} y={y(threshold)} width={W - pad.l - pad.r} height={Math.max(0, H - pad.b - y(threshold))} className="chart-danger" />
            <line x1={pad.l} x2={W - pad.r} y1={y(threshold)} y2={y(threshold)} className="chart-threshold" />
            <text x={pad.l + 4} y={y(threshold) + 16} textAnchor="start" className="chart-label">
              Your low-balance line {money(threshold, { cents: false })}
            </text>
          </g>
        )}
        <path d={area} className="chart-area" />
        <path d={path} className="chart-line" />
        <circle cx={x(lowIdx)} cy={y(series[lowIdx].balance)} r="4.5" className="chart-low" />
        {ticks.map((i) => (
          <text key={i} x={x(i)} y={H - 6} textAnchor={i === 0 ? "start" : i >= series.length - 1 ? "end" : "middle"} className="chart-axis">
            {shortDate(series[i].date)}
          </text>
        ))}
      </svg>
    </figure>
  );
}
