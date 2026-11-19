# Databricks notebook source
# MAGIC %md
# MAGIC # Job Ops — register the integrations MCP server in Unity Catalog
# MAGIC Genie One reaches outside systems through **MCP services**: Unity Catalog objects that put a governed
# MAGIC proxy in front of an MCP server. One HTTP connection points at the integrations app, and three services
# MAGIC expose slices of its tools by name prefix:
# MAGIC
# MAGIC | Service | Tools | Notes |
# MAGIC |---|---|---|
# MAGIC | `mcp_mulesoft` | `mulesoft_*` | Mock. Point at the real MuleSoft MCP server instead — see docs/CUSTOMER_DEPLOY.md |
# MAGIC | `mcp_gcp` | `gcp_*` | Placeholder until the customer confirms what "GCP" covers |
# MAGIC | `mcp_job_ops` | `job_*` | Error text for failed runs (system tables keep only the code) |
# MAGIC
# MAGIC Idempotent. Needs the integrations app to be running.

# COMMAND ----------
dbutils.widgets.text("catalog", "retail_consumer_goods")
dbutils.widgets.text("schema", "job_ops")
dbutils.widgets.text("app_name", "mcp-job-ops-integrations")
dbutils.widgets.text("ops_app_name", "job-ops")
dbutils.widgets.text("connection_name", "", "UC connection name; empty = <app_name>_conn")
dbutils.widgets.text("ops_group", "account users")
dbutils.widgets.text("demo_flags_table", "")
dbutils.widgets.text("view_jobs_tag", "source_system", "Give both app SPs CAN VIEW on jobs carrying this tag (empty = skip)")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
app_name = dbutils.widgets.get("app_name")
ops_app_name = dbutils.widgets.get("ops_app_name")
conn = dbutils.widgets.get("connection_name") or dbutils.widgets.get("app_name").replace("-", "_") + "_conn"
ops_group = dbutils.widgets.get("ops_group")
demo_flags_table = dbutils.widgets.get("demo_flags_table")
view_jobs_tag = dbutils.widgets.get("view_jobs_tag")

SERVICES: dict[str, str] = {"mcp_mulesoft": "mulesoft_*", "mcp_gcp": "gcp_*", "mcp_job_ops": "job_*"}

# COMMAND ----------
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import PermissionDenied
from databricks.sdk.service.apps import AppAccessControlRequest, AppPermissionLevel
from databricks.sdk.service.catalog import ConnectionType
from databricks.sdk.service.jobs import JobAccessControlRequest, JobPermissionLevel
from databricks.sdk.service.pipelines import PipelineAccessControlRequest, PipelinePermissionLevel

w = WorkspaceClient()
host = w.config.host.rstrip("/")
app = w.apps.get(name=app_name)
app_url = app.url.rstrip("/")

# The UC connection calls the app as the app's own service principal, which must be allowed to use the app.
w.apps.update_permissions(app_name, access_control_list=[
    AppAccessControlRequest(service_principal_name=app.service_principal_client_id, permission_level=AppPermissionLevel.CAN_USE)])

# COMMAND ----------
# 1. HTTP connection to the MCP server (M2M OAuth as the app's service principal).
if any(c.name == conn for c in w.connections.list()):
    print(f"Connection {conn} exists")
else:
    minted = w.service_principal_secrets_proxy.create(service_principal_id=app.service_principal_id)
    secret = minted.secret
    try:
        w.connections.create(name=conn, connection_type=ConnectionType.HTTP, options={
            "host": app_url, "port": "443", "base_path": "/mcp", "is_mcp_connection": "true",
            "oauth_scope": "all-apis", "token_endpoint": f"{host}/oidc/v1/token",
            "client_id": app.service_principal_client_id, "client_secret": secret,
        })
    except PermissionDenied as e:
        w.service_principal_secrets_proxy.delete(service_principal_id=app.service_principal_id, secret_id=minted.id)
        raise RuntimeError(
            "Creating the MCP connection needs CREATE CONNECTION on the metastore. Ask a metastore admin to run "
            f"`GRANT CREATE CONNECTION ON METASTORE TO `{w.current_user.me().user_name}`` (or to run this job), "
            "then re-run it.") from e
    print(f"Created connection {conn}")

# 2. One MCP service per tool group.
existing = {s.get("name") for s in (w.api_client.do("GET", "/api/2.1/unity-catalog/mcp-services",
                                                     query={"parent": f"schemas/{catalog}.{schema}"}) or {}).get("mcp_services", [])}
for service, selector in SERVICES.items():
    full = f"{catalog}.{schema}.{service}"
    config = {"source_connection": {"name": f"connections/{conn}"}, "include_tool_selectors": [selector]}
    if f"mcp-services/{full}" in existing:
        w.api_client.do("PATCH", f"/api/2.1/unity-catalog/mcp-services/{full}",
                        query={"update_mask": "config.include_tool_selectors"}, body={"config": config})
        print(f"Updated {full} → {selector}")
    else:
        w.api_client.do("POST", "/api/2.1/unity-catalog/mcp-services",
                        query={"parent": f"schemas/{catalog}.{schema}", "mcp_service_id": service}, body={"config": config})
        print(f"Created {full} → {selector}")
    w.api_client.do("PATCH", f"/api/2.1/unity-catalog/permissions/mcp_service/{full}",
                    body={"changes": [{"principal": ops_group, "add": ["EXECUTE"]}]})

# COMMAND ----------
# 3. What the app service principals need to read.
ops_app = w.apps.get(name=ops_app_name)
sp_ids = [app.service_principal_client_id, ops_app.service_principal_client_id]

if demo_flags_table:  # the mock MCP follows the demo's failure flags
    c, s, _ = demo_flags_table.split(".")
    spark.sql(f"GRANT USE CATALOG ON CATALOG `{c}` TO `{app.service_principal_client_id}`")
    spark.sql(f"GRANT USE SCHEMA ON SCHEMA `{c}`.`{s}` TO `{app.service_principal_client_id}`")
    spark.sql(f"GRANT SELECT ON TABLE {demo_flags_table} TO `{app.service_principal_client_id}`")

if view_jobs_tag:  # read-only access so error text can be shown for these jobs
    for job in w.jobs.list():
        if view_jobs_tag in ((job.settings and job.settings.tags) or {}):
            w.jobs.update_permissions(str(job.job_id), access_control_list=[
                JobAccessControlRequest(service_principal_name=sp, permission_level=JobPermissionLevel.CAN_VIEW) for sp in sp_ids])
            print(f"CAN VIEW on '{job.settings.name}' for the app service principals")
            # Pipeline tasks keep their error in the pipeline event log, which needs view on the pipeline too.
            for task in w.jobs.get(job.job_id).settings.tasks or []:
                if task.pipeline_task:
                    w.pipelines.update_permissions(task.pipeline_task.pipeline_id, access_control_list=[
                        PipelineAccessControlRequest(service_principal_name=sp, permission_level=PipelinePermissionLevel.CAN_VIEW)
                        for sp in sp_ids])

print(f"Done. In Genie One, add the MCP services {', '.join(SERVICES)} from {catalog}.{schema} to a chat (+ → Tools).")
