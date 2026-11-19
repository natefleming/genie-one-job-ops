# Databricks notebook source
# MAGIC %md
# MAGIC # Job Ops — deploy the "Job Ops" Genie Agent
# MAGIC Genie spaces are not a native bundle resource, so this notebook creates or updates the
# MAGIC space with the SDK. Genie One routes job-health questions to this agent; the agent
# MAGIC answers from the metric views and functions created by `setup_objects`.
# MAGIC Writes the space id to the job task value `space_id`.

# COMMAND ----------
dbutils.widgets.text("catalog", "retail_consumer_goods")
dbutils.widgets.text("schema", "job_ops")
dbutils.widgets.text("warehouse_id", "")
dbutils.widgets.text("ops_group", "account users")
dbutils.widgets.text("title", "Job Ops")
dbutils.widgets.text("company_name", "Acme")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
warehouse_id = dbutils.widgets.get("warehouse_id")
ops_group = dbutils.widgets.get("ops_group")
title = dbutils.widgets.get("title")
company = dbutils.widgets.get("company_name")
fq = f"{catalog}.{schema}"

# COMMAND ----------
import json

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()


def qid(n: int) -> str:
    """Genie ids are 32-char hex strings."""
    return f"{n:032x}"


sample_questions: list[str] = [
    "What is broken right now?",
    "How many job runs failed in the last 7 days, by failure category?",
    "Which jobs have failed more than once this week?",
    "What is our mean time to recover from a failed job over the last 30 days?",
    "Which tables have stopped receiving data?",
]

example_sqls: list[tuple[str, str]] = [
    ("What is broken right now?",
     f"SELECT job_name, failure_category, consecutive_failures, failing_since, run_url\nFROM {fq}.failing_now(24)"),
    ("How many job runs failed in the last 7 days, by failure category?",
     f"SELECT failure_category, MEASURE(failed_runs) AS failed_runs\nFROM {fq}.mv_job_runs\n"
     "WHERE run_date >= current_date() - 7 AND is_failure\nGROUP BY ALL ORDER BY failed_runs DESC"),
    ("What is our mean time to recover from a failed job over the last 30 days?",
     f"SELECT ROUND(MEASURE(avg_hours_to_recover), 2) AS mttr_hours, MEASURE(unrecovered_failures) AS still_broken\n"
     f"FROM {fq}.mv_job_runs WHERE run_date >= current_date() - 30"),
    ("Which tables have stopped receiving data?",
     f"SELECT table_name, MEASURE(max_hours_since_write) AS hours_since_write, MEASURE(avg_typical_gap_hours) AS usual_gap_hours\n"
     f"FROM {fq}.mv_table_freshness WHERE is_stale GROUP BY ALL ORDER BY hours_since_write DESC"),
]

instructions = f"""You help the data platform team at {company} understand and resolve failed jobs and pipelines.
Speak plainly: the audience is not deeply technical. Lead with the answer, then the detail.

Data:
- mv_job_runs: job run health. Use MEASURE(failed_runs), MEASURE(failure_rate), MEASURE(avg_hours_to_recover) (MTTR).
- mv_task_runs: task-level health inside jobs; is_nested marks for-each iterations; skipped_downstream_tasks are tasks that never ran because something upstream failed.
- mv_pipeline_updates: Lakeflow pipeline update health.
- mv_table_freshness: is_stale = the table has gone quiet ("receiving no data").
- failure_taxonomy: what each termination code means and the first step to take.

Functions (prefer these for the questions they cover):
- {fq}.failing_now(hours): what is broken right now, with how many times in a row it has failed. Leaves out child notebook runs.
- {fq}.failing_notebooks(hours): child notebook runs (dbutils.notebook.run) that failed, one row per notebook with its path.
- {fq}.run_tasks(run_id): which tasks inside a run failed.
- {fq}.downstream_impact(job_id): which tables, jobs, dashboards and Genie agents are affected.
- {fq}.run_links(run_id): links to the run (Repair run), the job, and the ZeroOps inbox.

Rules:
- Failure categories: Data Error, Compute Error, Access & Configuration, Capacity & Limits, Platform. Cancelled is not a failure.
- Default time window is the last 7 days unless the user says otherwise.
- Child notebook runs (is_notebook_run) get a throwaway job id each, so never count them as separate broken jobs: group them by notebook with failing_notebooks, and filter mv_job_runs with NOT is_notebook_run when counting jobs. They can't be repaired on their own; the fix is to re-run the job or notebook that calls them.
- Whenever you mention a specific failed run, include its run_url so the user can open it.
- Never claim to have re-run or fixed anything. To re-run, the user opens the run link and clicks Repair run; Databricks checks their permissions.
- For the root cause and a suggested code fix, point the user to Genie ZeroOps (zeroops_url from run_links).
"""

serialized = {
    "version": 2,
    "config": {"sample_questions": [{"id": qid(0x1000 + i), "question": [q]} for i, q in enumerate(sample_questions)]},
    "data_sources": {"tables": sorted(
        [{"identifier": f"{fq}.{t}"} for t in
         ["mv_job_runs", "mv_task_runs", "mv_pipeline_updates", "mv_table_freshness", "failure_taxonomy"]],
        key=lambda t: t["identifier"])},
    "instructions": {
        "text_instructions": [{"id": qid(0x3000), "content": [instructions]}],
        "example_question_sqls": [
            {"id": qid(0x2000 + i), "question": [q], "sql": [s]} for i, (q, s) in enumerate(example_sqls)],
        "sql_functions": [
            {"id": qid(0x4000 + i), "identifier": f"{fq}.{fn}"}
            for i, fn in enumerate(["downstream_impact", "failing_notebooks", "failing_now", "run_links", "run_tasks"])],
    },
    "benchmarks": {"questions": [
        {"id": qid(0x5000 + i), "question": [q], "answer": [{"format": "SQL", "content": [s]}]}
        for i, (q, s) in enumerate(example_sqls)]},
}

# COMMAND ----------
if not warehouse_id:
    warehouse_id = next(iter(w.warehouses.list())).id

existing = [s for s in (w.genie.list_spaces().spaces or []) if s.title == title]
if existing:
    space = w.genie.update_space(existing[0].space_id, serialized_space=json.dumps(serialized),
                                 title=title, warehouse_id=warehouse_id)
    print("Updated Genie Agent")
else:
    parent = f"/Workspace/Users/{w.current_user.me().user_name}/genie_spaces"
    w.workspace.mkdirs(parent)
    space = w.genie.create_space(warehouse_id=warehouse_id, serialized_space=json.dumps(serialized), title=title,
                                 description=f"Job and pipeline health for {company}: what broke, why, who is affected and how to fix it.",
                                 parent_path=parent)
    print("Created Genie Agent")

# Let the ops group use the agent. Workspace ACLs call the all-users group "users";
# Unity Catalog calls it "account users".
acl_group = "users" if ops_group == "account users" else ops_group
w.api_client.do("PATCH", f"/api/2.0/permissions/genie/{space.space_id}",
                body={"access_control_list": [{"group_name": acl_group, "permission_level": "CAN_RUN"}]})

print(f"SPACE_ID: {space.space_id}\nOpen: {w.config.host.rstrip('/')}/genie/rooms/{space.space_id}")
dbutils.jobs.taskValues.set("space_id", space.space_id)
