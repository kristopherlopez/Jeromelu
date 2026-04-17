# Agents

Jaromelu is an agent-first product. "Agent" here spans three different things:

| Kind | What | Folder |
|------|------|--------|
| **Crew** | User-facing personas with voice, persona, and presence in the show | [crew/](crew/README.md) |
| **System** | Backend workers — Temporal workflows, LLM activities, scrapers | [system/](system/README.md) |
| **Skills** | Claude Code dev-time skill agents | [skills/README.md](skills/README.md) |

## Roster at a Glance

### Crew (6)

| Member | Role |
|--------|------|
| [Jaromelu](crew/jaromelu.md) | The front man — makes the call |
| [Scout](crew/scout.md) | Intelligence gatherer |
| [Analyst](crew/analyst.md) | Cross-references claims, finds contradictions |
| [Critic](crew/critic.md) | Challenges Jaromelu before the call |
| [Bookkeeper](crew/bookkeeper.md) | The numbers — breakevens, cap space, prices |
| [Archivist](crew/archivist.md) | The long memory — patterns, history |

See also: [Crew Dynamics](crew/dynamics.md) — how they hand off, face-offs.

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

Crew agents are narrative — they are what the user sees. System agents are operational — they are what actually runs. Some map cleanly (e.g. the `FeedGenerationWorkflow` produces what the crew "says"), but they are not 1:1. Treat them as separate concerns that reference each other, not duplicates.
