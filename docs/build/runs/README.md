# Build run reports

The durable, human-readable record of completed build work — one report per plan/initiative ("a run"), written as a status update: what each work order delivered, how it was verified, the decisions/deviations made, what's outstanding, and lessons learned.

This folder is the system of record for *what happened*. `PLAN.md` holds only active/future goal plans; `WORK_ORDERS.md` holds only live/future dispatchable work; `THREADS.md` holds only live coordination state. All three get reused. Git history is the immutable log. See the run-report ritual in [META.md](../META.md).

Newest first.

| Date | Run | Status |
|---|---|---|
| 2026-05-30 | [Scout roadmap completion](./2026-05-30-scout-roadmap-completion.md) | In progress |
| 2026-05-28 | [Engineering quality hardening — Tier 1](./2026-05-28-eng-quality-tier-1.md) | 🟢 Shipped (6/6; CI dry-run + path-filter SHA-fidelity check deferred to operator) |
| 2026-05-29 | [Scout Phase 5 — Historical backfill + standard-data-model conformance](./2026-05-28-scout-phase-5-historical-backfill.md) | 🟢 Shipped (10/10; 3 spec-side threshold over-estimates — actual data correct) |
| 2026-05-28 | [Scout Phase 4.5 — nrl.com stats + players roster (D8 harden, schedule, seed)](./2026-05-28-scout-phase-4-5-stats-players-roster.md) | 🟢 Shipped (cron first-fire + extractor-scheduling deferred) |
| 2026-05-28 | [Scout Phase 4 — nrl.com casualty ward + ladder + retire worker-scraper](./2026-05-28-scout-phase-4-casualty-ladder.md) | 🟢 Shipped (cron first-fire + extractor-scheduling deferred) |
| 2026-05-27 | [Change-only storage for video_metrics + channel_metrics](./2026-05-27-change-only-metrics-storage.md) | 🟢 Shipped (prod 641 MB → 171 MB) |
| 2026-05-24 | [Scout Phase 3.5 — nrl.com match-centre DB extractors](./2026-05-24-scout-phase-3.5-nrlcom-extractors.md) | 🟢 Shipped (runtime follow-up noted) |
| 2026-05-24 | [Scout Phase 3 — nrl.com draw + match-centre ingest hardening](./2026-05-24-scout-phase-3-nrlcom-ingest.md) | 🟢 Shipped (cron first-fire pending) |
| 2026-05-24 | [Scout Phase 2.5 closure — SC teams + settings](./2026-05-24-scout-phase-2.5-closure.md) | 🟢 Shipped |
