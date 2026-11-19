# Databricks notebook source
# MAGIC %md
# MAGIC # Job Ops — create the Genie One domain
# MAGIC A domain groups the assets and Pages for one subject so Genie One knows where to look.
# MAGIC This creates the **Data Platform Operations** domain (backed by a governed tag), then tags the
# MAGIC Job Ops Genie Agent, the Ops app and the metric views into it.
# MAGIC Pages (the plain-English concept definitions in `pages/`) are added in the UI — see
# MAGIC `docs/PAGES.md`; there is no public Pages API yet.

# COMMAND ----------
dbutils.widgets.text("schema_only_scope", "false", "true = skip: this writes outside the schema")
if dbutils.widgets.get("schema_only_scope").lower() == "true":
    dbutils.notebook.exit("skipped (schema_only_scope)")

dbutils.widgets.text("catalog", "retail_consumer_goods")
dbutils.widgets.text("schema", "job_ops")
dbutils.widgets.text("domain_tag_key", "Data Platform Operations")
dbutils.widgets.text("domain_name", "Data Platform Operations")
dbutils.widgets.text("ops_app_name", "job-ops")
dbutils.widgets.text("space_id", "")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
tag_key = dbutils.widgets.get("domain_tag_key")
domain_name = dbutils.widgets.get("domain_name")
ops_app_name = dbutils.widgets.get("ops_app_name")
space_id = dbutils.widgets.get("space_id")

# COMMAND ----------
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import DatabricksError, NotFound

w = WorkspaceClient()

# 1. Governed tag behind the domain.
try:
    w.api_client.do("GET", f"/api/2.1/tag-policies/{tag_key}")
    print(f"Tag policy '{tag_key}' exists")
except NotFound:
    w.api_client.do("POST", "/api/2.1/tag-policies",
                    body={"tag_key": tag_key, "description": "Genie One domain: job and pipeline operations"})
    print(f"Created tag policy '{tag_key}'")

# 2. The domain itself (one domain per tag key).
domain = {
    "tag_key": tag_key,
    "name": domain_name,
    "subtitle": "Job and pipeline health",
    "description": ("Is the data platform healthy? Which jobs and pipelines failed, why, who is affected "
                    "downstream, and how to fix it. Answers come from the Job Ops Genie Agent, metric views "
                    "over Databricks system tables, and Genie ZeroOps for deep root cause."),
    "draft": False,
    "icon": {"name": "CHART_PIE_SLICE", "color": "#1B5162"},
}
def list_domains() -> list[dict]:
    domains, token = [], None
    while True:
        page = w.api_client.do("GET", "/api/2.0/domains", query={"page_size": 100, **({"page_token": token} if token else {})})
        domains += page.get("domains", [])
        token = page.get("next_page_token")
        if not token:
            return domains


existing = [d for d in list_domains() if d.get("tag_key") == tag_key]
if existing:
    domain_id = existing[0]["domain_id"]
    w.api_client.do("PATCH", f"/api/2.0/domains/{domain_id}",
                    query={"update_mask": "subtitle,description,icon"}, body=domain)
else:
    domain_id = w.api_client.do("POST", "/api/2.0/domains", body=domain)["domain_id"]
print(f"Domain {domain_name}: {domain_id}")

# COMMAND ----------
# 3. Put the assets in the domain by tagging them.
def tag_workspace_entity(entity_type: str, entity_id: str) -> None:
    try:
        w.api_client.do("POST", "/api/2.0/entity-tag-assignments",
                        body={"entity_type": entity_type, "entity_id": entity_id, "tag_key": tag_key})
        print(f"tagged {entity_type}/{entity_id}")
    except DatabricksError as e:
        print(f"{entity_type}/{entity_id}: {e}")  # already tagged, or app not created yet


if space_id:
    tag_workspace_entity("geniespaces", space_id)
tag_workspace_entity("apps", ops_app_name)

for view in ["mv_job_runs", "mv_task_runs", "mv_pipeline_updates", "mv_table_freshness"]:
    spark.sql(f"ALTER VIEW `{catalog}`.`{schema}`.`{view}` SET TAGS ('{tag_key}')")
    print(f"tagged {catalog}.{schema}.{view}")
