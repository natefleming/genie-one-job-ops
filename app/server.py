"""Job Ops app — FastAPI backend.

Every data call runs as the signed-in user (on-behalf-of): the Databricks Apps proxy forwards the
user's token in X-Forwarded-Access-Token, so people only see what Unity Catalog lets them see.

Re-running a job is deliberately a link, not a button that calls the API: Databricks Apps user tokens
can't carry a Jobs API scope, and a service principal re-running jobs would hide who did it. The user
opens the failed run in Databricks and clicks Repair run; Databricks checks their own permission.

The React UI is pre-built into ./static (see frontend/); this file serves it and the /api routes.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from itertools import chain
from pathlib import Path
from typing import Any

import mlflow
import requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.config import Config
from databricks.sdk.errors import DatabricksError
from databricks.sdk.service.sql import StatementParameterListItem, StatementState
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from databricks_agentkit.runtime import configure_tracing, start_trace
from loguru import logger
from pydantic import BaseModel, Field

from logging_setup import configure_logging

configure_logging()
# MLflow traces of each Genie turn go to the experiment bound as an app resource (MLFLOW_EXPERIMENT_ID +
# MLFLOW_TRACKING_URI). Without them (local runs) tracing is off and start_trace is a no-op.
configure_tracing()

WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "")
SCHEMA = os.environ.get("JOB_OPS_SCHEMA", "retail_consumer_goods.job_ops")
ZEROOPS_URL = os.environ.get("ZEROOPS_URL", "{host}/jobs?o={workspace_id}")
GENIE_AGENT_TITLE = os.environ.get("GENIE_AGENT_TITLE", "Job Ops")
COMPANY_NAME = os.environ.get("COMPANY_NAME", "Acme")
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Job Ops")


# --------------------------------------------------------------------------- auth & SQL
@lru_cache(maxsize=1)
def app_client() -> WorkspaceClient:
    """The app's own service principal — only used for workspace metadata, never for data."""
    return WorkspaceClient()


def user_client(request: Request) -> WorkspaceClient:
    token = request.headers.get("x-forwarded-access-token")
    if not token:  # local development: fall back to the developer's own CLI profile
        return WorkspaceClient()
    # Explicit PAT config so the SDK ignores the app SP's client id/secret in the environment.
    return WorkspaceClient(config=Config(host=app_client().config.host, token=token, auth_type="pat"))


def _param(name: str, value: Any) -> StatementParameterListItem:
    kind = "INT" if isinstance(value, int) and not isinstance(value, bool) else "STRING"
    return StatementParameterListItem(name=name, value=None if value is None else str(value), type=kind)


def _convert(value: str | None, type_name: str) -> Any:
    """The statement API returns every value as a string; give booleans and numbers their real types."""
    if value is None:
        return None
    if type_name == "BOOLEAN":
        return value.lower() == "true"
    if type_name in ("BYTE", "SHORT", "INT", "LONG"):
        return int(value)
    if type_name in ("FLOAT", "DOUBLE", "DECIMAL"):
        return float(value)
    return value


def query(w: WorkspaceClient, sql: str, **params: Any) -> list[dict[str, Any]]:
    res = w.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID, statement=sql, wait_timeout="50s",
        parameters=[_param(k, v) for k, v in params.items()])
    if res.status and res.status.state != StatementState.SUCCEEDED:
        raise HTTPException(502, (res.status.error.message if res.status.error else str(res.status.state)))
    columns = (res.manifest.schema.columns or []) if res.manifest and res.manifest.schema else []
    types = [c.type_name.value if c.type_name else "STRING" for c in columns]
    return [{c.name: _convert(v, t) for c, v, t in zip(columns, row, types)}
            for row in ((res.result and res.result.data_array) or [])]


# --------------------------------------------------------------------------- models
class AppConfig(BaseModel):
    host: str = Field(description="Workspace URL")
    workspace_id: str = Field(description="Workspace id (the ?o= parameter)")
    user: str = Field(description="Signed-in user")
    zeroops_url: str = Field(description="Genie ZeroOps inbox for this workspace")
    company: str = Field(description="Company name shown in the nav and page title")
    has_presentation: bool = Field(description="The customer deck was built into the app (/presentation/)")


class Summary(BaseModel):
    kpis: dict[str, Any] = Field(description="Headline numbers for the window")
    trend: list[dict[str, Any]] = Field(description="Failed runs per day per failure category")
    by_category: list[dict[str, Any]] = Field(description="Failed runs per failure category")


class RunDetail(BaseModel):
    run: dict[str, Any] = Field(description="The job run: outcome, category, plain-English meaning, links")
    tasks: list[dict[str, Any]] = Field(description="Every task in the run, including nested ones")
    errors: list[dict[str, Any]] = Field(description="Error text for failed tasks, read as the user")
    impact: list[dict[str, Any]] = Field(description="Downstream lineage impact of the job")
    history: list[dict[str, Any]] = Field(description="Recent runs of the same job")
    zeroops_url: str = Field(description="Where to open the ZeroOps investigation")


