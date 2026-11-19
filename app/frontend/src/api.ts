// Thin typed client for the FastAPI backend. Every call runs as the signed-in user.
export type Row = Record<string, string | number | boolean | null>;

export interface AppConfig { host: string; workspace_id: string; user: string; zeroops_url: string; company: string; has_presentation: boolean }
export interface Summary { kpis: Row; trend: Row[]; by_category: Row[] }
export interface RunDetail {
  run: Row; tasks: Row[]; errors: Row[]; impact: Row[]; history: Row[];
  zeroops_url: string;
}
/** `url` is Genie One's link (used to match inline citations); `link` is where to send the user (Unity Catalog for skills). */
export interface Citation { index: number; title: string; url: string; link?: string; asset_type: string; identifier: string }
export interface KnowledgePage {
  name: string; domain: string; description: string; synonyms: string[] | null; relevance_score: number; certified: boolean; id: string; url?: string;
}
/** Genie One chart spec (renderSpec): widgetType + encodings by field name. */
export interface VizSpec {
  widgetType?: string;
  encodings?: Record<string, { fieldName?: string; axis?: { title?: string }; scale?: { type?: string } } | undefined>;
  frame?: { title?: string };
}
export interface GenieResult { columns: string[]; types: string[]; rows: (string | number | boolean | null)[][] }
/** One event from /api/genie/stream (newline-delimited JSON). */
export type GenieEvent =
  | { type: "start"; conversation_id: string; engine?: string; thread_url?: string }
  | { type: "thought"; text: string }
  | { type: "skill"; name: string; description: string; url?: string }
  | { type: "knowledge"; query: string; pages: KnowledgePage[] }
  | { type: "query"; sql: string }
  | { type: "memory" }
  | { type: "step"; name: string }
  | { type: "answer"; markdown: string; citations: Citation[]; table?: { columns: string[]; rows: (string | null)[][] } | null; suggested_actions?: string[] }
  | { type: "viz"; id: string; title: string; spec: VizSpec; statement_id: string }
  | { type: "notice"; text: string }
  | { type: "error"; message: string }
  | { type: "ping" }
  | { type: "done"; elapsed_s: number };

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  config: () => call<AppConfig>("/api/config"),
  summary: (days: number) => call<Summary>(`/api/summary?days=${days}`),
  failures: (hours: number) => call<Row[]>(`/api/failures?hours=${hours}`),
  pipelines: (hours: number) => call<Row[]>(`/api/pipelines?hours=${hours}`),
  notebooks: (hours: number) => call<Row[]>(`/api/notebooks?hours=${hours}`),
  healthyJobs: (hours: number) => call<Row[]>(`/api/healthy/jobs?hours=${hours}`),
  healthyPipelines: (hours: number) => call<Row[]>(`/api/healthy/pipelines?hours=${hours}`),
  tables: () => call<Row[]>("/api/tables"),
  run: (runId: string) => call<RunDetail>(`/api/runs/${runId}`),
  genieResult: (statementId: string) => call<GenieResult>(`/api/genie/result/${statementId}`),
  /** Stream one Genie turn; calls onEvent for every event as it arrives. Resolves when the stream ends. */
  streamGenie: async (question: string, context: string, conversation_id: string | null,
                      onEvent: (e: GenieEvent) => void, signal: AbortSignal): Promise<void> => {
    const res = await fetch("/api/genie/stream", {
      method: "POST", headers: { "Content-Type": "application/json" }, signal,
      body: JSON.stringify({ question, context, conversation_id }),
    });
    if (!res.ok || !res.body) throw new Error(`Genie request failed (${res.status})`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const flush = (line: string) => { if (line.trim()) onEvent(JSON.parse(line) as GenieEvent); };
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      lines.forEach(flush);
    }
    flush(buffer + decoder.decode()); // the last event may arrive without a trailing newline
  },
};

export const asNum = (v: Row[string]): number => (v === null || v === undefined ? 0 : Number(v));
export const fmtTime = (v: Row[string]): string =>
  v ? new Date(String(v)).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "—";
export const ago = (v: Row[string]): string => {
  if (!v) return "—";
  const h = (Date.now() - new Date(String(v)).getTime()) / 36e5;
  return h < 1 ? `${Math.max(1, Math.round(h * 60))} min ago` : h < 48 ? `${Math.round(h)} h ago` : `${Math.round(h / 24)} days ago`;
};
