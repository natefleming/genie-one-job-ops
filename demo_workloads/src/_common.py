# Databricks notebook source
# Shared helpers for the demo notebooks: widgets + failure flags.
dbutils.widgets.text("catalog", "retail_consumer_goods")
dbutils.widgets.text("schema", "job_ops")
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
fq = f"`{catalog}`.`{schema}`"


def flag(name: str) -> bool:
    """True when the chaos job has switched this failure scenario on."""
    rows = spark.sql(f"SELECT enabled FROM {fq}.demo_flags WHERE flag = '{name}'").collect()
    return bool(rows and rows[0].enabled)