# --------------------------------------------------------------------------- routes
@app.get("/api/config", response_model=AppConfig, operation_id="getConfig")
def get_config(w: WorkspaceClient = Depends(user_client)) -> AppConfig:
    host = app_client().config.host.rstrip("/")
    ws_id = str(app_client().get_workspace_id())
    return AppConfig(host=host, workspace_id=ws_id, user=w.current_user.me().user_name or "",
                     zeroops_url=ZEROOPS_URL.format(host=host, workspace_id=ws_id), company=COMPANY_NAME,
                     has_presentation=(STATIC / "presentation").exists())


@app.get("/api/summary", response_model=Summary, operation_id="getSummary")
def get_summary(days: int = 7, w: WorkspaceClient = Depends(user_client)) -> Summary:
    sql = {
        "kpis": (f"""SELECT MEASURE(total_runs) AS total_runs, MEASURE(failed_runs) AS failed_runs,
                       MEASURE(failure_rate) AS failure_rate, MEASURE(avg_hours_to_recover) AS mttr_hours,
                       MEASURE(failing_jobs) AS failing_jobs, MEASURE(unrecovered_failures) AS unrecovered_failures
                FROM {SCHEMA}.mv_job_runs WHERE run_date >= date_sub(current_date(), :days) AND NOT is_notebook_run""", {"days": days}),
        "broken": (f"SELECT count(*) AS n FROM {SCHEMA}.failing_now(:h)", {"h": days * 24}),
        "stale": (f"SELECT MEASURE(stale_tables) AS n FROM {SCHEMA}.mv_table_freshness", {}),
        "pipelines": (f"""SELECT MEASURE(updates) AS updates, MEASURE(failed_updates) AS failed_updates,
                       MEASURE(failing_pipelines) AS failing_pipelines, MEASURE(pipeline_failure_rate) AS failure_rate
                     FROM {SCHEMA}.mv_pipeline_updates WHERE update_date >= date_sub(current_date(), :days)""", {"days": days}),
        "pipelines_broken": (f"SELECT count(*) AS n FROM ({BROKEN_PIPELINES_SQL})", {"h": days * 24}),
        "notebooks": (f"""SELECT count(*) AS notebooks, count_if(still_failing) AS still_failing,
                            coalesce(sum(failed_runs), 0) AS failed_runs FROM {SCHEMA}.failing_notebooks(:h)""", {"h": days * 24}),
        "trend": (f"""SELECT run_date, failure_category, MEASURE(failed_runs) AS failed_runs FROM {SCHEMA}.mv_job_runs
                 WHERE run_date >= date_sub(current_date(), :days) AND is_failure AND NOT is_notebook_run
                 GROUP BY ALL ORDER BY run_date""", {"days": days}),
        "by_category": (f"""SELECT failure_category, MEASURE(failed_runs) AS failed_runs, MEASURE(failing_jobs) AS jobs
                       FROM {SCHEMA}.mv_job_runs WHERE run_date >= date_sub(current_date(), :days) AND is_failure
                         AND NOT is_notebook_run
                       GROUP BY ALL ORDER BY failed_runs DESC""", {"days": days}),
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as pool:
        futures = {k: pool.submit(query, w, q, **p) for k, (q, p) in sql.items()}
        out = {k: f.result() for k, f in futures.items()}
    kpis = out["kpis"][0]
    pipes = out["pipelines"][0]
    kpis.update(broken_now=out["broken"][0]["n"], stale_tables=out["stale"][0]["n"],
                failed_pipeline_updates=pipes["failed_updates"], pipeline_updates=pipes["updates"],
                failing_pipelines=pipes["failing_pipelines"], pipeline_failure_rate=pipes["failure_rate"],
                pipelines_broken_now=out["pipelines_broken"][0]["n"],
                failing_notebooks=out["notebooks"][0]["notebooks"], notebooks_still_failing=out["notebooks"][0]["still_failing"],
                failed_notebook_runs=out["notebooks"][0]["failed_runs"])
    trend, by_category = out["trend"], out["by_category"]
    return Summary(kpis=kpis, trend=trend, by_category=by_category)


@app.get("/api/failures", response_model=list[dict[str, Any]], operation_id="listFailures")
def list_failures(hours: int = 168, w: WorkspaceClient = Depends(user_client)) -> list[dict[str, Any]]:
    return query(w, f"SELECT * FROM {SCHEMA}.failing_now(:h)", h=hours)


# Pipelines whose most recent update in the last :h hours failed, with the failure streak — the pipeline twin of
# the failing_now() SQL function that the job lists use.
BROKEN_PIPELINES_SQL = f"""
    WITH recent AS (
      SELECT *, row_number() OVER (PARTITION BY pipeline_id ORDER BY start_time DESC) AS rn
      FROM {SCHEMA}.pipeline_updates
      WHERE result_state IS NOT NULL AND start_time >= current_timestamp() - make_interval(0, 0, 0, 0, :h, 0, 0)
    ),
    last_ok AS (
      SELECT pipeline_id, max(start_time) AS last_success FROM {SCHEMA}.pipeline_updates
      WHERE result_state = 'COMPLETED' GROUP BY pipeline_id
    ),
    streak AS (
      SELECT u.pipeline_id, count(*) AS consecutive_failures, min(u.start_time) AS failing_since
      FROM {SCHEMA}.pipeline_updates u LEFT JOIN last_ok o USING (pipeline_id)
      WHERE u.is_failure AND u.start_time > coalesce(o.last_success, TIMESTAMP'1970-01-01')
      GROUP BY u.pipeline_id
    )
    SELECT r.pipeline_id, r.pipeline_name, r.pipeline_owner, r.update_id AS last_update_id, r.end_time AS last_failure,
           s.consecutive_failures, s.failing_since, r.update_type, r.update_url
    FROM recent r JOIN streak s USING (pipeline_id)
    WHERE r.rn = 1 AND r.is_failure"""


@app.get("/api/pipelines", response_model=list[dict[str, Any]], operation_id="listPipelineFailures")
def list_pipeline_failures(hours: int = 168, w: WorkspaceClient = Depends(user_client)) -> list[dict[str, Any]]:
    rows = query(w, f"{BROKEN_PIPELINES_SQL} ORDER BY consecutive_failures DESC, last_failure DESC", h=hours)
    return [{**r, "pipeline_url": entity_url(w, "PIPELINE", r["pipeline_id"])} for r in rows]


# Jobs / pipelines whose most recent run or update in the last :h hours succeeded, with the success streak since
# their last failure — the healthy counterpart of the broken lists.
HEALTHY_JOBS_SQL = f"""
    WITH recent AS (
      SELECT *, row_number() OVER (PARTITION BY job_id ORDER BY start_time DESC) AS rn
      FROM {SCHEMA}.job_runs
      WHERE result_state IS NOT NULL AND start_time >= current_timestamp() - make_interval(0, 0, 0, 0, :h, 0, 0)
        AND NOT is_notebook_run
    ),
    last_bad AS (SELECT job_id, max(start_time) AS last_failure FROM {SCHEMA}.job_runs WHERE is_failure GROUP BY job_id),
    streak AS (
      SELECT r.job_id, count(*) AS consecutive_successes, min(r.start_time) AS healthy_since
      FROM {SCHEMA}.job_runs r LEFT JOIN last_bad b USING (job_id)
      WHERE r.result_state = 'SUCCEEDED' AND r.start_time > coalesce(b.last_failure, TIMESTAMP'1970-01-01')
      GROUP BY r.job_id
    )
    SELECT r.job_id, r.job_name, r.job_owner, r.run_id AS last_run_id, r.end_time AS last_run_end,
           s.consecutive_successes, s.healthy_since, r.run_url, r.job_url
    FROM recent r JOIN streak s USING (job_id)
    WHERE r.rn = 1 AND r.result_state = 'SUCCEEDED'
    ORDER BY r.end_time DESC"""

HEALTHY_PIPELINES_SQL = f"""
    WITH recent AS (
      SELECT *, row_number() OVER (PARTITION BY pipeline_id ORDER BY start_time DESC) AS rn
      FROM {SCHEMA}.pipeline_updates
      WHERE result_state IS NOT NULL AND start_time >= current_timestamp() - make_interval(0, 0, 0, 0, :h, 0, 0)
    ),
    last_bad AS (SELECT pipeline_id, max(start_time) AS last_failure FROM {SCHEMA}.pipeline_updates WHERE is_failure GROUP BY pipeline_id),
    streak AS (
      SELECT u.pipeline_id, count(*) AS consecutive_successes, min(u.start_time) AS healthy_since
      FROM {SCHEMA}.pipeline_updates u LEFT JOIN last_bad b USING (pipeline_id)
      WHERE u.result_state = 'COMPLETED' AND u.start_time > coalesce(b.last_failure, TIMESTAMP'1970-01-01')
      GROUP BY u.pipeline_id
    )
    SELECT r.pipeline_id, r.pipeline_name, r.pipeline_owner, r.end_time AS last_update_end,
           s.consecutive_successes, s.healthy_since, r.update_url
    FROM recent r JOIN streak s USING (pipeline_id)
    WHERE r.rn = 1 AND r.result_state = 'COMPLETED'
    ORDER BY r.end_time DESC"""


def notebook_url(w: WorkspaceClient, notebook_id: Any) -> str:
    return f"{w.config.host.rstrip('/')}/?o={workspace_id()}#notebook/{notebook_id}" if notebook_id else ""


@app.get("/api/notebooks", response_model=list[dict[str, Any]], operation_id="listFailingNotebooks")
def list_failing_notebooks(hours: int = 168, w: WorkspaceClient = Depends(user_client)) -> list[dict[str, Any]]:
    """Child notebook runs (dbutils.notebook.run) that failed, one row per notebook."""
    rows = query(w, f"SELECT * FROM {SCHEMA}.failing_notebooks(:h)", h=hours)
    return [{**r, "notebook_url": notebook_url(w, r["notebook_id"])} for r in rows]


@app.get("/api/healthy/jobs", response_model=list[dict[str, Any]], operation_id="listHealthyJobs")
def list_healthy_jobs(hours: int = 168, w: WorkspaceClient = Depends(user_client)) -> list[dict[str, Any]]:
    return query(w, HEALTHY_JOBS_SQL, h=hours)


@app.get("/api/healthy/pipelines", response_model=list[dict[str, Any]], operation_id="listHealthyPipelines")
def list_healthy_pipelines(hours: int = 168, w: WorkspaceClient = Depends(user_client)) -> list[dict[str, Any]]:
    rows = query(w, HEALTHY_PIPELINES_SQL, h=hours)
    return [{**r, "pipeline_url": entity_url(w, "PIPELINE", r["pipeline_id"])} for r in rows]


@app.get("/api/tables", response_model=list[dict[str, Any]], operation_id="listTableFreshness")
def list_table_freshness(w: WorkspaceClient = Depends(user_client)) -> list[dict[str, Any]]:
    # Writer names come from the snapshot tables (fast); writers with no runs in 90 days fall back to their id.
    rows = query(w, f"""
        WITH names AS (
          SELECT 'JOB' AS t, r.job_id AS id,
                 max_by(coalesce(concat(element_at(split(p.notebook_path, '/'), -1), ' (notebook run)'), r.job_name), r.start_time) AS name,
                 max(r.notebook_id) AS notebook_id
          FROM {SCHEMA}.job_runs r LEFT JOIN {SCHEMA}.notebook_paths p USING (notebook_id) GROUP BY ALL
          UNION ALL
          SELECT 'PIPELINE', pipeline_id, max_by(pipeline_name, start_time), NULL FROM {SCHEMA}.pipeline_updates GROUP BY ALL
        )
        SELECT f.table_name, f.last_write, round(f.hours_since_write, 1) AS hours_since_write,
               round(f.typical_gap_hours, 1) AS typical_gap_hours, f.is_stale, f.last_writer_type, f.last_writer_id,
               n.name AS last_writer_name, n.notebook_id AS last_writer_notebook_id
        FROM {SCHEMA}.table_freshness f LEFT JOIN names n ON n.t = f.last_writer_type AND n.id = f.last_writer_id
        ORDER BY f.is_stale DESC, f.hours_since_write DESC""")
    # A notebook run's throwaway job has no page; link its notebook instead.
    return [{**r, "last_writer_url": notebook_url(w, r["last_writer_notebook_id"]) if r["last_writer_notebook_id"]
             else entity_url(w, str(r["last_writer_type"]), r["last_writer_id"])} for r in rows]


def pipeline_error(w: WorkspaceClient, pipeline_id: str) -> str:
    """Pipeline tasks only say "see the pipeline logs"; pull the real error from the pipeline event log."""
    for event in w.pipelines.list_pipeline_events(pipeline_id, filter="level='ERROR'", max_results=10):
        details = [x.message for x in ((event.error and event.error.exceptions) or []) if x.message]
        if details or event.message:
            return "\n".join([event.message or "", *details[:2]]).strip()[:2000]
    return ""


def failure_details(w: WorkspaceClient, run_id: int) -> list[dict[str, Any]]:
    """Error text as the user if their token allows it; otherwise read-only as the app's service principal
    (needs CAN VIEW on the job). Apps user tokens currently can't carry a Jobs API scope."""
    errors = run_errors(w, run_id)
    if errors and "required scopes" in errors[0].get("error", ""):
        errors = run_errors(app_client(), run_id)
        if errors and errors[0].get("task_key") == "":
            errors = [{"task_key": "", "error": "Open the run in Databricks to see the error (grant the Job Ops app "
                       "CAN VIEW on jobs to show it here)."}]
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for e in errors:  # a retried task fails with the same error twice
        unique.setdefault((e.get("task_key", ""), e.get("error", "")), e)
    return list(unique.values())


def run_errors(w: WorkspaceClient, run_id: int) -> list[dict[str, Any]]:
    """Error text for failed tasks (and failed for-each iterations), read with the user's own access."""
    errors: list[dict[str, Any]] = []
    try:
        run = w.jobs.get_run(run_id)
    except DatabricksError as e:
        return [{"task_key": "", "error": f"Could not read the run: {e}"}]
    for task in run.tasks or []:
        if not task.state or str(task.state.result_state) not in ("RunResultState.FAILED", "RunResultState.TIMEDOUT"):
            continue
        targets = [(task.task_key, task.run_id)]
        if task.for_each_task:
            iterations = w.jobs.get_run(task.run_id).iterations or []
            targets = [(f"{task.task_key} › {i.task_key}", i.run_id) for i in iterations
                       if i.state and str(i.state.result_state) == "RunResultState.FAILED"]
        for key, task_run_id in targets:
            try:
                if task.pipeline_task:
                    errors.append({"task_key": key, "error": pipeline_error(w, task.pipeline_task.pipeline_id), "trace": ""})
                    continue
                out = w.jobs.get_run_output(task_run_id)
                errors.append({"task_key": key, "error": (out.error or "")[:2000], "trace": (out.error_trace or "")[-2000:]})
            except DatabricksError as e:
                errors.append({"task_key": key, "error": str(e)})
    return errors


@app.get("/api/runs/{run_id}", response_model=RunDetail, operation_id="getRun")
def get_run(run_id: str, w: WorkspaceClient = Depends(user_client)) -> RunDetail:
    rows = query(w, f"""SELECT r.*, p.notebook_path FROM {SCHEMA}.job_runs r
                        LEFT JOIN {SCHEMA}.notebook_paths p USING (notebook_id) WHERE r.run_id = :r""", r=run_id)
    if not rows:
        raise HTTPException(404, "Run not found in the last 90 days (system tables can lag by a few minutes).")
    run = {**rows[0], "notebook_url": notebook_url(w, rows[0].get("notebook_id"))}
    # A child notebook run is the only run of its throwaway job, so its history is the notebook's other runs.
    by_notebook = bool(run.get("is_notebook_run") and run.get("notebook_id"))
    with ThreadPoolExecutor(max_workers=5) as pool:
        links = pool.submit(query, w, f"SELECT zeroops_url FROM {SCHEMA}.run_links(:r)", r=run_id)
        tasks = pool.submit(query, w, f"SELECT * FROM {SCHEMA}.run_tasks(:r)", r=run_id)
        impact = pool.submit(query, w, f"SELECT * FROM {SCHEMA}.downstream_impact(:j) ORDER BY hop, asset_type", j=run["job_id"])
        history = pool.submit(query, w, f"""SELECT run_id, start_time, result_state, failure_category, run_url FROM {SCHEMA}.job_runs
                                         WHERE {"notebook_id" if by_notebook else "job_id"} = :k
                                         ORDER BY start_time DESC LIMIT 15""",
                              k=run["notebook_id"] if by_notebook else run["job_id"])
        errors = pool.submit(failure_details, w, int(run_id)) if run.get("is_failure") else None
        saved = pool.submit(query, w, f"SELECT run_id, error FROM {SCHEMA}.notebook_errors WHERE notebook_id = :n",
                            n=run["notebook_id"]) if by_notebook and run.get("is_failure") else None
        error_list = errors.result() if errors else []
        # Child runs usually can't be read as the user or the app; fall back to the error the refresh captured.
        if saved and saved.result() and (not error_list or error_list[0].get("task_key") == ""):
            s = saved.result()[0]
            label = "Error from this run" if s["run_id"] == run_id else "Latest captured error of this notebook"
            error_list = [{"task_key": label, "error": s["error"]}]
        return RunDetail(
            run=run, tasks=tasks.result(), errors=error_list,
            impact=group_notebook_runs(w, impact.result()),
            history=history.result(), zeroops_url=(links.result() or [{}])[0].get("zeroops_url", ""),
        )


def group_notebook_runs(w: WorkspaceClient, impact: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Downstream readers that are child notebook runs each have their own throwaway job id; show them once per
    notebook (linked to the notebook) instead of as many separate jobs. Everything else gets its job/pipeline link."""
    ids = sorted({str(x["impacted_asset"]).split(":")[-1] for x in impact if x["asset_type"] == "JOB"})
    runs = {r["job_id"]: r for r in query(w, f"""
        SELECT r.job_id, max(r.notebook_id) AS notebook_id, max(p.notebook_path) AS notebook_path
        FROM {SCHEMA}.job_runs r LEFT JOIN {SCHEMA}.notebook_paths p USING (notebook_id)
        WHERE r.is_notebook_run AND array_contains(split(:ids, ','), r.job_id) GROUP BY r.job_id""", ids=",".join(ids))} if ids else {}
    out: dict[tuple[Any, ...], dict[str, Any]] = {}
    for x in impact:
        nb = runs.get(str(x["impacted_asset"]).split(":")[-1]) if x["asset_type"] == "JOB" else None
        if nb:
            name = str(nb["notebook_path"] or "").rsplit("/", 1)[-1] or "unknown notebook"
            x = {**x, "impacted_asset": name, "asset_type": "NOTEBOOK RUN", "url": notebook_url(w, nb["notebook_id"])}
        else:
            x = {**x, "url": entity_url(w, str(x["asset_type"]), x["impacted_asset"])}
        out.setdefault((x["hop"], x["written_table"], x["impacted_asset"], x["asset_type"]), x)
    return list(out.values())


# --------------------------------------------------------------------------- Genie side panel
# The panel streams Genie One: it routes across the workspace and reports what it used (skills, ontology snippets,
# sources). Genie One has no public API yet, so this talks to the endpoint the Databricks CLI (`databricks genie ask`)
# uses. Everything that knows that endpoint lives in `genie_one_events`; if it is unavailable the panel falls back to
# the Job Ops Genie Agent (space Conversation API). Set GENIE_ENGINE=agent to force the fallback.
GENIE_ENGINE = os.environ.get("GENIE_ENGINE", "one")
GENIE_ONE_PATH = "/api/2.0/data-rooms/tools/onechat/responses"
HEARTBEAT_SECONDS = 8.0


class GenieAsk(BaseModel):
    question: str = Field(description="What the user typed")
    context: str = Field(default="", description="What the user is looking at, so Genie answers about this page")
    conversation_id: str | None = Field(default=None, description="Continue this conversation; empty starts a new one")


class GenieUnavailable(Exception):
    """Genie One could not be reached before any answer started; use the fallback."""


Event = dict[str, Any]


def genie_one_events(w: WorkspaceClient, content: str, conversation_id: str | None) -> Iterator[Event]:
    """Stream Genie One and translate its Responses-style items into the panel's event vocabulary:
    start, thought, skill, knowledge, query, memory, step, answer."""
    body: dict[str, Any] = {"input": [{"type": "message", "role": "user",
                                       "content": [{"type": "input_text", "text": content}]}],
                            "enable_viz": True, "source": "job_ops_app"}
    if conversation_id:
        body["conversationId"] = conversation_id
    headers = {**w.config.authenticate(), "Content-Type": "application/json", "Accept": "text/event-stream"}
    try:
        resp = requests.post(w.config.host.rstrip("/") + GENIE_ONE_PATH, json=body, headers=headers,
                             stream=True, timeout=(15, 300))
    except requests.RequestException as e:
        raise GenieUnavailable(str(e)) from e
    if resp.status_code != 200:
        raise GenieUnavailable(f"HTTP {resp.status_code}: {resp.text[:300]}")

    resp.encoding = "utf-8"  # text/event-stream has no charset; requests would guess Latin-1
    seen: set[str] = set()  # items arrive as `added` and again as `done`
    thread_url = ""
    for event in sse_events(resp):
        if event.get("type") == "response.created":
            conv = event.get("conversation_id") or conversation_id or ""
            thread_url = workspace_url(w, f"/one/chat/threads/{conv}") if conv else ""
            yield {"type": "start", "conversation_id": conv, "thread_url": thread_url}
            continue
        # The final snapshot repeats every item; anything not seen yet (e.g. a dropped answer) is handled from it.
        items = (event.get("response") or {}).get("output") or [] if event.get("type") == "response.done" else [event.get("item") or {}]
        for item in items:
            yield from translate_item(item, seen, w)


def sse_events(resp: requests.Response) -> Iterator[Event]:
    """Parse a Server-Sent Events body; one event may span several `data:` lines until a blank line."""
    data: list[str] = []
    for raw in resp.iter_lines(decode_unicode=True):
        line = raw or ""
        if line.startswith("data:"):
            data.append(line[5:].lstrip())
            continue
        if line.strip() or not data:
            continue  # `event:` / `id:` lines, or a blank line with nothing buffered
        payload, data = "\n".join(data), []
        if payload != "[DONE]":
            try:
                yield json.loads(payload)
            except ValueError:
                pass
    if data:
        try:
            yield json.loads("\n".join(data))
        except ValueError:
            pass


@lru_cache(maxsize=1)
def workspace_id() -> str:
    return str(app_client().get_workspace_id())


def workspace_url(w: WorkspaceClient, path: str) -> str:
    return f"{w.config.host.rstrip('/')}{path}?o={workspace_id()}"


def entity_url(w: WorkspaceClient, entity_type: str, entity_id: Any) -> str:
    """Workspace link for a job or pipeline id (lineage sometimes prefixes it, e.g. "job:123"); "" for anything else."""
    path = {"JOB": "/jobs/", "PIPELINE": "/pipelines/"}.get(entity_type)
    ident = str(entity_id or "").split(":")[-1]
    return workspace_url(w, path + ident) if path and ident else ""


def skill_url(w: WorkspaceClient, full_name: str) -> str:
    """The skill's page in Catalog Explorer (Genie One's own links go to its skill viewer instead)."""
    parts = full_name.split(".")
    return workspace_url(w, "/explore/data/skills/" + "/".join(parts)) if len(parts) == 3 else ""


def translate_item(item: dict[str, Any], seen: set[str], w: WorkspaceClient) -> Iterator[Event]:
    """One Genie One output item → panel events (skips items already translated). Skills and Pages get `url`s to
    where they live (Catalog Explorer, Discover); each citation gets a `link` — its Unity Catalog page for skills,
    otherwise Genie One's own URL."""
    key = f"{item.get('type')}:{item.get('id')}"
    if not item or key in seen:
        return
    seen.add(key)
    meta = item.get("metadata") or {}
    ui = meta.get("ui_type") or ""
    kind = item.get("type")
    if kind == "message":
        parts = [c for c in item.get("content") or [] if c.get("type") == "output_text"]
        text = "".join(c.get("text", "") for c in parts).strip()
        if ui == "FINAL_RESPONSE":
            citations = [a for c in parts for a in c.get("annotations") or [] if a.get("type") == "databricks_asset_citation"]
            yield {"type": "answer", "markdown": text, "citations": [
                {**{k: a.get(k) for k in ("index", "title", "url", "asset_type", "identifier")},
                 "link": (a.get("asset_type") == "USER_SKILL" and skill_url(w, a.get("identifier") or "")) or a.get("url")}
                for a in citations]}
        elif text:
            yield {"type": "thought", "text": text}
    elif kind == "function_call":
        if ui == "LOAD_SKILLS":
            for sk in meta.get("skills") or []:
                yield {"type": "skill", "name": sk.get("name", ""), "description": sk.get("description", ""),
                       "url": skill_url(w, sk.get("skill_id") or "")}
        elif ui == "QUERY_EXECUTION":
            sql = meta.get("query") or ""
            if not sql:
                try:
                    sql = json.loads(item.get("arguments") or "{}").get("query", "")
                except ValueError:
                    sql = ""
            yield {"type": "query", "sql": sql}
        elif "EPISODIC_MEMORY" in ui:
            yield {"type": "memory"}
        elif ui == "VIZ":
            yield {"type": "step", "name": "create_viz"}
        elif ui != "SEARCH_RESULTS":
            yield {"type": "step", "name": item.get("name") or ui.lower()}
    elif kind == "function_call_output" and ui == "VIZ":
        try:
            definition = json.loads(meta.get("viz_definition") or "{}")
        except ValueError:
            definition = {}
        spec = definition.get("renderSpec") or {}
        yield {"type": "viz", "id": meta.get("embed_id") or meta.get("asset_id") or "",
               "title": (spec.get("frame") or {}).get("title", ""), "spec": spec, "statement_id": meta.get("statement_id", "")}
    elif kind == "function_call_output" and ui == "SEARCH_RESULTS":
        pages = [{**{k: p.get(k) for k in ("name", "domain", "description", "synonyms", "relevance_score", "certified", "id")},
                  "url": workspace_url(w, f"/discover/pages/{p['id']}") if p.get("id") else ""}
                 for p in meta.get("knowledge_pages") or []]
        yield {"type": "knowledge", "query": meta.get("query", ""), "pages": pages}


def genie_space_id(w: WorkspaceClient) -> str:
    spaces = [s for s in (w.genie.list_spaces().spaces or []) if s.title == GENIE_AGENT_TITLE]
    if not spaces:
        raise HTTPException(404, f"Genie Agent '{GENIE_AGENT_TITLE}' not found — run the setup job.")
    return spaces[0].space_id


def agent_events(w: WorkspaceClient, content: str, conversation_id: str | None) -> Iterator[Event]:
    """Fallback: the Job Ops Genie Agent through the space Conversation API (no sources, skills or ontology)."""
    space = genie_space_id(w)
    waiter = (w.genie.create_message(space, conversation_id, content) if conversation_id
              else w.genie.start_conversation(space, content))
    conv, msg_id = waiter.conversation_id, waiter.message_id
    yield {"type": "start", "conversation_id": conv, "engine": "agent"}
    yield {"type": "thought", "text": f"Asking the {GENIE_AGENT_TITLE} agent…"}
    announced: set[str] = set()
    for _ in range(150):
        msg = w.genie.get_message(space, conv, msg_id)
        for att in msg.attachments or []:
            if att.query and att.attachment_id and att.attachment_id not in announced:
                announced.add(att.attachment_id)
                yield {"type": "query", "sql": att.query.query or ""}
        status = msg.status.value if msg.status else ""
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError((msg.error.error if msg.error else "") or f"Genie {status.lower()}")
        if status == "COMPLETED":
            text = "\n".join(a.text.content for a in msg.attachments or [] if a.text and a.text.content)
            table: dict[str, Any] | None = None
            for att in msg.attachments or []:
                if att.query and att.attachment_id:
                    stmt = w.genie.get_message_attachment_query_result(space, conv, msg_id, att.attachment_id).statement_response
                    if stmt and stmt.manifest and stmt.manifest.schema:
                        table = {"columns": [c.name or "" for c in stmt.manifest.schema.columns or []],
                                 "rows": ((stmt.result and stmt.result.data_array) or [])[:50]}
            yield {"type": "answer", "markdown": text.strip(), "citations": [], "table": table}
            return
        time.sleep(1.5 if _ < 5 else 2.5)
    raise RuntimeError("Genie took too long to answer.")


def with_heartbeat(events: Iterator[Event]) -> Iterator[Event]:
    """Pass events through, adding a ping whenever the upstream is quiet, so proxies keep the stream open
    (Genie One goes silent for ~20 s while it writes the final answer)."""
    q: queue.Queue[tuple[str, Any]] = queue.Queue()

    def pump() -> None:
        try:
            for e in events:
                q.put(("event", e))
            q.put(("end", None))
        except Exception as exc:  # noqa: BLE001 — surfaced to the caller below
            q.put(("error", exc))

    threading.Thread(target=pump, daemon=True).start()
    while True:
        try:
            kind, value = q.get(timeout=HEARTBEAT_SECONDS)
        except queue.Empty:
            yield {"type": "ping"}
            continue
        if kind == "end":
            return
        if kind == "error":
            raise value
        yield value


@app.get("/api/genie/result/{statement_id}", operation_id="getGenieResult")
def get_genie_result(statement_id: str, w: WorkspaceClient = Depends(user_client)) -> dict[str, Any]:
    """Rows behind a Genie One chart (the statement Genie ran as this user)."""
    st = w.statement_execution.get_statement(statement_id)
    if not st.status or st.status.state != StatementState.SUCCEEDED or not st.manifest or not st.manifest.schema:
        raise HTTPException(404, "That result isn't available any more — open it in Genie One.")
    columns = st.manifest.schema.columns or []
    types = [c.type_name.value if c.type_name else "STRING" for c in columns]
    rows = [[_convert(v, t) for v, t in zip(row, types)] for row in ((st.result and st.result.data_array) or [])[:500]]
    return {"columns": [c.name for c in columns], "types": types, "rows": rows}


def turn_events(w: WorkspaceClient, body: GenieAsk, content: str, user: str) -> Iterator[Event]:
    """One Genie turn as one MLflow trace: Genie One, or the Job Ops agent when Genie One is unavailable.
    Consumed entirely by with_heartbeat's thread, so the trace's span stays in one context."""
    with start_trace("genie_turn", inputs={"question": body.question, "context": body.context},
                     session_id=body.conversation_id) as span:
        if span is not None and user:
            mlflow.update_current_trace(metadata={"mlflow.trace.user": user})
        engine, answer, queries = "one", "", []
        try:
            if GENIE_ENGINE == "agent":
                raise GenieUnavailable("GENIE_ENGINE=agent")
            events = genie_one_events(w, content, body.conversation_id)
            first = next(events, None)  # GenieUnavailable can only come before the first event
        except GenieUnavailable as e:
            logger.warning("Genie One unavailable, falling back to the {} agent: {}", GENIE_AGENT_TITLE, e)
            engine = "agent"
            yield {"type": "notice", "text": f"Genie One isn't available here, so the {GENIE_AGENT_TITLE} agent is "
                                             "answering. Sources, skills and ontology aren't shown for its answers."}
            events, first = agent_events(w, content, None), None
        for e in chain([first] if first else [], events):
            if e["type"] == "start" and span is not None and e.get("conversation_id"):
                mlflow.update_current_trace(metadata={"mlflow.trace.session": e["conversation_id"]})
            elif e["type"] == "query":
                queries.append(e.get("sql", ""))
            elif e["type"] == "answer":
                answer = e.get("markdown", "")
            yield e
        if span is not None:
            span.set_attributes({"genie.engine": engine})
            span.set_outputs({"engine": engine, "answer": answer, "queries": queries})
        logger.info("Genie turn answered by {} ({} queries, {} chars)", engine, len(queries), len(answer))


@app.post("/api/genie/stream", operation_id="streamGenie")
def stream_genie(body: GenieAsk, request: Request, w: WorkspaceClient = Depends(user_client)) -> StreamingResponse:
    """Newline-delimited JSON events for one Genie turn, streamed as they happen."""
    content = f"{body.question}\n\n(Context: {body.context})" if body.context else body.question
    user = request.headers.get("x-forwarded-email", "")
    started = time.monotonic()

    def run() -> Iterator[str]:
        def emit(e: Event) -> str:
            return json.dumps(e, default=str) + "\n"

        try:
            for e in with_heartbeat(turn_events(w, body, content, user)):
                yield emit(e)
        except Exception as e:  # noqa: BLE001 — the panel shows it instead of a broken stream
            logger.exception("Genie turn failed")
            yield emit({"type": "error", "message": str(e)})
        yield emit({"type": "done", "elapsed_s": round(time.monotonic() - started, 1)})

    return StreamingResponse(run(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --------------------------------------------------------------------------- UI
if STATIC.exists():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")
    if (STATIC / "presentation").exists():  # the customer deck, copied in by `npm run build`
        app.mount("/presentation", StaticFiles(directory=STATIC / "presentation", html=True), name="presentation")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        # Never cache the shell: it names the current hashed bundles, so a stale copy runs old code after a deploy.
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
