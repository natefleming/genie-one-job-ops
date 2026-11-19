import { createContext, FormEvent, Fragment, ReactNode, useContext, useEffect, useRef, useState } from "react";
import { api, Citation, GenieEvent, GenieResult, KnowledgePage, VizSpec } from "./api";
import { useBoxWidth } from "./StackedBars";

/** What the user is looking at — pages publish it, the panel sends it with every question. */
export interface PageContext { label: string; detail: string; starters: string[] }
const DEFAULT: PageContext = { label: "Job Ops", detail: "", starters: ["What is broken right now?"] };

const Ctx = createContext<{ page: PageContext; setPage: (p: PageContext) => void }>({ page: DEFAULT, setPage: () => {} });
export const usePageContext = (page: PageContext, deps: unknown[]) => {
  const { setPage } = useContext(Ctx);
  useEffect(() => setPage(page), deps); // eslint-disable-line react-hooks/exhaustive-deps
};
export function PageContextProvider({ children }: { children: ReactNode }) {
  const [page, setPage] = useState<PageContext>(DEFAULT);
  return <Ctx.Provider value={{ page, setPage }}>{children}</Ctx.Provider>;
}
export const useCurrentPage = () => useContext(Ctx).page;

/** The AI sparkle, same idea as the assistant toggle in the Databricks workspace. */
export function Sparkle({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M12 2.5l1.9 5.2a3 3 0 0 0 1.8 1.8l5.2 1.9-5.2 1.9a3 3 0 0 0-1.8 1.8L12 20.3l-1.9-5.2a3 3 0 0 0-1.8-1.8L3.1 11.4l5.2-1.9a3 3 0 0 0 1.8-1.8z" />
      <path fill="currentColor" d="M19 2l.7 1.8 1.8.7-1.8.7L19 7l-.7-1.8-1.8-.7 1.8-.7z" opacity=".7" />
    </svg>
  );
}

export function SparkleButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button className={`sparkle-btn${open ? " on" : ""}`} onClick={onToggle} aria-expanded={open}
      aria-label={open ? "Close Genie" : "Ask Genie about this page"} title="Ask Genie about this page">
      <Sparkle /> <span>Genie</span>
    </button>
  );
}

// --------------------------------------------------------------------------- turn state
type Step =
  | { kind: "thought"; text: string }
  | { kind: "skill"; name: string }
  | { kind: "knowledge"; count: number }
  | { kind: "query"; sql: string }
  | { kind: "memory" }
  | { kind: "step"; name: string };

interface Turn {
  question: string;
  startedAt: number;
  steps: Step[];
  skills: { name: string; description: string; url?: string }[];
  pages: KnowledgePage[];
  searchedKnowledge: boolean;
  answer?: string;
  citations: Citation[];
  table?: { columns: string[]; rows: (string | null)[][] } | null;
  vizzes: Record<string, { title: string; spec: VizSpec; statement_id: string }>;
  threadUrl?: string;
  suggestions: string[];
  notice?: string;
  error?: string;
  interrupted?: boolean;
  elapsed?: number;
  done: boolean;
  stopped?: boolean;
}

const newTurn = (question: string): Turn =>
  ({ question, startedAt: Date.now(), steps: [], skills: [], pages: [], searchedKnowledge: false, citations: [], vizzes: {}, suggestions: [], done: false });

function applyEvent(t: Turn, e: GenieEvent): Turn {
  switch (e.type) {
    case "thought": return { ...t, steps: [...t.steps, { kind: "thought", text: e.text }] };
    case "skill":
      return t.skills.some((s) => s.name === e.name) ? t
        : { ...t, skills: [...t.skills, { name: e.name, description: e.description, url: e.url }], steps: [...t.steps, { kind: "skill", name: e.name }] };
    case "knowledge": {
      const known = new Set(t.pages.map((p) => p.id));
      return { ...t, searchedKnowledge: true, pages: [...t.pages, ...e.pages.filter((p) => !known.has(p.id))],
               steps: [...t.steps, { kind: "knowledge", count: e.pages.length }] };
    }
    case "query": return { ...t, steps: [...t.steps, { kind: "query", sql: e.sql }] };
    case "memory": return { ...t, steps: [...t.steps, { kind: "memory" }] };
    case "step": return { ...t, steps: [...t.steps, { kind: "step", name: e.name }] };
    case "answer": return { ...t, answer: e.markdown, citations: e.citations, table: e.table, suggestions: e.suggested_actions ?? [] };
    case "viz": return { ...t, vizzes: { ...t.vizzes, [e.id]: { title: e.title, spec: e.spec, statement_id: e.statement_id } } };
    case "start": return e.thread_url ? { ...t, threadUrl: e.thread_url } : t;
    case "notice": return { ...t, notice: e.text };
    case "error": return { ...t, error: e.message };
    case "done": return { ...t, done: true, elapsed: e.elapsed_s };
    default: return t;
  }
}

