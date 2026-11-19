---
name: ops-daily-briefing
description: A short morning briefing on data platform health, written to read well on a phone - what failed overnight, what is still broken, what is affected and what to do first. Use for the daily ops briefing, a scheduled morning summary, or when someone asks "give me the briefing" or "how did last night go".
---

# Daily ops briefing

Short enough to read on a phone in 30 seconds.

## Steps

1. Overnight results:
   ```sql
   SELECT MEASURE(total_runs) AS runs, MEASURE(failed_runs) AS failed, ROUND(MEASURE(failure_rate) * 100, 1) AS failure_pct
   FROM {{catalog}}.{{schema}}.mv_job_runs WHERE run_hour >= current_timestamp() - INTERVAL 12 HOURS
   ```
2. Still broken: `SELECT * FROM {{catalog}}.{{schema}}.failing_now(12)`
3. Stale tables: `SELECT table_name FROM {{catalog}}.{{schema}}.table_freshness WHERE is_stale`
4. For the single most urgent failure, run `downstream_impact` to say what it affects.

## Format

```
Good morning — data platform briefing for <date>
✅ <runs> runs overnight, <failed> failed (<failure_pct>%)
🔴 Still broken: <job> — <plain reason> (failed <n>x) → <run link>
⚠️ Not updating: <table> (no data for <h> hours)
👉 First thing to do: <one action>
```

No tables or long paragraphs. If everything is healthy, say so in one line.
