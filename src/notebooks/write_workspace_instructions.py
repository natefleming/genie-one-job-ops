# Databricks notebook source
# MAGIC %md
# MAGIC # Job Ops — Genie One workspace instructions
# MAGIC Genie One reads `/Workspace/.genie_workspace_instructions.md` for every user in the workspace.
# MAGIC This adds (or refreshes) a Job Ops block that tells Genie One where job-health answers come
# MAGIC from — no per-user setup. Anything else in the file is left untouched. Needs workspace admin.

# COMMAND ----------
dbutils.widgets.text("schema_only_scope", "false", "true = skip: this writes outside the schema")
if dbutils.widgets.get("schema_only_scope").lower() == "true":
    dbutils.notebook.exit("skipped (schema_only_scope)")

dbutils.widgets.text("catalog", "retail_consumer_goods")
dbutils.widgets.text("schema", "job_ops")
dbutils.widgets.text("bundle_root", "")
dbutils.widgets.text("instructions_path", "/Workspace/.genie_workspace_instructions.md")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
path = dbutils.widgets.get("instructions_path")

# COMMAND ----------
import io
import re
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from databricks.sdk.service.workspace import ImportFormat

w = WorkspaceClient()
BEGIN, END = "<!-- BEGIN job-ops (managed by bundle) -->", "<!-- END job-ops -->"

block = (Path(dbutils.widgets.get("bundle_root")) / "src" / "genie_workspace_instructions.md").read_text()
block = block.replace("{{catalog}}", catalog).replace("{{schema}}", schema)

try:
    current = w.workspace.download(path).read().decode()
except NotFound:
    current = ""

managed = f"{BEGIN}\n{block.strip()}\n{END}"
if BEGIN in current:
    updated = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: managed, current, flags=re.S)
else:
    updated = (current.rstrip() + "\n\n" if current.strip() else "") + managed + "\n"

w.workspace.upload(path, io.BytesIO(updated.encode()), format=ImportFormat.AUTO, overwrite=True)
print(updated)