/** Plain-English labels for Genie One tools we've seen; anything new falls back to "Used <tool name>". */
const TOOL_LABELS: Record<string, string> = {
  ask_genie_space: "Asked the Job Ops agent",
  get_asset_info: "Looked up an asset in Unity Catalog",
  search_assets: "Searched the catalog for relevant assets",
  search_knowledge_snippets: "Searched the ontology",
  execute_sql_query: "Ran a query",
  episode_fetch: "Checked a past conversation",
  web_search: "Searched the web",
  create_viz: "Built a chart",
};

const stepLabel = (s: Step): ReactNode => {
  switch (s.kind) {
    case "skill": return <>Loaded skill <b>{s.name}</b></>;
    case "knowledge": return s.count ? <>Found {s.count} ontology snippet{s.count === 1 ? "" : "s"}</> : <>Searched the ontology — no matching pages</>;
    case "query": return <>Ran a query</>;
    case "memory": return <>Checked a past conversation</>;
    case "step": return TOOL_LABELS[s.name] ?? <>Used {s.name.replace(/_/g, " ")}</>;
    case "thought": return s.text;
  }
};

const liveLabel = (t: Turn): string => {
  const last = [...t.steps].reverse().find((s) => s.kind !== "thought");
  if (t.answer) return "Finishing up";
  if (!t.steps.length) return "Starting";
  const lastAny = t.steps[t.steps.length - 1];
  if (lastAny.kind === "thought" && /final|compile|deliver|put together|summar/i.test(lastAny.text)) return "Writing the answer";
  if (!last) return "Thinking";
  return { skill: "Loading skills", knowledge: "Checking the ontology", query: "Running queries", memory: "Checking past conversations", step: "Working", thought: "Thinking" }[last.kind];
};

