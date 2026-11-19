import { useCallback, useMemo, useRef, useState } from "react";
import { asNum, Row } from "./api";
import { CATEGORIES, slot } from "./categories";

/** Width of the element `ref` is attached to, so charts draw in real pixels and text stays legible however narrow the
 *  container gets (e.g. with the Genie panel open). A callback ref, so it also works for elements mounted later. */
export function useBoxWidth(initial: number): [(el: HTMLElement | null) => void, number] {
  const [w, setW] = useState(initial);
  const ro = useRef<ResizeObserver | null>(null);
  const ref = useCallback((el: HTMLElement | null) => {
    ro.current?.disconnect();
    if (!el) return;
    ro.current = new ResizeObserver(([e]) => setW(Math.max(240, Math.round(e.contentRect.width))));
    ro.current.observe(el);
  }, []);
  return [ref, w];
}

/** Failed runs per day, stacked by failure category. Hover a day for the breakdown; the table view is one click away. */
export function StackedBars({ rows, days }: { rows: Row[]; days: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);
  const [box, W] = useBoxWidth(720);

  const { dates, byDate, present, max } = useMemo(() => {
    const dates: string[] = [];
    for (let i = days; i >= 0; i--) dates.push(new Date(Date.now() - i * 864e5).toISOString().slice(0, 10));
    const byDate: Record<string, Record<string, number>> = Object.fromEntries(dates.map((d) => [d, {}]));
    for (const r of rows) {
      const d = String(r.run_date).slice(0, 10);
      const cat = CATEGORIES.includes(String(r.failure_category) as never) ? String(r.failure_category) : "Other";
      if (byDate[d]) byDate[d][cat] = (byDate[d][cat] ?? 0) + asNum(r.failed_runs);
    }
    const present = CATEGORIES.filter((c) => dates.some((d) => byDate[d][c]));
    const max = Math.max(1, ...dates.map((d) => Object.values(byDate[d]).reduce((a, b) => a + b, 0)));
    return { dates, byDate, present, max };
  }, [rows, days]);

  const H = 220, padL = 34, padB = 26, plotH = H - padB - 8;
  const slotW = (W - padL) / dates.length;
  const barW = Math.min(34, slotW * 0.62);
  const every = Math.ceil(dates.length / Math.max(2, Math.floor((W - padL) / 56)));
  const ticks = [0, Math.ceil(max / 2), max];
  const y = (v: number) => 8 + plotH - (v / max) * plotH;
  const label = (d: string) => new Date(d + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });

  return (
    <div>
      <div className="row spread" style={{ marginBottom: 8 }}>
        <div className="legend" style={{ marginTop: 0 }}>
          {present.map((c) => (
            <span key={c} className="chip"><span className="dot" style={{ background: `var(--series-${slot(c)})` }} />{c}</span>
          ))}
        </div>
        <div className="seg">
          <button className={!asTable ? "on" : ""} onClick={() => setAsTable(false)}>Chart</button>
          <button className={asTable ? "on" : ""} onClick={() => setAsTable(true)}>Table</button>
        </div>
      </div>
      {asTable ? (
        <table>
          <thead><tr><th>Day</th>{present.map((c) => <th key={c}>{c}</th>)}<th>Total</th></tr></thead>
          <tbody>
            {dates.map((d) => (
              <tr key={d}>
                <td>{label(d)}</td>
                {present.map((c) => <td key={c}>{byDate[d][c] ?? 0}</td>)}
                <td><b>{Object.values(byDate[d]).reduce((a, b) => a + b, 0)}</b></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="chart" ref={box} onMouseLeave={() => setHover(null)}>
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Failed runs per day by failure category">
            {ticks.map((t) => (
              <g key={t}>
                <line x1={padL} x2={W} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth={1} />
                <text x={padL - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--text-muted)">{t}</text>
              </g>
            ))}
            {dates.map((d, i) => {
              const x = padL + i * slotW + (slotW - barW) / 2;
              let acc = 0;
              const segs = present.filter((c) => byDate[d][c]);
              return (
                <g key={d} onMouseEnter={() => setHover(i)}>
                  <rect x={padL + i * slotW} y={0} width={slotW} height={H - padB} fill="transparent" />
                  {segs.map((c, k) => {
                    const v = byDate[d][c];
                    const top = y(acc + v), bottom = y(acc);
                    acc += v;
                    const h = Math.max(1, bottom - top - (k > 0 ? 2 : 0)); // 2px surface gap between segments
                    const isTop = k === segs.length - 1;
                    return (
                      <path key={c} fill={`var(--series-${slot(c)})`} opacity={hover === null || hover === i ? 1 : 0.45}
                        d={isTop
                          ? `M${x},${top + h} v${-(h - 4)} q0,-4 4,-4 h${barW - 8} q4,0 4,4 v${h - 4} z`
                          : `M${x},${top} h${barW} v${h} h${-barW} z`} />
                    );
                  })}
                  {((i % every === 0 && dates.length - 1 - i >= every) || i === dates.length - 1) && (
                    <text x={x + barW / 2} y={H - 8} textAnchor="middle" fontSize={11} fill="var(--text-muted)">{label(d)}</text>
                  )}
                </g>
              );
            })}
          </svg>
          {hover !== null && (
            <div className="tooltip" style={{ left: `${Math.min(78, ((padL + hover * slotW) / W) * 100)}%`, top: 4 }}>
              <div className="t">{label(dates[hover])}</div>
              {present.filter((c) => byDate[dates[hover]][c]).map((c) => (
                <div key={c} className="row spread" style={{ gap: 14 }}>
                  <span className="chip"><span className="dot" style={{ background: `var(--series-${slot(c)})` }} />{c}</span>
                  <b>{byDate[dates[hover]][c]}</b>
                </div>
              ))}
              {!Object.keys(byDate[dates[hover]]).length && <div className="muted">No failures</div>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
