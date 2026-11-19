# Databricks notebook source
# MAGIC %md # Nightly Sales Load · clean sales (silver)

# COMMAND ----------
# MAGIC %run ./_common

# COMMAND ----------
# ANSI casting: a non-numeric amount fails the build instead of silently becoming NULL.
spark.sql(f"""CREATE OR REPLACE TABLE {fq}.silver_sales AS
SELECT b.txn_id, b.store_id, s.region, b.sale_date, CAST(b.amount_raw AS DECIMAL(12,2)) AS amount, b.units
FROM {fq}.bronze_pos_sales b JOIN {fq}.stores s USING (store_id)""")
