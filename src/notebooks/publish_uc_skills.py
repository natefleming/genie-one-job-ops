# Databricks notebook source
# MAGIC %md
# MAGIC # Job Ops — publish the Genie One skills to Unity Catalog
# MAGIC Each folder under `skills/` becomes a UC Skill `<catalog>.<schema>.<skill-name>`.
# MAGIC `{{catalog}}` / `{{schema}}` placeholders in the skill files are filled in here, so the same
# MAGIC skills work in any workspace. The ops group gets `READ VOLUME` (the privilege that shares a
# MAGIC skill); users then install them in Genie One from **Customizations → Skills**.
# MAGIC
# MAGIC Requires the previews **Enhanced Unity AI Gateway** (account) and **Unity Gateway skills in
# MAGIC Genie** (workspace). Re-running updates the skill contents in place.

# COMMAND ----------
dbutils.widgets.text("catalog", "retail_consumer_goods")
dbutils.widgets.text("schema", "job_ops")
dbutils.widgets.text("ops_group", "account users")
dbutils.widgets.text("bundle_root", "")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
ops_group = dbutils.widgets.get("ops_group")
bundle_root = dbutils.widgets.get("bundle_root")

# COMMAND ----------
import io
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import ResourceConflict

w = WorkspaceClient()
skills_root = Path(bundle_root) / "skills"


def render(data: bytes, path: Path) -> bytes:
    """Fill catalog/schema placeholders in text files; copy everything else byte for byte."""
    if path.suffix not in {".md", ".sql", ".py", ".txt", ".yaml", ".yml", ".json"}:
        return data
    return data.decode().replace("{{catalog}}", catalog).replace("{{schema}}", schema).encode()


def publish(skill_dir: Path) -> None:
    name = skill_dir.name
    full_name = f"{catalog}.{schema}.{name}"
    try:
        w.api_client.do("POST", "/api/2.1/unity-catalog/skills",
                        query={"parent": f"schemas/{catalog}.{schema}", "skill_id": name}, body={})
        print(f"created  {full_name}")
    except ResourceConflict:  # 409 ALREADY_EXISTS
        print(f"updating {full_name}")
    for f in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
        target = f"/Skills/{catalog}/{schema}/{name}/{f.relative_to(skill_dir).as_posix()}"
        w.files.upload(target, io.BytesIO(render(f.read_bytes(), f)), overwrite=True)
    w.api_client.do("POST", f"/api/2.1/unity-catalog/skills/{full_name}/finalize")
    w.api_client.do("PATCH", f"/api/2.1/unity-catalog/permissions/skill/{full_name}",
                    body={"changes": [{"principal": ops_group, "add": ["READ_VOLUME"]}]})


skill_dirs = sorted(d for d in skills_root.iterdir() if (d / "SKILL.md").exists())
for d in skill_dirs:
    publish(d)
print(f"Published {len(skill_dirs)} skills to {catalog}.{schema}; {ops_group} has READ VOLUME.")
