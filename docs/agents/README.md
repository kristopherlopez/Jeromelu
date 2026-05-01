---
tags: [area/agents]
---

# Agents

Jaromelu is an agent-first product. "Agent" here spans three different things:

| Kind | What | Folder |
|------|------|--------|
| **Crew** | Internal reasoning architecture composing Jaromelu — the only on-screen character | [crew/](crew/README.md) |
| **System** | Backend workers — Temporal workflows, LLM activities, scrapers | [system/](system/README.md) |
| **Skills** | Claude Code dev-time skill agents | [skills/README.md](skills/README.md) |

## Roster at a Glance

### Crew

Internal reasoning architecture for Jaromelu — not separate visible characters. Users only see Jaromelu; the "crew" is how he thinks (research, analysis, skepticism, math, memory).

| Internal function | What it does |
|---|---|
| [Jaromelu](crew/jaromelu.md) | The on-screen character — integrates everything below |
| [Scout](crew/scout.md) | Research / intelligence gathering mode |
| [Analyst](crew/analyst.md) | Cross-reference / contradiction-detection mode |
| [Critic](crew/critic.md) | Self-doubt / pre-call challenge mode |
| [Bookkeeper](crew/bookkeeper.md) | Math / numbers mode |
| [Archivist](crew/archivist.md) | Long-memory / pattern-matching mode |

See also: [Crew Dynamics](crew/dynamics.md) — internal reasoning patterns (handoffs are engineering flow, not on-screen interactions).

### System

| Worker / Agent | Status | Purpose |
|----------------|--------|---------|
| [Orchestrator](system/orchestrator.md) | Skeleton | Central workflow hub (intended) |
| [Ingestion](system/ingestion.md) | Live | YouTube discovery, transcripts, indexing |
| [Publishing](system/publishing.md) | Live | Feed events + KB generation (incl. LLM activities) |
| [Scraper](system/scraper.md) | Partial | SuperCoach prices/scores/teamlists |
| [Extraction](system/extraction.md) | Not yet built | Entity/claim extraction |
| [Decision](system/decision.md) | Not yet built | Scoring, ranking, strategy |

### Skills

| Skill | Purpose |
|-------|---------|
| [Transcript Pipeline](skills/transcript-pipeline.md) | Hierarchical multi-agent claim extraction |
| [Skill Creator](skills/skill-creator.md) | Skill evaluation and improvement |

---

## How crew vs system relate

Crew is **how Jaromelu thinks** — internal reasoning architecture (research, analysis, skepticism, math, memory). System is **what actually runs** — Temporal workflows, LLM activities, scrapers. They map but are not 1:1: a single internal mode (e.g. Scout = research) can span multiple system workers (ingestion + source discovery), and conversely the publishing agent wraps every internal-mode output in Jaromelu's single on-screen voice. Treat them as separate concerns that reference each other, not duplicates.
