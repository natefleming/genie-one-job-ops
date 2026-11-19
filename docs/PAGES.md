# Uploading the Genie One Pages

Pages are governed definitions of business concepts. Genie One uses them as the official meaning of a term and cites
them. Each Page belongs to one domain, so run the setup job first (it creates the domain).

There is no public Pages API yet, so Pages are uploaded in the UI. (As of 2026-10-20 a Pages and Domains API with full
create/update/publish is in internal dogfood and awaiting public-API approval, expected around the end of October. When it
lands, the setup job can publish these files the way it publishes the skills.) The files in `pages/` are templates; render them for the
workspace first:

```bash
./scripts/render_pages.sh <catalog.schema> [domain]
# FEVM:      ./scripts/render_pages.sh retail_consumer_goods.job_ops "Operational Resilience"
# Customer:  ./scripts/render_pages.sh <catalog>.<schema>            # domain defaults to "Data Platform Operations"
```

This writes `build/pages/<page>.md` (one per page) and `build/pages/all-pages.md` (all nine).

Each file uses the layout Genie Code reads best: title, `Domain:`, `Synonyms:`, `Description:`, the page body,
`Related assets` (the metric views and functions that answer it) and `Sources`.

## Option A — bulk import (recommended)

1. **Discover → Pages → Create page → Genie Code → Bulk import pages.**
2. Name the target domain (FEVM: *Operational Resilience*; customer: *Data Platform Operations*).
3. Attach `build/pages/all-pages.md` (or the nine individual files).
4. Review what Genie Code proposes: merge duplicates, check the synonyms and related assets, then create them as drafts.
5. Open each draft and **Publish**.

## Option B — one at a time

**Discover → Pages → Create page**, pick the domain, and copy each file's fields in: the `#` heading is the page name,
`Synonyms` and `Description` go in their fields, the rest is the body; add the listed related assets. **Publish.**

## The nine pages

| File | Page |
|---|---|
| `job-failure.md` | Job failure |
| `failure-category.md` | Failure category (data error vs. compute error) |
| `nested-task.md` | Nested task (for-each) |
| `lineage-impact.md` | Lineage impact (who is affected) |
| `receiving-no-data.md` | Receiving no data (stale table) |
| `governed-table.md` | Governed vs. ungoverned table |
| `genie-zeroops.md` | Genie ZeroOps |
| `repair-vs-rerun.md` | Repair run vs. re-run |
| `severity.md` | Severity: what to fix first |

Notes: Pages are Beta. Only Genie One reads them (a Genie Agent used directly does not), so the same definitions also
live in the Job Ops agent's instructions. Page text is stored as plain text and may be replicated globally, so keep
customer data out of it (these files contain none).
