---
tags: [area/agents, subarea/skills]
---

# Claude Code Skills

Dev-time agents invoked via `/skill-name` inside Claude Code. These are not production workers — they support the development workflow (extraction experimentation, skill evaluation, transcript handling).

| Skill | Purpose |
|-------|---------|
| [Transcript Pipeline](transcript-pipeline.md) | Hierarchical multi-agent claim extraction from YouTube transcripts |
| [Skill Creator](skill-creator.md) | Skill evaluation, comparison, and improvement |

## Related skills (docs live in the skills themselves, not here)

- `/clean-transcript` — Phase 1 of transcript pipeline (deterministic NLP)
- `/process-transcript` — flat single-pass extraction (simpler alternative)
- `/verify-claims` — Phase 4 of transcript pipeline (standalone)
- `/fetch-transcripts` — download raw transcripts from S3
- `/upload-transcript` — persist claims to DB