// --------------------------------------------------------------------------- markdown (what Genie One writes)
function Prose({ text, citations, vizzes = {} }: { text: string; citations: Citation[]; vizzes?: Turn["vizzes"] }) {
  const byUrl = new Map(citations.map((c) => [c.url, c]));
  const inline = (s: string): ReactNode[] =>
    s.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g).map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return <b key={i}>{inline(part.slice(2, -2))}</b>;
      if (part.startsWith("`") && part.endsWith("`") && part.length > 2) return <code key={i}>{part.slice(1, -1)}</code>;
      const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (link) {
        const c = byUrl.get(link[2]);
        return c
          ? <a key={i} className="cite" href={c.link || c.url} target="_blank" rel="noreferrer" title={c.title}>{c.index}</a>
          : <a key={i} href={link[2]} target="_blank" rel="noreferrer">{inline(link[1])}</a>;
      }
      return <Fragment key={i}>{part.replace(/\\([\\`*_{}\[\]()#+\-.!~|>])/g, "$1")}</Fragment>;
    });

  const renderBlocks = (text: string): ReactNode[] => {
    const blocks: ReactNode[] = [];
    const lines = text.split("\n");
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (!line.trim()) continue;
      const h = line.match(/^(#{1,4})\s+(.*)$/);
      if (h) { blocks.push(h[1].length <= 2 ? <h4 key={i}>{inline(h[2])}</h4> : <h5 key={i}>{inline(h[2])}</h5>); continue; }
      if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) { blocks.push(<hr key={i} />); continue; }
      if (line.trim().startsWith("|")) {
        const rows: string[][] = [];
        while (i < lines.length && lines[i].trim().startsWith("|")) {
          const cells = lines[i].trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
          if (!cells.every((c) => /^:?-{2,}:?$/.test(c))) rows.push(cells);
          i++;
        }
        i--;
        const [head, ...body] = rows;
        blocks.push(
          <div className="result" key={i}><table>
            <thead><tr>{head.map((c, k) => <th key={k}>{inline(c)}</th>)}</tr></thead>
            <tbody>{body.map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{inline(c)}</td>)}</tr>)}</tbody>
          </table></div>);
        continue;
      }
      if (/^\s*([-*•]|\d+\.)\s+/.test(line)) {
        const ordered = /^\s*\d+\./.test(line);
        const items: string[] = [];
        while (i < lines.length && /^\s*([-*•]|\d+\.)\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*([-*•]|\d+\.)\s+/, "")); i++; }
        i--;
        const List = ordered ? "ol" : "ul";
        blocks.push(<List key={i}>{items.map((it, k) => <li key={k}>{inline(it)}</li>)}</List>);
        continue;
      }
      const para: string[] = [line];
      while (i + 1 < lines.length && lines[i + 1].trim() && !/^(#{1,4}\s|\||\s*([-*•]|\d+\.)\s|\s*-{3,}\s*$)/.test(lines[i + 1])) para.push(lines[++i]);
      blocks.push(<p key={i}>{para.map((l, k) => <Fragment key={k}>{k > 0 && <br />}{inline(l)}</Fragment>)}</p>);
    }
  return blocks;
  };

  // Genie One wraps embedded query results in <!-- begin-embedded:query_ID --> … <!-- end-embedded:query_ID -->.
  // Render each as a result card linked to its citation; drop any other HTML comments.
  const parts: ReactNode[] = [];
  const re = /<!--\s*begin-embedded:(\S+?)\s*-->([\s\S]*?)<!--\s*end-embedded:\1\s*-->/g;
  let last = 0;
  let m: RegExpExecArray | null;
  const clean = (t: string) => t.replace(/<!--[\s\S]*?-->/g, "");
  while ((m = re.exec(text))) {
    parts.push(...renderBlocks(clean(text.slice(last, m.index))));
    const id = m[1];
    const cite = citations.find((c) => c.url.includes(`embed-${id}`));
    if (vizzes[id]) { parts.push(<GenieChart key={`viz-${m.index}`} viz={vizzes[id]} />); last = m.index + m[0].length; continue; }
    parts.push(
      <div className="embed" key={`embed-${m.index}`}>
        <div className="embed-head">
          <span>Query result</span>
          {cite && <a href={cite.url} target="_blank" rel="noreferrer">open in Genie One ↗</a>}
        </div>
        {clean(m[2]).trim() ? renderBlocks(clean(m[2])) : <p className="muted">The result is shown in Genie One.</p>}
      </div>);
    last = m.index + m[0].length;
  }
  parts.push(...renderBlocks(clean(text.slice(last))));
  return <>{parts}</>;
}

// --------------------------------------------------------------------------- charts Genie One builds
/** Draws a Genie One chart (bar / line / area, one series) from its spec and the rows of the statement behind it.
 *  Anything else renders as a table, with a link to the full chart in Genie One. */
function GenieChart({ viz }: { viz: { title: string; spec: VizSpec; statement_id: string } }) {
  const [data, setData] = useState<GenieResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);
  const [box, W] = useBoxWidth(560);
  useEffect(() => {
    if (!viz.statement_id) { setError("No data attached to this chart."); return; }
    api.genieResult(viz.statement_id).then(setData).catch((e: Error) => setError(e.message));
  }, [viz.statement_id]);

  const enc = viz.spec.encodings ?? {};
  const xf = enc.x?.fieldName, yf = enc.y?.fieldName;
  const kind = viz.spec.widgetType ?? "";
  const drawable = ["bar", "line", "area"].includes(kind) && xf && yf && !enc.color?.fieldName;

  let body: ReactNode = <div className="skeleton" style={{ height: 160 }} />;
  if (error) body = <p className="muted">{error}</p>;
  else if (data) {
    const xi = data.columns.indexOf(xf ?? ""), yi = data.columns.indexOf(yf ?? "");
    if (!drawable || xi < 0 || yi < 0 || asTable) {
      body = (
        <div className="result"><table>
          <thead><tr>{data.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{data.rows.slice(0, 20).map((r, j) => <tr key={j}>{r.map((v, k) => <td key={k}>{String(v ?? "")}</td>)}</tr>)}</tbody>
        </table></div>);
    } else {
      const pts = data.rows.map((r) => ({ x: String(r[xi] ?? ""), y: Number(r[yi] ?? 0) }));
      const H = 190, padL = 34, padB = 24, top = 10;
      const max = Math.max(1, ...pts.map((p) => p.y));
      const slot = (W - padL) / Math.max(1, pts.length);
      const bw = Math.min(28, slot * 0.66);
      const y = (v: number) => top + (H - padB - top) * (1 - v / max);
      const cx = (i: number) => padL + i * slot + slot / 2;
      const ticks = [0, Math.round(max / 2), max];
      const fmtX = (v: string) => (/^\d{4}-\d{2}-\d{2}/.test(v) ? new Date(v.slice(0, 10) + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }) : v);
      const every = Math.ceil(pts.length / Math.max(2, Math.floor((W - padL) / 56)));
      body = (
        <div className="chart" ref={box} onMouseLeave={() => setHover(null)}>
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={viz.title}>
            {ticks.map((t) => (
              <g key={t}>
                <line x1={padL} x2={W} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
                <text x={padL - 6} y={y(t) + 4} textAnchor="end" fontSize={10} fill="var(--text-muted)">{t}</text>
              </g>
            ))}
            {kind === "bar" ? pts.map((p, i) => {
              const h = Math.max(1, y(0) - y(p.y));
              return (
                <g key={i} onMouseEnter={() => setHover(i)}>
                  <rect x={padL + i * slot} y={top} width={slot} height={H - padB - top} fill="transparent" />
                  <path fill="var(--series-1)" opacity={hover === null || hover === i ? 1 : 0.45}
                    d={`M${cx(i) - bw / 2},${y(0)} v${-(Math.max(h, 4) - 4)} q0,-4 4,-4 h${bw - 8} q4,0 4,4 v${Math.max(h, 4) - 4} z`} />
                </g>);
            }) : (
              <>
                {kind === "area" && <path fill="var(--series-1)" opacity={0.15}
                  d={`M${cx(0)},${y(0)} ${pts.map((p, i) => `L${cx(i)},${y(p.y)}`).join(" ")} L${cx(pts.length - 1)},${y(0)} Z`} />}
                <path fill="none" stroke="var(--series-1)" strokeWidth={2} d={pts.map((p, i) => `${i ? "L" : "M"}${cx(i)},${y(p.y)}`).join(" ")} />
                {pts.map((p, i) => (
                  <g key={i} onMouseEnter={() => setHover(i)}>
                    <rect x={padL + i * slot} y={top} width={slot} height={H - padB - top} fill="transparent" />
                    <circle cx={cx(i)} cy={y(p.y)} r={hover === i ? 5 : 3} fill="var(--series-1)" stroke="var(--surface-1)" strokeWidth={2} />
                  </g>))}
              </>
            )}
            {pts.map((p, i) => ((i % every === 0 && pts.length - 1 - i >= every) || i === pts.length - 1) && (
              <text key={i} x={cx(i)} y={H - 7} textAnchor="middle" fontSize={10} fill="var(--text-muted)">{fmtX(p.x)}</text>))}
          </svg>
          {hover !== null && (
            <div className="tooltip" style={{ left: `${Math.min(70, (cx(hover) / W) * 100)}%`, top: 0 }}>
              <div className="t">{fmtX(pts[hover].x)}</div>
              <div className="row spread" style={{ gap: 12 }}><span className="muted">{enc.y?.axis?.title ?? yf}</span><b className="num">{pts[hover].y.toLocaleString()}</b></div>
            </div>
          )}
        </div>);
    }
  }
  return (
    <div className="embed">
      <div className="embed-head">
        <span>{viz.title || "Chart"}</span>
        {drawable && data && <button className="ghost mini" onClick={() => setAsTable((v) => !v)}>{asTable ? "Chart" : "Table"}</button>}
      </div>
      {body}
    </div>
  );
}

// --------------------------------------------------------------------------- pieces of a turn
function Elapsed({ since, stopped }: { since: number; stopped?: number }) {
  const [, tick] = useState(0);
  useEffect(() => { if (stopped !== undefined) return; const id = setInterval(() => tick((n) => n + 1), 1000); return () => clearInterval(id); }, [stopped]);
  const s = stopped ?? Math.round((Date.now() - since) / 1000);
  return <span className="num">{s}s</span>;
}

function Activity({ turn }: { turn: Turn }) {
  const working = !turn.done;
  const [open, setOpen] = useState(true);
  useEffect(() => { if (turn.done && turn.answer) setOpen(false); }, [turn.done, turn.answer]);
  const toolSteps = turn.steps.filter((s) => s.kind !== "thought").length;
  return (
    <div className={`activity${working ? " live" : ""}`}>
      <button className="activity-head" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className={`sparkle-ink${working ? " spin" : ""}`}><Sparkle size={14} /></span>
        <span aria-live="polite">{working ? `${liveLabel(turn)}…` : turn.stopped ? "Stopped" : `${toolSteps} step${toolSteps === 1 ? "" : "s"}`}</span>
        <span className="muted">· <Elapsed since={turn.startedAt} stopped={turn.done ? Math.round(turn.elapsed ?? (Date.now() - turn.startedAt) / 1000) : undefined} /></span>
        <span className="chev" aria-hidden="true">{open ? "▾" : "▸"}</span>
      </button>
      {open && turn.steps.length > 0 && (
        <ol className="steps-list">
          {turn.steps.map((s, i) => (
            <li key={i} className={s.kind === "thought" ? "thought" : "tool"}>
              {s.kind === "query"
                ? <details><summary>{stepLabel(s)}</summary><pre className="err">{s.sql}</pre></details>
                : stepLabel(s)}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

const SOURCE_GROUPS: [string, string][] = [
  ["ONE_CHAT_SQL_QUERY", "Queries"], ["USER_SKILL", "Skills"], ["EPISODE", "Past conversations"],
];

function Metadata({ turn }: { turn: Turn }) {
  const skillUrl = new Map(turn.citations.filter((c) => c.asset_type === "USER_SKILL").map((c) => [c.title, c.link || c.url]));
  const skills = [...turn.skills];
  turn.citations.filter((c) => c.asset_type === "USER_SKILL" && !skills.some((s) => s.name === c.title))
    .forEach((c) => skills.push({ name: c.title, description: "" }));
  const groups = SOURCE_GROUPS.map(([type, label]) => [label, turn.citations.filter((c) => c.asset_type === type)] as const);
  const other = turn.citations.filter((c) => !SOURCE_GROUPS.some(([t]) => t === c.asset_type));
  return (
    <div className="meta">
      {skills.length > 0 && (
        <section>
          <h6>Skills used</h6>
          <div className="meta-chips">
            {skills.map((s) => {
              const url = s.url || skillUrl.get(s.name);
              const chip = <><Sparkle size={12} />{s.name}</>;
              return url
                ? <a key={s.name} className="meta-chip" href={url} target="_blank" rel="noreferrer" title={s.description}>{chip}</a>
                : <span key={s.name} className="meta-chip" title={s.description}>{chip}</span>;
            })}
          </div>
        </section>
      )}
      {turn.searchedKnowledge && (
        <details className="meta-sec">
          <summary><h6>Ontology snippets</h6><span className="muted">{turn.pages.length ? `${turn.pages.length} page${turn.pages.length === 1 ? "" : "s"}` : "none matched"}</span></summary>
          {turn.pages.length > 0 ? (
            <ul className="pages">
              {[...turn.pages].sort((a, b) => b.relevance_score - a.relevance_score).map((p) => (
                <li key={p.id}>
                  <div className="row" style={{ gap: 8 }}>
                    {p.url ? <a className="page-link" href={p.url} target="_blank" rel="noreferrer"><b>{p.name}</b></a> : <b>{p.name}</b>}
                    {p.certified && <span className="status ok">Certified</span>}
                    <span className="muted num">{Math.round(p.relevance_score * 100)}% match</span>
                  </div>
                  <div className="muted">{p.domain}</div>
                  {p.description && <div>{p.description}</div>}
                  {p.synonyms?.length ? <div className="muted">Also: {p.synonyms.join(", ")}</div> : null}
                </li>
              ))}
            </ul>
          ) : <p className="muted">Genie searched the ontology but no page matched this question.</p>}
        </details>
      )}
      {turn.citations.length > 0 && (
        <details className="meta-sec">
          <summary><h6>Sources</h6><span className="muted">{turn.citations.length}</span></summary>
          {[...groups, ["Other", other] as const].filter(([, cs]) => cs.length).map(([label, cs]) => (
            <div key={label} className="src-group">
              <div className="muted">{label}</div>
              <ul>{cs.map((c, k) => (
                <li key={c.index}><span className="cite">{c.index}</span>
                  <a href={c.link || c.url} target="_blank" rel="noreferrer">{c.asset_type === "ONE_CHAT_SQL_QUERY" ? `Query ${k + 1}` : c.title}</a>
                  {c.asset_type === "ONE_CHAT_SQL_QUERY" && <span className="muted">· result in Genie One</span>}</li>
              ))}</ul>
            </div>
          ))}
        </details>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- resizing
const WIDTH_KEY = "jobops.genie.width";
const DEFAULT_WIDTH = 420;
const MIN_WIDTH = 340;
const maxWidth = () => Math.max(MIN_WIDTH, Math.round(window.innerWidth * 0.75));
const clampWidth = (w: number) => Math.min(maxWidth(), Math.max(MIN_WIDTH, Math.round(w)));

/** Width of the panel, shared with the page through the --genie-w CSS variable (the page reflows to make room). */
function usePanelWidth(): [number, (w: number) => void] {
  const [width, setWidth] = useState(() => clampWidth(Number(localStorage.getItem(WIDTH_KEY)) || DEFAULT_WIDTH));
  useEffect(() => {
    document.documentElement.style.setProperty("--genie-w", `${width}px`);
    localStorage.setItem(WIDTH_KEY, String(width));
  }, [width]);
  useEffect(() => {
    const onResize = () => setWidth((w) => clampWidth(w));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return [width, (w: number) => setWidth(clampWidth(w))];
}

/** Drag the panel's left edge to resize; arrow keys nudge it; double-click resets. */
function ResizeHandle({ width, onResize }: { width: number; onResize: (w: number) => void }) {
  const [dragging, setDragging] = useState(false);
  const active = useRef(false); // a ref, so moves arriving before the next render still resize
  const start = (e: React.PointerEvent) => {
    e.preventDefault();
    try { (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); } catch { /* synthetic or lost pointer */ }
    active.current = true;
    setDragging(true);
    document.body.classList.add("resizing");
  };
  const move = (e: React.PointerEvent) => { if (active.current) onResize(window.innerWidth - e.clientX); };
  const end = () => { active.current = false; setDragging(false); document.body.classList.remove("resizing"); };
  return (
    <div className={`panel-resize${dragging ? " dragging" : ""}`} role="separator" aria-orientation="vertical"
      aria-label="Resize Genie panel" aria-valuenow={width} aria-valuemin={MIN_WIDTH} aria-valuemax={maxWidth()} tabIndex={0}
      title="Drag to resize · double-click to reset"
      onPointerDown={start} onPointerMove={move} onPointerUp={end} onPointerCancel={end}
      onDoubleClick={() => onResize(DEFAULT_WIDTH)}
      onKeyDown={(e) => {
        if (e.key === "ArrowLeft") { e.preventDefault(); onResize(width + (e.shiftKey ? 80 : 20)); }
        if (e.key === "ArrowRight") { e.preventDefault(); onResize(width - (e.shiftKey ? 80 : 20)); }
      }} />
  );
}

// --------------------------------------------------------------------------- panel
export function GeniePanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const page = useCurrentPage();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversation, setConversation] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const abort = useRef<AbortController | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const busy = turns.length > 0 && !turns[turns.length - 1].done;
  const [width, setWidth] = usePanelWidth();

  useEffect(() => { scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" }); }, [turns]);

  const update = (index: number, fn: (t: Turn) => Turn) => setTurns((ts) => ts.map((t, i) => (i === index ? fn(t) : t)));

  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    setDraft("");
    const index = turns.length;
    setTurns((ts) => [...ts, newTurn(question)]);
    const ctrl = new AbortController();
    abort.current = ctrl;
    const context = `The user is on the "${page.label}" page of the Job Ops app. ${page.detail}`.trim();
    try {
      await api.streamGenie(question, context, conversation, (e) => {
        if (e.type === "start" && e.engine !== "agent") setConversation(e.conversation_id);
        update(index, (t) => applyEvent(t, e));
      }, ctrl.signal);
    } catch {
      // The stream dropped (network blip, or the app restarted during a deploy) before Genie finished.
      if (!ctrl.signal.aborted) update(index, (t) => (t.answer ? t : { ...t, interrupted: true }));
    } finally {
      update(index, (t) => (t.done ? t : { ...t, done: true, stopped: ctrl.signal.aborted, elapsed: Math.round((Date.now() - t.startedAt) / 1000) }));
      abort.current = null;
    }
  };

  const submit = (e: FormEvent) => { e.preventDefault(); void ask(draft); };

  return (
    <aside className={`genie-panel${open ? " open" : ""}`} aria-hidden={!open}>
      <ResizeHandle width={width} onResize={setWidth} />
      <header>
        <div className="row" style={{ gap: 8 }}><span className="sparkle-ink"><Sparkle /></span><b>Genie One</b><span className="muted">· Job Ops</span></div>
        <div className="row" style={{ gap: 4 }}>
          <button className="ghost" onClick={() => { setTurns([]); setConversation(null); }} disabled={busy} title="New conversation">New</button>
          <button className="ghost" onClick={onClose} aria-label="Close">✕</button>
        </div>
      </header>
      {/* page.detail is instructions for Genie (sent with every question), not text for the user */}
      <div className="context-chip">About: <b>{page.label}</b></div>

      <div className="turns" ref={scroller}>
        {turns.length === 0 && (
          <div className="starters">
            <p className="muted">Ask about what you're looking at. Genie One answers as you, from the governed Job Ops data, and shows the skills, ontology and sources it used.</p>
            {page.starters.map((s) => <button key={s} className="starter" onClick={() => void ask(s)}>{s}</button>)}
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className="turn">
            <div className="q">{t.question}</div>
            {t.notice && <div className="notice">{t.notice}</div>}
            <Activity turn={t} />
            {t.error && <div className="a err-text">{t.error}</div>}
            {t.interrupted && (
              <div className="a interrupted">
                <span>The connection to Genie was interrupted before it finished — the app may have restarted.</span>
                <button className="starter" onClick={() => void ask(t.question)} disabled={busy}>↻ Ask again</button>
              </div>
            )}
            {t.stopped && !t.answer && <div className="a muted">Stopped before Genie finished.</div>}
            {t.answer !== undefined && (
              <div className="a">
                <Prose text={t.answer} citations={t.citations} vizzes={t.vizzes} />
                {t.table && t.table.columns.length > 0 && (
                  <div className="result"><table>
                    <thead><tr>{t.table.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                    <tbody>{t.table.rows.slice(0, 12).map((r, j) => <tr key={j}>{r.map((v, k) => <td key={k}>{String(v ?? "")}</td>)}</tr>)}</tbody>
                  </table></div>
                )}
                <Metadata turn={t} />
                {t.threadUrl && (
                  <div className="answer-links">
                    <a href={t.threadUrl} target="_blank" rel="noreferrer">Open this conversation in Genie One ↗</a>
                    {t.suggestions.includes("SUGGESTED_ACTION_TYPE_CREATE_SCHEDULED_TASK") &&
                      <a href={t.threadUrl} target="_blank" rel="noreferrer" title="Genie One can run this on a schedule and send you the result">Schedule this in Genie One ↗</a>}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <form className="composer" onSubmit={submit}>
        <textarea value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={busy ? "Genie is working…" : "Ask Genie about this page…"} rows={2}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void ask(draft); } }} disabled={!open} />
        {busy
          ? <button type="button" className="stop" onClick={() => abort.current?.abort()} aria-label="Stop">■</button>
          : <button className="primary" type="submit" disabled={!draft.trim()} aria-label="Send">↑</button>}
      </form>
    </aside>
  );
}
