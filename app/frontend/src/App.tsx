import { Fragment, ReactNode, useEffect, useState } from "react";
import { ago, api, AppConfig, asNum, fmtTime, Row, RunDetail, Summary } from "./api";
import { CATEGORY_HELP, slot } from "./categories";
import { GeniePanel, PageContextProvider, SparkleButton, usePageContext } from "./GeniePanel";
import { StackedBars } from "./StackedBars";

// --------------------------------------------------------------------------- tiny helpers
function useHash(): string {
  const [hash, setHash] = useState(window.location.hash || "#/");
  useEffect(() => {
    const on = () => setHash(window.location.hash || "#/");
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}

function useLoad<T>(load: () => Promise<T>, deps: unknown[]): { data: T | null; error: string | null; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    setData(null); setError(null);
    load().then((d) => live && setData(d)).catch((e: Error) => live && setError(e.message));
    return () => { live = false; };
  }, [...deps, n]); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, error, reload: () => setN((x) => x + 1) };
}

const Category = ({ name }: { name: string }) => (
  <span className="chip" title={CATEGORY_HELP[name]}><span className="dot" style={{ background: `var(--series-${slot(name)})` }} />{name}</span>
);

const State = ({ v }: { v: Row[string] }) => {
  const s = String(v ?? "RUNNING");
  const cls = s === "SUCCEEDED" ? "ok" : ["FAILED", "ERROR", "TIMED_OUT"].includes(s) ? "bad" : "warn";
  const text = s === "SUCCEEDED" ? "✓ Succeeded" : cls === "bad" ? "✕ Failed" : s.charAt(0) + s.slice(1).toLowerCase().replace(/_/g, " ");
  return <span className={`status ${cls}`}>{text}</span>;
};

function Loading({ error, children }: { error: string | null; children?: ReactNode }) {
  if (error) return <div className="note">Couldn't load this: {error}</div>;
  return <>{children ?? <div className="skeleton" />}</>;
}

const go = (path: string) => { window.location.hash = path; };

/** Opens a job/pipeline in Databricks (new tab) without triggering the row's own click. No url = plain text. */
const ExtLink = ({ href, children }: { href: Row[string] | undefined; children: ReactNode }) =>
  href ? <a href={String(href)} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>{children} ↗</a> : <>{children}</>;

/** Hover / keyboard-focus tooltip. `plain` skips the dotted underline (for values rather than labels). */
function Hint({ tip, children, plain }: { tip: string; children: ReactNode; plain?: boolean }) {
  return (
    <span className={`hint${plain ? " plain" : ""}`} tabIndex={0} aria-label={typeof children === "string" ? `${children}: ${tip}` : tip}>
      {children}
      <span className="hint-tip" role="tooltip">{tip}</span>
    </span>
  );
}

// Time buckets for list filters, in hours since a row's timestamp. The "Over …" bucket isolates the long-running
// ones (jobs failing for weeks, tables quiet for days) so they can be looked at, or filtered out, separately.
interface Bucket { label: string; minH?: number; maxH?: number }
const SINCE: Bucket[] = [
  { label: "Any time" }, { label: "Last hour", maxH: 1 }, { label: "24 hours", maxH: 24 },
  { label: "7 days", maxH: 168 }, { label: "30 days", maxH: 720 }, { label: "Over 30 days", minH: 720 },
];
const NO_OWNER = "(no owner)";
const hoursSince = (v: Row[string]) => (v ? (Date.now() - new Date(String(v)).getTime()) / 36e5 : Infinity);

interface ListFilter {
  shown: Row[]; total: number; active: boolean; label: string; buckets: Bucket[]; since: number; owner: string;
  owners: string[] | null; setSince: (i: number) => void; setOwner: (o: string) => void; clear: () => void;
  /** For Genie's page context: what the filter is doing, or "" when it's off. */
  describe: string;
}

/** Filter a list by a time bucket on `at`, and by owner when `ownerOf` is given. */
function useListFilter(rows: Row[] | null, label: string, at: (r: Row) => Row[string],
                       ownerOf?: (r: Row) => Row[string], buckets: Bucket[] = SINCE): ListFilter {
  const [since, setSince] = useState(0);
  const [owner, setOwner] = useState("");
  const ownerName = (r: Row) => String(ownerOf?.(r) ?? NO_OWNER);
  const all = rows ?? [];
  const bucket = buckets[since];
  const shown = all.filter((r) => {
    const h = hoursSince(at(r));
    return (bucket.maxH === undefined || h <= bucket.maxH) && (bucket.minH === undefined || h > bucket.minH)
      && (!owner || ownerName(r) === owner);
  });
  const active = since > 0 || owner !== "";
  const describe = active
    ? `filtered to ${shown.length} of ${all.length}${since > 0 ? ` (${label.toLowerCase()}: ${bucket.label.toLowerCase()})` : ""}${owner ? ` owned by ${owner}` : ""}`
    : "";
  return {
    shown, total: all.length, active, label, buckets, since, owner, describe, setSince, setOwner,
    owners: ownerOf ? [...new Set(all.map(ownerName))].sort() : null,
    clear: () => { setSince(0); setOwner(""); },
  };
}

