"""Integrations MCP server (mock) — what Genie One calls for "is the source system down?".

Three groups of tools, each registered as its own Unity Catalog MCP Service via tool-name prefixes:

  mulesoft_*  MuleSoft integration flows (stand-in for the real MuleSoft MCP server)
  gcp_*       GCP / BigQuery health (placeholder; what "GCP" means is an open question with the customer)
  job_*       Error text for a Databricks job run (system tables only keep the termination code)

The MuleSoft and GCP tools return mock data that follows the demo's failure flags (when DEMO_FLAGS_TABLE
is set) so the story lines up with the failing demo jobs. Swap in the real MuleSoft MCP URL with the
bundle variable `mulesoft_mcp_url`; the Genie One skills keep working because only the connection changes.

Runs as a Databricks App: binds to $DATABRICKS_APP_PORT and serves streamable HTTP at /mcp.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import RunResultState
from mcp.server.fastmcp import FastMCP

PORT = int(os.environ.get("DATABRICKS_APP_PORT") or os.environ.get("PORT") or "8000")
DEMO_FLAGS_TABLE = os.environ.get("DEMO_FLAGS_TABLE", "")
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")

mcp = FastMCP("job-ops-integrations", host="0.0.0.0", port=PORT, stateless_http=True)


@lru_cache(maxsize=1)
def workspace() -> WorkspaceClient:
    return WorkspaceClient()  # the app's service principal


def demo_flag(name: str) -> bool:
    """Read a demo failure flag; with no flags table configured, report the failure (the scripted story)."""
    if not (DEMO_FLAGS_TABLE and WAREHOUSE_ID):
        return True
    try:
        res = workspace().statement_execution.execute_statement(
            warehouse_id=WAREHOUSE_ID, wait_timeout="20s",
            statement=f"SELECT enabled FROM {DEMO_FLAGS_TABLE} WHERE flag = '{name}'")
        rows = (res.result and res.result.data_array) or []
        return bool(rows) and str(rows[0][0]).lower() == "true"
    except Exception:  # noqa: BLE001 — mock data must never break the conversation
        return True


def hours_ago(h: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=h)).strftime("%Y-%m-%d %H:%M UTC")


# --------------------------------------------------------------------------- MuleSoft (mock)
FLOWS: dict[str, dict[str, str]] = {
    "inventory-sync-to-lakehouse": {"schedule": "nightly 02:00 CT", "owner": "Supply Chain Integration team",
                                    "target": "landing volume → Inventory Sync job"},
    "pos-transactions-to-lakehouse": {"schedule": "nightly 05:30 CT", "owner": "Store Systems team",
                                      "target": "Nightly Sales Load job"},
    "oms-orders-stream": {"schedule": "every 15 min", "owner": "eCommerce Platform team",
                          "target": "Customer Orders Pipeline"},
}


def flow_state(name: str) -> dict[str, Any]:
    failed = name == "inventory-sync-to-lakehouse" and demo_flag("mulesoft_feed_missing")
    state: dict[str, Any] = {"flow": name, **FLOWS[name], "status": "FAILED" if failed else "RUNNING",
                             "last_success": hours_ago(26 if failed else 2)}
    if failed:
        state["last_error"] = {
            "time": hours_ago(3),
            "message": "SFTP:CONNECTIVITY — Could not connect to sftp.vendor-wms.example.com:22 "
                       "(connection refused). 0 of 1 files delivered to the lakehouse landing volume.",
            "retries": 3,
        }
    return state


@mcp.tool()
def mulesoft_list_flows() -> list[dict[str, Any]]:
    """List the MuleSoft integration flows that feed Databricks, with their current status and owner team."""
    return [flow_state(name) for name in FLOWS]


@mcp.tool()
def mulesoft_get_flow_status(flow_name: str) -> dict[str, Any]:
    """Status of one MuleSoft flow: RUNNING or FAILED, last success, last error and the owning team.

    Args:
        flow_name: Flow name, e.g. "inventory-sync-to-lakehouse". Partial names are matched.
    """
    match = next((n for n in FLOWS if flow_name.lower() in n), None)
    if not match:
        return {"error": f"No flow matching '{flow_name}'", "flows": list(FLOWS)}
    return flow_state(match)


@mcp.tool()
def mulesoft_recent_errors(hours: int = 24) -> list[dict[str, Any]]:
    """MuleSoft flow errors in the last N hours (default 24)."""
    errors = [f for f in (flow_state(n) for n in FLOWS) if "last_error" in f]
    return [{"flow": e["flow"], "owner": e["owner"], **e["last_error"]} for e in errors] if hours >= 3 else []


# --------------------------------------------------------------------------- GCP / BigQuery (placeholder)
@mcp.tool()
def gcp_service_health() -> dict[str, Any]:
    """Health of the GCP services Databricks depends on (BigQuery, BigQuery Storage API)."""
    outage = demo_flag("bigquery_outage")
    return {
        "project": "acme-digital",
        "services": [
            {"service": "BigQuery", "status": "DEGRADED" if outage else "OK"},
            {"service": "BigQuery Storage Read API", "status": "UNAVAILABLE" if outage else "OK",
             **({"since": hours_ago(4), "detail": "Requests from the Databricks service account time out"} if outage else {})},
        ],
    }


@mcp.tool()
def gcp_bigquery_job_status(dataset: str = "web_analytics") -> dict[str, Any]:
    """Recent BigQuery export/read activity for a dataset (default web_analytics)."""
    outage = demo_flag("bigquery_outage")
    return {"dataset": f"acme-digital.{dataset}", "last_successful_read": hours_ago(4 if outage else 1),
            "failed_reads_last_4h": 4 if outage else 0}


# --------------------------------------------------------------------------- Databricks job error text
@mcp.tool()
def job_get_run_error(run_id: str) -> dict[str, Any]:
    """The error message and stack-trace summary for each failed task in a Databricks job run.

    System tables only record a termination code, so this reads the run output. The app's service
    principal needs CAN VIEW on the job.

    Args:
        run_id: The job run id (run_id from v_job_runs).
    """
    w = workspace()
    run = w.jobs.get_run(int(run_id))
    failed: list[dict[str, Any]] = []
    for task in run.tasks or []:
        state = task.state
        if not state or state.result_state not in (RunResultState.FAILED, RunResultState.TIMEDOUT):
            continue
        if task.for_each_task:
            # The error lives on the failed iterations (nested task runs), not on the for-each task.
            iterations = w.jobs.get_run(task.run_id).iterations or []
            # attempt_number > 0 is an automatic retry of an earlier iteration, not another input.
            targets = [(f"{task.task_key} › {i.task_key}", i.run_id, i.state, i.attempt_number or 0) for i in iterations
                       if i.state and i.state.result_state in (RunResultState.FAILED, RunResultState.TIMEDOUT)]
        else:
            targets = [(task.task_key, task.run_id, state, task.attempt_number or 0)]
        for key, task_run_id, task_state, attempt in targets:
            if task.pipeline_task:
                # Pipeline tasks only say "see the pipeline logs"; the real error is in the pipeline event log.
                events = w.pipelines.list_pipeline_events(task.pipeline_task.pipeline_id, filter="level='ERROR'", max_results=5)
                event = next(iter(events), None)
                detail = [x.message for x in ((event and event.error and event.error.exceptions) or []) if x.message]
                failed.append({"task_key": key, "error": "\n".join([(event and event.message) or "", *detail[:2]]).strip()[:1500],
                               "trace_tail": ""})
                continue
            out = w.jobs.get_run_output(task_run_id)
            failed.append({
                "task_key": key,
                "attempt": attempt,
                "error": (out.error or (task_state.state_message or ""))[:1500],
                "trace_tail": (out.error_trace or "")[-1500:],
            })
    return {"run_id": run_id, "job_name": run.run_name, "state": str(run.state.result_state if run.state else ""),
            "failed_tasks": failed or [{"note": "No failed task output found; open the run page for details."}]}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
