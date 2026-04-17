# Correction Patterns

The accumulating catalogue of what cleaning knows to fix — and what it must not touch. Updated whenever a new garble or false-correction surfaces.

This doc is the **project-level source of truth**. Memory files (`reference_transcript_corrections.md`, `reference_nrl_slang.md`) mirror this for cross-conversation recall.

---

## Player Name Garbles

Auto-captions mishear NRL player names in predictable ways. The deterministic pre-pass fixes these against `data/players.yaml`.

| Heard | Canonical | Notes |
|-------|-----------|-------|
| _(populate as patterns surface)_ | | |

**How to add:** when cleaning surfaces a garble, add the row. If it's cross-conversational, also add to memory (`reference_transcript_corrections.md`).

---

## Team Name Garbles

| Heard | Canonical | Notes |
|-------|-----------|-------|
| _(populate as patterns surface)_ | | |

---

## Protected Terms

Slang, nicknames, and NRL-specific jargon that must **not** be "corrected" by the LLM. These feed the skill prompt as an explicit do-not-touch list.

| Term | What it means | Why LLM might over-correct |
|------|--------------|----------------------------|
| PVL | Actual NRL term — keep as-is | LLMs guess "Payroll" or "Paul" |
| _(populate as patterns surface)_ | | |

Cross-ref memory: `reference_nrl_slang.md`.

---

## Advisor/Source Name Variants

| Heard | Canonical | Notes |
|-------|-----------|-------|
| "Super Coach Playbook" | `SC Playbook` | Canonical short name in `data/sources.yaml` |
| _(populate as patterns surface)_ | | |

---

## Structural Corrections

Patterns that aren't single-word substitutions but recurring clean-up:

| Pattern | Rule |
|---------|------|
| Filler repetition ("uh... uh... uh...") | Collapse to single instance |
| Cross-speaker overlap in a single transcript line | Split into two segments; flag for speaker attribution later |
| Ad reads / sponsor breaks | Preserve but tag as non-claim segments |
| _(populate as patterns surface)_ | |

---

## How These Feed the Skill

The `/clean-transcript` skill consumes this file (or its memory mirror) as part of its context:

1. **Deterministic patterns** (player/team name garbles, structural corrections) run as Python substitutions in the pre-pass.
2. **Protected terms** appear in the skill's LLM prompt as explicit do-not-correct instructions.
3. **Advisor variants** get resolved against `data/sources.yaml` during attribution.

When you add a row here, also add to the relevant memory and/or the skill's instructions so the change actually runs. This doc is the catalogue; the skill is the execution.

---

## Related

- [cleaning.md](cleaning.md) — the workbench that uses these patterns
- [types.md](types.md) — per-source-type cleaning notes
- Memory: `reference_transcript_corrections.md`, `reference_nrl_slang.md`
- `data/players.yaml` — canonical player registry
- `data/sources.yaml` — canonical advisor/channel registry
