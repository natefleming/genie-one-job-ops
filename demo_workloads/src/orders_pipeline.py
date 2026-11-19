# Lakeflow pipeline: customer orders. The expectation stops the update when the order feed sends
# negative totals (turned on by the chaos job's "orders_negative_totals" flag).
from pyspark import pipelines as dp
from pyspark.sql import functions as F

SOURCE_TABLE = spark.conf.get("source_table")  # set in the pipeline configuration


@dp.materialized_view(comment="Orders as received from the order management system")
def bronze_orders():
    return spark.read.table(SOURCE_TABLE)


@dp.materialized_view(comment="Validated orders")
@dp.expect_or_fail("order_total_not_negative", "order_total >= 0")
def silver_orders():
    return spark.read.table("bronze_orders").withColumn("order_date", F.to_date("order_ts"))


@dp.materialized_view(comment="Daily orders by channel")
def gold_daily_orders():
    return (spark.read.table("silver_orders").groupBy("order_date", "channel")
            .agg(F.count("*").alias("orders"), F.sum("order_total").alias("revenue")))