function FilterControls({ f }: { f: ListFilter }) {
  return (
    <div className="row filters">
      <span className="muted">{f.label}</span>
      <div className="seg">
        {f.buckets.map((b, i) => <button key={b.label} className={i === f.since ? "on" : ""} onClick={() => f.setSince(i)}>{b.label}</button>)}
      </div>
      {f.owners && (
        <select value={f.owner} onChange={(e) => f.setOwner(e.target.value)} aria-label="Owner">
          <option value="">All owners</option>
          {f.owners.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      )}
    </div>
  );
}

type Health = "failing" | "healthy";

interface SwitchOption<T extends string> { value: T; label: string; tone?: "ok" | "bad" }

/** Segmented status switch: the selected option turns green ("ok") or red ("bad"), or stays neutral without a tone. */
function StatusSwitch<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: SwitchOption<T>[]; label: string }) {
  return (
    <div className="seg health" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} role="radio" aria-checked={value === o.value} className={value === o.value ? `on${o.tone ? ` ${o.tone}` : ""}` : ""}
          onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

const count = (x?: number) => (x === undefined ? "" : ` ${x}`);

/** Failing / healthy switch. Counts appear once loaded. */
function HealthSwitch({ value, onChange, failing, healthy }: { value: Health; onChange: (v: Health) => void; failing?: number; healthy?: number }) {
  return <StatusSwitch label="Show failing or healthy" value={value} onChange={onChange} options={[
    { value: "failing", label: `✕ Failing${count(failing)}`, tone: "bad" },
    { value: "healthy", label: `✓ Healthy${count(healthy)}`, tone: "ok" },
  ]} />;
}

/** "Showing N of M" line, only while a filter is on. `limit` = how many rows the table actually shows. */
function FilterCount({ f, noun, limit }: { f: ListFilter; noun: string; limit?: number }) {
  if (!f.active) return null;
  const n = f.shown.length;
  return (
    <div className="sub">
      {limit !== undefined && n > limit ? `Showing ${limit} of ${n} matching` : `${n} matching`} ({f.total} {noun} in total) ·{" "}
      <a href="#" onClick={(e) => { e.preventDefault(); f.clear(); }}>Clear filters</a>
    </div>
  );
}

// --------------------------------------------------------------------------- pages
function Overview() {
  const [days, setDays] = useState(7);
  const summary = useLoad<Summary>(() => api.summary(days), [days]);
  const broken = useLoad<Row[]>(() => api.failures(days * 24), [days]);
  const pipes = useLoad<Row[]>(() => api.pipelines(days * 24), [days]);
  const f = useListFilter(broken.data, "Failing since", (r) => r.failing_since, (r) => r.job_owner);
  const pf = useListFilter(pipes.data, "Failing since", (r) => r.failing_since, (r) => r.pipeline_owner);
  const notebooks = useLoad<Row[]>(() => api.notebooks(days * 24), [days]);
  const okJobs = useLoad<Row[]>(() => api.healthyJobs(days * 24), [days]);
  const okPipes = useLoad<Row[]>(() => api.healthyPipelines(days * 24), [days]);
  const hf = useListFilter(okJobs.data, "Healthy since", (r) => r.healthy_since, (r) => r.job_owner);
  const hpf = useListFilter(okPipes.data, "Healthy since", (r) => r.healthy_since, (r) => r.pipeline_owner);
  const [jobView, setJobView] = useState<Health>("failing");
  const [pipeView, setPipeView] = useState<Health>("failing");
  const k = summary.data?.kpis;
  usePageContext({
    label: "Overview",
    detail: k ? `Unless the user says otherwise, answer for the last ${days === 1 ? "24 hours" : `${days} days`} (the window on screen). On screen: ${k.failed_runs} failed runs of ${k.total_runs}, ${k.broken_now} jobs broken now, ${k.stale_tables} tables gone quiet, ${k.failed_pipeline_updates} failed pipeline updates of ${k.pipeline_updates}, ${k.pipelines_broken_now} pipelines broken now.${f.active ? ` The broken-jobs list is ${f.describe}: ${f.shown.slice(0, 10).map((j) => j.job_name).join(", ")}.` : ""}${pf.active ? ` The broken-pipelines list is ${pf.describe}.` : ""}${k.failing_notebooks ? ` Separately, ${k.failed_notebook_runs} child notebook runs (dbutils.notebook.run) failed across ${k.failing_notebooks} notebooks, ${k.notebooks_still_failing} still failing: ${(notebooks.data ?? []).slice(0, 5).map((n) => `${notebookName(n).name} (${n.failed_runs} failed)`).join(", ")}. These are not counted as broken jobs.` : ""}${okJobs.data ? ` ${okJobs.data.length} jobs and ${okPipes.data?.length ?? "?"} pipelines are healthy (last run succeeded).` : ""}${jobView === "healthy" ? ` The jobs list shows healthy jobs${hf.active ? `, ${hf.describe}` : ""}.` : ""}${pipeView === "healthy" ? ` The pipelines list shows healthy pipelines${hpf.active ? `, ${hpf.describe}` : ""}.` : ""}` : `Window: last ${days} days.`,
    starters: [`Summarize platform health for the last ${days === 1 ? "24 hours" : `${days} days`}`, "Which failures should I fix first, and why?", "Is the failure rate better or worse than the week before?"],
  }, [days, k, notebooks.data, f.describe, pf.describe, okJobs.data, okPipes.data, jobView, pipeView, hf.describe, hpf.describe]);
  const pct = (v: Row[string]) => `${(asNum(v) * 100).toFixed(1)}%`;

  return (
    <>
      <div className="row spread">
        <h1>Is the data platform healthy?</h1>
        <div className="seg">
          {[1, 7, 30].map((d) => <button key={d} className={d === days ? "on" : ""} onClick={() => setDays(d)}>{d === 1 ? "24 hours" : `${d} days`}</button>)}
        </div>
      </div>
      <p className="lede">Everything here comes from Databricks system tables through governed metric views — the same numbers Genie One answers from.</p>

      {k && <p className="callout"><b>{asNum(k.stale_tables)}</b> tables have gone quiet (not receiving data on schedule) · <a href="#/tables">Data freshness →</a></p>}

      <h2 className="section">Jobs</h2>
      <p className="callout">Scheduled and triggered jobs. Child notebook runs are counted separately, per notebook, below.</p>
      <Loading error={summary.error}>
        {k ? (
          <div className="grid kpis">
            <div className="card kpi"><div className="label">Broken right now</div><div className="value">{asNum(k.broken_now)}</div><div className="hint">jobs whose last run failed</div></div>
            <div className="card kpi"><div className="label">Failed runs</div><div className="value">{asNum(k.failed_runs)}</div><div className="hint">of {asNum(k.total_runs).toLocaleString()} runs</div></div>
            <div className="card kpi"><div className="label">Failure rate</div><div className="value">{pct(k.failure_rate)}</div><div className="hint">of finished runs</div></div>
            <div className="card kpi"><div className="label">Time to recover</div><div className="value">{k.mttr_hours === null ? "—" : `${asNum(k.mttr_hours).toFixed(1)} h`}</div><div className="hint">failure → next success (MTTR)</div></div>
          </div>
        ) : <div className="grid kpis">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton" />)}</div>}
      </Loading>

      <div className="grid two">
        <div className="card">
          <h2>Failed runs by day</h2>
          <div className="sub">Colored by what kind of problem it was</div>
          <Loading error={summary.error}>{summary.data && <StackedBars rows={summary.data.trend} days={days} />}</Loading>
        </div>
        <div className="card">
          <h2>What kind of problems</h2>
          <div className="sub">Hover a category for what it means</div>
          <Loading error={summary.error}>
            {summary.data && (summary.data.by_category.length ? (
              <table><tbody>{summary.data.by_category.map((r) => (
                <tr key={String(r.failure_category)}><td><Category name={String(r.failure_category)} /></td><td style={{ textAlign: "right" }}><b>{asNum(r.failed_runs)}</b> runs · {asNum(r.jobs)} jobs</td></tr>
              ))}</tbody></table>
            ) : <div className="empty">No failures in this window.</div>)}
          </Loading>
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <div className="row spread">
          <div>
            <div className="row"><h2>{jobView === "failing" ? "Broken right now" : "Healthy right now"}</h2>
              <HealthSwitch value={jobView} onChange={setJobView} failing={broken.data?.length} healthy={okJobs.data?.length} /></div>
            <div className="sub">{jobView === "failing" ? "Most repeated failures first — click one to see why and how to fix it" : "Jobs whose last run succeeded, most recent first"}</div>
          </div>
          <FilterControls f={jobView === "failing" ? f : hf} />
        </div>
        {jobView === "failing" ? (
          <Loading error={broken.error}>{broken.data && (
            <>
              <FilterCount f={f} noun="broken" limit={8} />
              <FailureTable rows={f.shown.slice(0, 8)} empty={f.active ? "No broken jobs match these filters." : undefined} />
            </>
          )}</Loading>
        ) : (
          <Loading error={okJobs.error}>{okJobs.data && (
            <>
              <FilterCount f={hf} noun="healthy" limit={8} />
              <HealthyJobTable rows={hf.shown.slice(0, 8)} empty={hf.active ? "No healthy jobs match these filters." : undefined} />
            </>
          )}</Loading>
        )}
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <div className="row spread">
          <div>
            <h2><Hint tip={NOTEBOOK_RUNS_HELP}>Failing child notebooks</Hint></h2>
            <div className="sub">{k && asNum(k.failing_notebooks) > 0
              ? <>{asNum(k.failed_notebook_runs)} failed runs from {asNum(k.failing_notebooks)} notebook{asNum(k.failing_notebooks) === 1 ? "" : "s"} ({asNum(k.notebooks_still_failing)} still failing) — click one to see the latest error</>
              : "Notebooks started from other notebooks with dbutils.notebook.run()"}</div>
          </div>
          {(notebooks.data?.length ?? 0) > 5 && <a href="#/failures?tab=notebooks">See all {notebooks.data?.length} →</a>}
        </div>
        <Loading error={notebooks.error}>{notebooks.data && <NotebookTable rows={notebooks.data.slice(0, 5)} />}</Loading>
      </div>

      <h2 className="section">Pipelines (SDP)</h2>
      <Loading error={summary.error}>
        {k ? (
          <div className="grid kpis">
            <div className="card kpi"><div className="label">Broken right now</div><div className="value">{asNum(k.pipelines_broken_now)}</div><div className="hint">pipelines whose last update failed</div></div>
            <div className="card kpi"><div className="label">Failed updates</div><div className="value">{asNum(k.failed_pipeline_updates)}</div><div className="hint">of {asNum(k.pipeline_updates).toLocaleString()} updates</div></div>
            <div className="card kpi"><div className="label">Failure rate</div><div className="value">{pct(k.pipeline_failure_rate)}</div><div className="hint">of finished updates</div></div>
            <div className="card kpi"><div className="label">Pipelines with failures</div><div className="value">{asNum(k.failing_pipelines)}</div><div className="hint">at least one failed update</div></div>
          </div>
        ) : <div className="grid kpis">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton" />)}</div>}
      </Loading>
      <div className="card">
        <div className="row spread">
          <div>
            <div className="row"><h2>{pipeView === "failing" ? "Broken right now" : "Healthy right now"}</h2>
              <HealthSwitch value={pipeView} onChange={setPipeView} failing={pipes.data?.length} healthy={okPipes.data?.length} /></div>
            <div className="sub">{pipeView === "failing" ? "Most repeated failures first — opens the pipeline or its last update in Databricks" : "Pipelines whose last update completed, most recent first"}</div>
          </div>
          <FilterControls f={pipeView === "failing" ? pf : hpf} />
        </div>
        {pipeView === "failing" ? (
          <Loading error={pipes.error}>{pipes.data && (
            <>
              <FilterCount f={pf} noun="broken" limit={8} />
              <PipelineTable rows={pf.shown.slice(0, 8)} empty={pf.active ? "No broken pipelines match these filters." : undefined} />
            </>
          )}</Loading>
        ) : (
          <Loading error={okPipes.error}>{okPipes.data && (
            <>
              <FilterCount f={hpf} noun="healthy" limit={8} />
              <HealthyPipelineTable rows={hpf.shown.slice(0, 8)} empty={hpf.active ? "No healthy pipelines match these filters." : undefined} />
            </>
          )}</Loading>
        )}
      </div>
    </>
  );
}

function FailureTable({ rows, empty }: { rows: Row[]; empty?: string }) {
  if (!rows.length) return <div className="empty">{empty ?? "Nothing is broken. 🎉"}</div>;
  return (
    <table>
      <thead><tr><th>Job</th><th>Problem</th><th>In a row</th><th>Failing since</th><th>Owner</th></tr></thead>
      <tbody>{rows.map((r) => (
        <tr key={String(r.job_id)} className="clickable" onClick={() => go(`/run/${r.last_run_id}`)}>
          <td><ExtLink href={r.job_url}><b>{r.job_name}</b></ExtLink></td>
          <td><Category name={String(r.failure_category)} /></td>
          <td>{asNum(r.consecutive_failures)}×</td>
          <td>{ago(r.failing_since)}</td>
          <td className="muted">{r.job_owner}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}

function PipelineTable({ rows, empty }: { rows: Row[]; empty?: string }) {
  if (!rows.length) return <div className="empty">{empty ?? "No pipelines are broken. 🎉"}</div>;
  return (
    <table>
      <thead><tr><th>Pipeline</th><th>In a row</th><th>Failing since</th><th>Last failure</th><th>Owner</th><th></th></tr></thead>
      <tbody>{rows.map((r) => (
        <tr key={String(r.pipeline_id)}>
          <td><ExtLink href={r.pipeline_url}><b>{r.pipeline_name}</b></ExtLink></td>
          <td>{asNum(r.consecutive_failures)}×</td>
          <td>{ago(r.failing_since)}</td>
          <td>{ago(r.last_failure)}</td>
          <td className="muted">{r.pipeline_owner}</td>
          <td><ExtLink href={r.update_url}>Last update</ExtLink></td>
        </tr>
      ))}</tbody>
    </table>
  );
}

/** "StagingToProductionETL" + its folder, from a workspace path; falls back when the path couldn't be looked up. */
function notebookName(r: Row): { name: string; folder: string } {
  const path = r.notebook_path ? String(r.notebook_path) : "";
  if (path) { const i = path.lastIndexOf("/"); return { name: path.slice(i + 1), folder: path.slice(0, i) }; }
  return r.notebook_id ? { name: `Notebook ${r.notebook_id}`, folder: "path not looked up yet (next refresh)" }
                       : { name: "Unknown notebook", folder: "the run didn't touch any tables, so lineage doesn't say which notebook" };
}

/** Child notebook runs grouped by notebook. Rows open the latest failed run in the app. */
function NotebookTable({ rows, empty }: { rows: Row[]; empty?: string }) {
  if (!rows.length) return <div className="empty">{empty ?? "No child notebook runs failed in this window. 🎉"}</div>;
  return (
    <table>
      <thead><tr><th>Notebook</th><th>Status</th><th>Runs</th><th>Last failure</th><th>Problem</th><th></th></tr></thead>
      <tbody>{rows.map((r) => {
        const { name, folder } = notebookName(r);
        return (
          <tr key={String(r.notebook_key)} className="clickable" onClick={() => go(`/run/${r.last_failed_run_id}`)}>
            <td><ExtLink href={r.notebook_url}><b>{name}</b></ExtLink><div className="muted small">{folder}</div>
              {r.last_error ? <div className="err-line" title={String(r.last_error)}>{String(r.last_error).split("\n")[0].slice(0, 180)}</div> : null}</td>
            <td>{r.still_failing ? <span className="status bad">✕ Still failing</span> : <span className="status ok">✓ Recovered</span>}</td>
            <td><b>{asNum(r.failed_runs)}</b> failed{asNum(r.succeeded_runs) ? <span className="muted"> · {asNum(r.succeeded_runs)} ok</span> : null}</td>
            <td>{ago(r.last_failure)}</td>
            <td><Category name={String(r.failure_category)} /></td>
            <td><ExtLink href={r.last_failed_run_url}>Latest failed run</ExtLink></td>
          </tr>
        );
      })}</tbody>
    </table>
  );
}

const NOTEBOOK_RUNS_HELP = "Started from inside another notebook with dbutils.notebook.run(). Databricks gives every one of these runs its own throwaway job id with no job page, so they're grouped here by the notebook that ran instead of being counted as separate broken jobs.";

function HealthyJobTable({ rows, empty }: { rows: Row[]; empty?: string }) {
  if (!rows.length) return <div className="empty">{empty ?? "No job has succeeded in this window."}</div>;
  return (
    <table>
      <thead><tr><th>Job</th><th>Last run</th><th>Succeeded in a row</th><th>Healthy since</th><th>Owner</th></tr></thead>
      <tbody>{rows.map((r) => (
        <tr key={String(r.job_id)} className="clickable" onClick={() => go(`/run/${r.last_run_id}`)}>
          <td><ExtLink href={r.job_url}><b>{r.job_name}</b></ExtLink></td>
          <td><span className="status ok">✓ {ago(r.last_run_end)}</span></td>
          <td>{asNum(r.consecutive_successes)}×</td>
          <td>{ago(r.healthy_since)}</td>
          <td className="muted">{r.job_owner}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}

function HealthyPipelineTable({ rows, empty }: { rows: Row[]; empty?: string }) {
  if (!rows.length) return <div className="empty">{empty ?? "No pipeline has completed an update in this window."}</div>;
  return (
    <table>
      <thead><tr><th>Pipeline</th><th>Last update</th><th>Succeeded in a row</th><th>Healthy since</th><th>Owner</th><th></th></tr></thead>
      <tbody>{rows.map((r) => (
        <tr key={String(r.pipeline_id)}>
          <td><ExtLink href={r.pipeline_url}><b>{r.pipeline_name}</b></ExtLink></td>
          <td><span className="status ok">✓ {ago(r.last_update_end)}</span></td>
          <td>{asNum(r.consecutive_successes)}×</td>
          <td>{ago(r.healthy_since)}</td>
          <td className="muted">{r.pipeline_owner}</td>
          <td><ExtLink href={r.update_url}>Last update</ExtLink></td>
        </tr>
      ))}</tbody>
    </table>
  );
}

function Failures() {
  const [tab, setTab] = useState<"jobs" | "notebooks" | "pipelines">(
    () => (new URLSearchParams(window.location.hash.split("?")[1]).get("tab") as "notebooks" | "pipelines") || "jobs");
  const jobs = useLoad<Row[]>(() => api.failures(168), []);
  const nbs = useLoad<Row[]>(() => api.notebooks(168), []);
  const pipes = useLoad<Row[]>(() => api.pipelines(168), []);
  const jf = useListFilter(jobs.data, "Failing since", (r) => r.failing_since, (r) => r.job_owner);
  const nf = useListFilter(nbs.data, "Last failure", (r) => r.last_failure, undefined, SINCE.slice(0, 4));
  const pf = useListFilter(pipes.data, "Failing since", (r) => r.failing_since, (r) => r.pipeline_owner);
  const f = tab === "jobs" ? jf : tab === "notebooks" ? nf : pf;
  usePageContext({
    label: `What's broken (${tab === "jobs" ? "jobs" : tab === "notebooks" ? "child notebook runs" : "pipelines"})`,
    detail: tab === "jobs"
      ? (jobs.data ? `Broken jobs on screen${jf.active ? ` (${jf.describe})` : ""}: ${jf.shown.slice(0, 10).map((j) => j.job_name).join(", ")}. Child notebook runs are on their own tab.` : "")
      : tab === "notebooks"
        ? (nbs.data ? `Failing child notebook runs (dbutils.notebook.run), grouped by notebook${nf.active ? ` (${nf.describe})` : ""}: ${nf.shown.slice(0, 10).map((n) => `${notebookName(n).name} — ${n.failed_runs} failed, ${n.still_failing ? "still failing" : "recovered"}`).join("; ") || "none"}.` : "")
        : (pipes.data ? `Broken Lakeflow (SDP) pipelines on screen${pf.active ? ` (${pf.describe})` : ""}: ${pf.shown.slice(0, 10).map((p) => p.pipeline_name).join(", ") || "none"}.` : ""),
    starters: tab === "jobs"
      ? ["Which of these failures are related to each other?", "Which broken job affects the most downstream tables?", "Are any of these caused by MuleSoft or BigQuery?"]
      : tab === "notebooks"
        ? ["Why is this notebook failing?", "Which job calls these notebooks?", "When did these notebooks start failing?"]
        : ["Which pipelines failed in the last week, and why?", "Which tables do the failing pipelines write?", "Which pipelines take longest to update?"],
  }, [tab, jobs.data, nbs.data, pipes.data, jf.describe, nf.describe, pf.describe]);
  const count = (d: Row[] | null) => (d ? ` (${d.length})` : "");
  return (
    <>
      <h1>What's broken</h1>
      <p className="lede">Jobs, child notebook runs and Lakeflow pipelines (SDP) that failed in the last 7 days.</p>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "jobs"} className={tab === "jobs" ? "on" : ""} onClick={() => setTab("jobs")}>Jobs{count(jobs.data)}</button>
        <button role="tab" aria-selected={tab === "notebooks"} className={tab === "notebooks" ? "on" : ""} onClick={() => setTab("notebooks")} title={NOTEBOOK_RUNS_HELP}>Notebook runs{count(nbs.data)}</button>
        <button role="tab" aria-selected={tab === "pipelines"} className={tab === "pipelines" ? "on" : ""} onClick={() => setTab("pipelines")}>Pipelines (SDP){count(pipes.data)}</button>
      </div>
      <div className="card">
        <div className="row spread">
          <div className="sub">{tab === "jobs" ? "Click a job for the cause, who is affected and how to fix it"
            : tab === "notebooks" ? "One row per notebook started with dbutils.notebook.run() — click one to see the latest error"
            : "Opens the pipeline or its last update in Databricks"}</div>
          <FilterControls f={f} />
        </div>
        <FilterCount f={f} noun="broken" />
        {tab === "jobs"
          ? <Loading error={jobs.error}>{jobs.data && <FailureTable rows={jf.shown} empty={jf.active ? "No broken jobs match these filters." : undefined} />}</Loading>
          : tab === "notebooks"
          ? <Loading error={nbs.error}>{nbs.data && <NotebookTable rows={nf.shown} empty={nf.active ? "No failing notebooks match these filters." : undefined} />}</Loading>
          : <Loading error={pipes.error}>{pipes.data && <PipelineTable rows={pf.shown} empty={pf.active ? "No broken pipelines match these filters." : undefined} />}</Loading>}
      </div>
    </>
  );
}

function Run({ runId, config }: { runId: string; config: AppConfig | null }) {
  const detail = useLoad<RunDetail>(() => api.run(runId), [runId]);
  const d = detail.data;
  const r = d?.run;
  usePageContext({
    label: r ? (r.is_notebook_run ? `Child notebook run of ${notebookName(r).name}` : `Run of ${r.job_name}`) : "Run detail",
    detail: r ? `${r.is_notebook_run ? `Child notebook run (dbutils.notebook.run) of notebook ${r.notebook_path ?? r.notebook_id ?? "unknown"}; it has no job of its own, so it can't be repaired by itself — re-run the job or notebook that calls it. ` : ""}job_id ${r.job_id}, run_id ${runId}, result ${r.result_state}, category ${r.failure_category}, code ${r.termination_code}.${d?.errors[0] ? ` Error: ${String(d.errors[0].error).slice(0, 300)}` : ""}` : `run_id ${runId}.`,
    starters: ["Why did this run fail, in plain English?", "Who is affected downstream if this stays broken?", "Has this job failed like this before?", "Should I repair it now or fix something first?"],
  }, [r, d]);

  return (
    <>
      <a href={r?.is_notebook_run ? "#/failures?tab=notebooks" : "#/failures"} className="muted">← What's broken</a>
      <Loading error={detail.error}>{d && r ? (
        <>
          <div className="row" style={{ marginTop: 10 }}><h1>{r.is_notebook_run ? notebookName(r).name : r.job_name}</h1><State v={r.result_state} /></div>
          <p className="reason">{r.is_failure ? <>It failed because <b>{String(r.failure_meaning ?? "of an unclassified error").replace(/\.$/, "").toLowerCase()}</b>.</> : "This run did not fail."}</p>
          <div className="row muted" style={{ fontSize: "0.88rem" }}>
            <Category name={String(r.failure_category)} /> · ended {fmtTime(r.end_time)} · owner {r.job_owner ?? "unknown"} · code {r.termination_code}
            {r.job_url ? <> · <ExtLink href={r.job_url}>job page</ExtLink></> : null}
            {r.is_notebook_run && r.notebook_url ? <> · <ExtLink href={r.notebook_url}>open notebook</ExtLink></> : null}
          </div>
          {r.is_notebook_run && (
            <p className="note">
              This is a <b>child notebook run</b>: another notebook started it with <code>dbutils.notebook.run()</code>
              {r.notebook_path ? <> to run <code>{String(r.notebook_path)}</code></> : null}. It has no job of its own, so it can't be repaired by
              itself — fix the cause, then re-run the job or notebook that calls it.
            </p>
          )}

          <div className="card" style={{ marginTop: 16 }}>
            <h2>Fix it</h2>
            <div className="sub">{String(r.first_step ?? "")}</div>
            {r.is_failure && r.is_notebook_run ? (
              <div className="grid fix-steps">
                <div>
                  <h3>See exactly what failed</h3>
                  <p className="muted">Opens this child run's output, with the cell that raised the error.</p>
                  <a className="btn primary" href={String(r.run_url)} target="_blank" rel="noreferrer">Open the run ↗</a>
                </div>
                <div>
                  <h3>Then re-run the caller</h3>
                  <p className="muted">Child runs can't be repaired on their own. Once the cause is fixed, re-run the job or notebook that calls {r.notebook_path ? <b>{notebookName(r).name}</b> : "this notebook"}.</p>
                  {r.notebook_url ? <a className="btn" href={String(r.notebook_url)} target="_blank" rel="noreferrer">Open the notebook ↗</a> : null}
                </div>
              </div>
            ) : r.is_failure ? (
              <div className="grid fix-steps">
                <div>
                  <h3>Cause was temporary, or already fixed?</h3>
                  <p className="muted">Repair re-runs only the failed tasks and the ones after them.</p>
                  <a className="btn primary" href={String(r.run_url)} target="_blank" rel="noreferrer">↻ Repair in Databricks ↗</a>
                </div>
                <div>
                  <h3>Something in the code or data needs fixing?</h3>
                  <p className="muted">Genie ZeroOps has the root-cause investigation and a suggested fix.</p>
                  <a className="btn" href={d.zeroops_url || config?.zeroops_url} target="_blank" rel="noreferrer">Open in Genie ZeroOps ↗</a>
                </div>
              </div>
            ) : <a className="btn" href={String(r.run_url)} target="_blank" rel="noreferrer">Open the run ↗</a>}
            {!r.is_notebook_run && <p className="muted" style={{ fontSize: "0.82rem", marginBottom: 0 }}>
              The link opens the run in Databricks, where you click <b>Repair run</b>. Databricks checks that you have "Can Manage Run" on the job
              {r.job_owner ? <> — if you don't, ask {r.job_owner}</> : null}.
            </p>}
          </div>

          {d.errors.length > 0 && (
            <div className="card" style={{ marginTop: 14 }}>
              <h2>The error</h2>
              {d.errors.map((e, i) => (
                <div key={i} style={{ marginTop: 10 }}><b>{e.task_key}</b><pre className="err">{String(e.error || e.trace || "No error text recorded.")}</pre></div>
              ))}
            </div>
          )}

          <div className="grid two" style={{ marginTop: 14 }}>
            <div className="card">
              <h2>Tasks in this run</h2>
              <div className="sub">Nested for-each iterations are indented; skipped tasks never ran because something before them failed</div>
              {!d.tasks.length && <div className="empty">{r.is_notebook_run ? "A child notebook run is a single notebook, with no separate tasks." : "No task details recorded for this run."}</div>}
              <table><tbody>{d.tasks.map((t) => (
                <tr key={String(t.task_run_id)}>
                  <td>{t.is_nested && <span className="tree-indent">↳</span>}{t.task_key}{t.is_retry && <span className="muted"> · retry</span>}</td>
                  <td><State v={t.result_state} /></td>
                  <td className="muted">{t.is_failure ? <Category name={String(t.failure_category)} /> : null}</td>
                </tr>
              ))}</tbody></table>
            </div>
            <div className="card">
              <h2>Who is affected</h2>
              <div className="sub">From Unity Catalog lineage, last 30 days</div>
              {d.impact.length ? (
                <table><tbody>{d.impact.map((x, i) => (
                  <tr key={i}><td className="muted">{["Writes", "Read by", "Then"][asNum(x.hop)]}</td><td><ExtLink href={x.url}>{String(x.impacted_asset).split(/(?<=[._])/).map((part, k) => <Fragment key={k}>{part}<wbr /></Fragment>)}</ExtLink></td><td className="muted">{String(x.asset_type).toLowerCase()}</td></tr>
                ))}</tbody></table>
              ) : <div className="empty">No downstream lineage recorded for this job.</div>}
            </div>
          </div>

          <div className="card" style={{ marginTop: 14 }}>
            <h2>{r.is_notebook_run ? "Recent runs of this notebook" : "Recent runs of this job"}</h2>
            <table><tbody>{d.history.map((h) => (
              <tr key={String(h.run_id)} className="clickable" onClick={() => go(`/run/${h.run_id}`)}>
                <td>{fmtTime(h.start_time)}</td><td><State v={h.result_state} /></td><td>{h.failure_category !== "Success" && <Category name={String(h.failure_category)} />}</td>
              </tr>
            ))}</tbody></table>
          </div>

        </>
      ) : undefined}</Loading>
    </>
  );
}

function Tables() {
  const tables = useLoad<Row[]>(() => api.tables(), []);
  // Only tables written in the last 30 days are tracked, so the long bucket is "Over 7 days" rather than 30.
  const tf = useListFilter(tables.data, "Last write", (r) => r.last_write, undefined,
                           [...SINCE.slice(0, 4), { label: "Over 7 days", minH: 168 }]);
  const [status, setStatus] = useState<"all" | "quiet" | "fresh">("all");
  const quiet = tf.shown.filter((t) => t.is_stale), fresh = tf.shown.filter((t) => !t.is_stale);
  const shown = status === "all" ? tf.shown : status === "quiet" ? quiet : fresh;
  const filtered = tf.active || status !== "all";
  usePageContext({
    label: "Data freshness",
    detail: tables.data ? `Tables gone quiet on screen${tf.active ? ` (list ${tf.describe})` : ""}: ${quiet.slice(0, 10).map((t) => t.table_name).join(", ")}.${status !== "all" ? ` The list shows only ${status === "quiet" ? "gone-quiet" : "fresh"} tables (${shown.length}).` : ""}` : "",
    starters: ["Which stale tables matter most?", "Why did these tables stop receiving data?", "Which jobs write the stale tables?"],
  }, [tables.data, tf.describe, status]);
  return (
    <>
      <h1>Is the data fresh?</h1>
      <p className="lede">Tables that jobs and pipelines write on a schedule. A table has "gone quiet" when it's been more than twice its usual gap since the last write.</p>
      <div className="legend-line">
        <span className="status ok">✓ Fresh</span><span className="muted">updated within twice its usual gap</span>
        <span className="status bad">● Gone quiet</span><span className="muted">no write for more than twice its usual gap: data is probably old</span>
      </div>
      <div className="card">
        <div className="row spread">
          <div className="sub">{filtered && <>{shown.length} matching ({tf.total} tables in total) ·{" "}
            <a href="#" onClick={(e) => { e.preventDefault(); tf.clear(); setStatus("all"); }}>Clear filters</a></>}</div>
          <div className="row filters">
            <span className="muted">Status</span>
            <StatusSwitch label="Filter by status" value={status} onChange={setStatus} options={[
              { value: "all", label: `All${count(tf.shown.length)}` },
              { value: "quiet", label: `● Gone quiet${count(quiet.length)}`, tone: "bad" },
              { value: "fresh", label: `✓ Fresh${count(fresh.length)}`, tone: "ok" },
            ]} />
            <FilterControls f={tf} />
          </div>
        </div>
        <Loading error={tables.error}>{tables.data && (shown.length === 0 ? <div className="empty">No tables match these filters.</div> : (
        <table className="fresh-table"><thead><tr>
          <th><Hint tip="The table, as catalog.schema.table. Only tables written on a schedule (in 3 or more separate hours over the last 30 days) are tracked.">Table</Hint></th>
          <th><Hint tip="Fresh: written recently enough. Gone quiet: it's been more than twice the usual gap since the last write, so readers are probably looking at old data.">Status</Hint></th>
          <th><Hint tip="When a job or pipeline last wrote to this table, from Unity Catalog lineage. Hover a value for the exact time.">Last write</Hint></th>
          <th><Hint tip="The typical (median) time between writes over the last 30 days. A table is flagged once the current gap is more than twice this.">Usually every</Hint></th>
          <th><Hint tip="The job or pipeline that last wrote this table, from Unity Catalog lineage. Opens it in Databricks.">Written by</Hint></th>
        </tr></thead>
          <tbody>{shown.map((t) => {
            const since = asNum(t.hours_since_write), gap = asNum(t.typical_gap_hours);
            const span = (h: number) => (h < 48 ? `${Math.round(h)} h` : `${Math.round(h / 24)} days`);
            const why = t.is_stale
              ? `Gone quiet: no write for ${span(since)}; it usually updates every ${span(gap)}. That's more than twice its usual gap, so the data is probably old. Check the job that writes it.`
              : `Fresh: last write ${span(since)} ago; it usually updates every ${span(gap)}.`;
            return (
              <tr key={String(t.table_name)}>
                <td>{String(t.table_name).split(/(?<=[._])/).map((part, k) => <Fragment key={k}>{part}<wbr /></Fragment>)}</td>
                <td><Hint tip={why} plain>{t.is_stale ? <span className="status bad">● Gone quiet</span> : <span className="status ok">✓ Fresh</span>}</Hint></td>
                <td><Hint tip={t.last_write ? new Date(String(t.last_write)).toLocaleString() : "No write recorded"} plain>{ago(t.last_write)}</Hint></td>
                <td className="muted"><Hint tip={`Median gap between writes over the last 30 days: ${gap} h`} plain>{span(gap)}</Hint></td>
                <td><ExtLink href={t.last_writer_url}>{t.last_writer_name ?? `${String(t.last_writer_type ?? "").toLowerCase()} ${t.last_writer_id ?? ""}`}</ExtLink></td>
              </tr>
            );
          })}</tbody></table>
      ))}</Loading></div>
    </>
  );
}

// --------------------------------------------------------------------------- shell
export function App() {
  return <PageContextProvider><Shell /></PageContextProvider>;
}

function Shell() {
  const hash = useHash();
  const [genieOpen, setGenieOpen] = useState(false); // collapsed by default, like the workspace assistant
  const config = useLoad<AppConfig>(() => api.config(), []);
  useEffect(() => { if (config.data) document.title = `Job Ops · ${config.data.company}`; }, [config.data]);
  const path = hash.replace(/^#/, "");
  const nav: [string, string][] = [["/", "Overview"], ["/failures", "What's broken"], ["/tables", "Data freshness"]];
  const active = (p: string) => (p === "/" ? path === "/" : path.startsWith(p) || (p === "/failures" && path.startsWith("/run/")));

  let page: ReactNode = <Overview />;
  if (path.startsWith("/run/")) page = <Run runId={path.slice(5)} config={config.data} />;
  else if (path.split("?")[0] === "/failures") page = <Failures key={path} />;
  else if (path === "/tables") page = <Tables />;

  return (
    <div className={`shell${genieOpen ? " with-genie" : ""}`}>
      <nav className="nav">
        <div className="brand">Job Ops<small>{config.data ? `${config.data.company} data platform` : "Data platform"}</small></div>
        {nav.map(([p, label]) => <a key={p} href={`#${p}`} className={active(p) ? "active" : ""}>{label}</a>)}
        {config.data?.has_presentation && <a className="deck-link" href="/presentation/" target="_blank" rel="noreferrer">The presentation ↗</a>}
        <div className="who">{config.data?.user}</div>
      </nav>
      <main>
        <div className="topbar"><SparkleButton open={genieOpen} onToggle={() => setGenieOpen((o) => !o)} /></div>
        {page}
      </main>
      <GeniePanel open={genieOpen} onClose={() => setGenieOpen(false)} />
    </div>
  );
}
