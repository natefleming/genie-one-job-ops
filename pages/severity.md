# Severity: what to fix first

Domain: {{domain}}

Synonyms:
- priority
- urgency
- what to fix first
- triage order

Description:
The order in which to work through failures: repeated failures and wide downstream impact first.

## Definition
Rank failures in this order:
1. **Broken repeatedly:** several consecutive failures; it won't fix itself.
2. **Wide downstream impact:** feeds dashboards, Genie agents or many other jobs (see *Lineage impact*).
3. **Data Error:** the business is probably looking at wrong or missing data.
4. **Business-critical feeds:** store sales, inventory and orders before internal or test jobs.
5. Everything else, oldest first.

A single Compute or Capacity failure that recovered on its own is low priority.

## How we measure it
`consecutive_failures` from `failing_now(hours)`; impact from `downstream_impact(job_id)`.

## Related assets
- {{catalog}}.{{schema}}.failing_now
- {{catalog}}.{{schema}}.downstream_impact

## Sources
- Genie One Job Ops project (pages/severity.md)
