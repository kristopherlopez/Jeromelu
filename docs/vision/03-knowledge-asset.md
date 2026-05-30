---
tags: [area/architecture]
---

# Knowledge Asset

> Last reviewed: 2026-05-23.

Behind the show is an asset that outlasts any single week of it. Every time the crew runs, it isn't only producing Remarks — it's adding to a permanent, growing, speaker-attributed record of everything said and predicted about the NRL, graded against what actually happened. That record is the knowledge asset.

The show is what you watch. The asset is what makes the show keep getting sharper — and what opens doors the show alone never could.

---

## What's In It

The asset is a structured projection of the entire NRL information ecosystem. Two streams feed it:

- **The factual spine** — structured data from nrl.com and SuperCoach: matches, lineups, per-player stats, ladders, injuries, scoring breakdowns. Decades deep. This is what claims get graded *against*.
- **The opinion layer** — unstructured commentary from the YouTube podcast and panel ecosystem, plus editorial notes: transcribed, speaker-diarised, and mined for **claims**. This is what the crew listens to so the audience doesn't have to.

Every claim that lands in the asset is **speaker-attributed** (who said it), **time-stamped** (when), **typed** (what kind of call), and **linked to the entities it's about** (which players, teams, rounds). The claims that are *predictions* are tracked through a lifecycle — open, locked, resolved — and graded when reality arrives.

The capture model is deliberately patient: external sources (L1) are archived durably and idempotently in S3 (L2), projected into a queryable database (L3), and surfaced in the app (L4). The archive is forensic; the database is fully re-derivable from it. **Capture everything now, compose richer later** — today's text-mined claim is tomorrow's input to a feature that doesn't exist yet. Full model in [data-lineage.md](../architecture/data-lineage.md).

---

## Why It Compounds

The asset's value is mostly a function of **time**, not spend.

Each round adds three things at once: new claims, new predictions, and — the part that can't be rushed — **resolved outcomes**. A graded history of who-called-what-and-was-it-right only accumulates by living through the rounds. You can backfill a transcript archive; you can't backfill the discipline of having captured, attributed, predicted, and graded *as it happened*, week after week, in public.

That's the compounding loop:

> ingest → attribute → predict → grade → remember → (sharper next time)

A pile of transcripts is inert. The same transcripts, run through that loop every week, become a living record that gets more valuable the longer it runs. The work is the asset.

---

## What It Powers

**1. It makes Jaromelu sharper.** The asset is his memory. Every past call, every claim, every resolved outcome is retrievable — so he reasons over the whole ecosystem and his own history, not a single week's feed. It's why he can say *"I called Cleary overrated three weeks ago, still do"* and mean it. The longer it runs, the harder his analysis is to dismiss. It's also the engine behind the show's **moving number**: when the asset updates — a late injury, a fresh take — his live read shifts within minutes. The asset is *why* a call can move in real time.

**2. It earns his credibility — the Alignment Index.** Because every prediction is graded against reality, the asset can score *every* commentator it ingests, not just Jaromelu — sliced by what each is actually good at (tipping, form reads, match narratives, injuries). Jaromelu is graded on the same rubric, no softer curve. His own takes run passively from day one; they get foregrounded once they *demonstrably* rival the human pundits'. The Index answers a question no other NRL property answers cleanly: **"who actually reads the game well?"** Detail in [the Ledger](../pages/ledger/overview.md).

**3. It's a discovery surface.** Speaker attribution means the asset doesn't just hold *what* was said — it knows *who* said it and how often they were right. A commentator with sharp, well-graded, contrarian takes becomes worth following. Jaromelu turns into a way to *find* the voices in the ecosystem worth your time — not just a verdict on them.

**4. It becomes visible — and auditable — as the Wiki.** The Archivist renders the asset as per-entity pages (players, teams, commentators, rounds), so the knowledge stops being a hidden database and becomes something you can *stand inside*. That visibility cuts two ways: the audience sees the lineage and trusts it; the creator sees what's wrong and refines it. Audit and trust are the same transparency from two sides — and nothing the crew learns goes missing. Detail in [the Wiki](../pages/wiki/overview.md).

**5. It unlocks new directions.** All of these sit on the same captured data, and are deliberately *later*, not V1:

- **Who's good at what** — specialisation profiles per commentator (form reads vs scoreline vs finals vs recovery timelines).
- **Betting signal research** — how graded track records intersect with markets. *(Heavily regulated; an adjacency to research carefully, not a casual feature.)*
- **SuperCoach** — how the same claims and outcomes inform selections, when that extension ships.

---

## What It Costs

Honest about the hard parts, because they're where this gets won or lost:

- **Speaker attribution is the load-bearing dependency.** Knowing *who* said something — across diarisation, voice, and face — is what makes the whole asset more than a bag of quotes. It's handled by a dedicated speaker-ID service; the end state is an API that returns a speaker-attributed transcript the crew can mine. Until that's solid, the opinion layer is thinner than the vision.
- **Grading is only as good as the outcome is clean.** A prediction is gradeable only when the outcome is unambiguous. Fuzzy claims need an honest rubric — right, wrong, or partial — never "well, technically." Soft-grading would rot the Index's authority.
- **Extraction quality gates everything.** Garbage claims poison the ledger. Extraction is multi-pass and verified before anything is trusted as load-bearing.
- **V1 reality.** The factual spine and SuperCoach editorial claims are shipped and queryable today. Transcript-derived claims *at scale* — the opinion layer that makes the Alignment Index sing — are the build-out still ahead.

---

## Not NRL-Specific

The asset's *shape* is domain-agnostic: ingest a domain's sources, attribute claims to speakers, track predictions, grade them against reality, remember. The hard parts — attribution, grading, extraction — are general, not NRL-flavoured. Swap the NRL feeds for another sport's, or another topic's, and the same machinery produces the same compounding asset.

NRL is where it gets proven (see [01 — Why NRL](01-venture-thesis.md)). The asset is why "done well, this extends to any sport and likely any topic" is more than a slogan — the thing that would have to be rebuilt per domain is just the *feeds*, not the machine.

---

## Related

- [Venture Thesis](01-venture-thesis.md) — "What Compounds" is the seed this doc grows from
- [The Show](02-the-show.md) — the asset, made watchable; the crew that builds it
- [The Machine](04-the-machine.md) — this asset's engineering decomposition into reusable modules
- [Data Lineage](../architecture/data-lineage.md) — the concrete L1→L4 model and the operations trinity
- [The Ledger](../pages/ledger/overview.md) — the Alignment Index in practice
- [The Wiki](../pages/wiki/overview.md) — the asset made visible and auditable
- [Miner](../agents/crew/miner/README.md) — the ingestion pipelines that feed the asset

