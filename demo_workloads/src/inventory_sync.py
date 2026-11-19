# Databricks notebook source
# MAGIC %md # Inventory Sync · load the nightly inventory file dropped by MuleSoft

# COMMAND ----------
# MAGIC %run ./_common

# COMMAND ----------
import json, random

landing = f"/Volumes/{catalog}/{schema}/landing/inventory_feed.json"
# The real MuleSoft flow drops the file; in the demo we stand in for it unless the "feed missing" flag is on.
if not flag("mulesoft_feed_missing"):
    rows = [{"store_id": s, "sku": f"SKU-{k:05d}", "on_hand": random.randint(0, 40)} for s in range(1, 401, 7) for k in range(20)]
    dbutils.fs.put(landing, "\n".join(json.dumps(r) for r in rows), overwrite=True)
else:
    dbutils.fs.rm(landing)

# Fails with PATH_NOT_FOUND when MuleSoft did not deliver.
df = spark.read.json(landing)
df.write.mode("overwrite").saveAsTable(f"{catalog}.{schema}.bronze_store_inventory")
print(f"loaded {df.count()} inventory rows")
