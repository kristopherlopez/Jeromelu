---
tags: [area/todo, status/in-progress]
---

# Presenter Scout — Auto-discover the regular presenters of a channel

> **Status:** Plan accepted 2026-05-05. Migration + agent + review surface staged for incremental ship.

**Phase:** Scout extension / identification feeder
**Priority:** Compounds with speaker-identification — confirmed presenters become strong priors for the voice/face fusion matchers, so each new channel goes from "cold start" to "first turn auto-resolved" much faster.
**Service:** new `services/api/app/scout/presenters.py` (+ CLI), new admin panel.

## Problem

Today, when we onboard a new YouTube channel or podcast, the only people the system *knows* are NRL players (seeded from SuperCoach) and whichever hosts an operator has manually voice/face-enrolled. The "this is Denan Kemp" loop only starts after someone a) figures out who the regulars are, b) creates `people` rows for them, c) enrolls voice/face spans.

Step (a) is a Google search. Step (b) is two SQL inserts. Step (c) is a real cost. The first two are exactly what an agent with web tools should do for us.

## Goals

- Given a `channel_id` (or a `source_id`, resolved to its channel), produce a ranked list of likely regular presenters with cited evidence.
- Persist candidates for human review — never write straight to `people`.
- One reviewer click promotes a candidate into:
  - a `people` row (or links to an existing one), and
  - a typed `source_presenters` association (role = host / co-host / regular / frequent-guest).
- The same surface is the backstop when the LLM hallucinates a presenter — reject is one click, no DB cleanup needed.

## Non-goals

- Building a full Person admin CRUD. We already have `people`; this just adds a link table and a candidates inbox.
- Voice / face enrollment. That's downstream — once a Person exists, the existing `make enroll-voice` / `make enroll-face` flows take over.
- Fuzzy alias merging. If the agent surfaces "Denan Kemp" and a Person already exists with that canonical_name, we expose `existing_person_id` so the reviewer can link instead of duplicate. Anything more elaborate (alias edit-distance, etc.) is out of scope.

## Architecture (target)

```
channel_id ──► presenter_scout (agent loop)
                   │
                   ├─ web_search (Anthropic-hosted)
                   ├─ web_fetch  (Anthropic-hosted)
                   └─ persist_presenter_candidate (custom tool)
                                       │
                                       ▼
                       scout_presenter_candidates (status='pending')
                                       │
                                  human review
                                       │
                                       ▼
                        people (insert OR link existing)
                                       │
                                       ▼
                       source_presenters (channel_id, person_id, role, ...)
```

The agent runs entirely in the API process, same shape as the existing Scout. `agent_audit` tracks turns / tokens / cost / S3 forensics. New `agent_id = 'presenter_scout'` so the budget/observability buckets stay clean.

## Data model

Two new tables, plus one CHECK extension. (Migration `052_source_presenters.sql`.)

### `scout_presenter_candidates` — staging inbox

```sql
CREATE TABLE scout_presenter_candidates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id          UUID NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    name                TEXT NOT NULL,                        -- "Denan Kemp"
    role                TEXT NOT NULL,                        -- 'host'|'co-host'|'regular'|'frequent-guest'
    evidence_json       JSONB NOT NULL DEFAULT '[]',          -- [{url, snippet}], at least 1 required
    llm_confidence      FLOAT,                                -- 0.0–1.0, agent's own score
    notes               TEXT,                                 -- free-form agent commentary
    existing_person_id  UUID REFERENCES people(person_id),    -- agent-surfaced candidate match (best-effort)

    status              TEXT NOT NULL DEFAULT 'pending',      -- 'pending'|'confirmed'|'rejected'
    reviewed_at         TIMESTAMPTZ,
    reviewed_by         TEXT,
    confirmed_person_id UUID REFERENCES people(person_id),    -- set on confirm

    run_id              TEXT,                                 -- agent_runs.run_id
    discovered_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_scout_pres_role
        CHECK (role IN ('host','co-host','regular','frequent-guest')),
    CONSTRAINT ck_scout_pres_status
        CHECK (status IN ('pending','confirmed','rejected'))
);

CREATE INDEX idx_scout_pres_channel_status
    ON scout_presenter_candidates (channel_id, status);

CREATE UNIQUE INDEX uq_scout_pres_channel_name_pending
    ON scout_presenter_candidates (channel_id, lower(name))
    WHERE status = 'pending';
```

The partial unique index on `(channel_id, lower(name)) WHERE status='pending'` makes re-running the agent idempotent: a second run for the same channel won't double-file a still-pending candidate, but it *can* re-surface a name that was previously rejected (sometimes the rejection was wrong, or the role changed).

### `source_presenters` — confirmed association

```sql
CREATE TABLE source_presenters (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id    UUID NOT NULL REFERENCES channels(channel_id) ON DELETE CASCADE,
    person_id     UUID NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
    role          TEXT NOT NULL,
    is_regular    BOOLEAN NOT NULL DEFAULT TRUE,
    since_ts      TIMESTAMPTZ,                                -- when did they join, if known
    confirmed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_by  TEXT,
    candidate_id  UUID REFERENCES scout_presenter_candidates(id),

    CONSTRAINT ck_src_pres_role
        CHECK (role IN ('host','co-host','regular','frequent-guest')),
    CONSTRAINT uq_src_pres_channel_person UNIQUE (channel_id, person_id)
);

CREATE INDEX idx_src_pres_person ON source_presenters (person_id);
```

Anchored at `channel_id`, not `source_id` — presenters are a property of the show, not the episode. (A guest on one episode is *not* a presenter; it's a `frequent-guest` role applied to the show or it stays a one-off.)

### `agent_runs.agent_id` CHECK extension

Existing: `('scout', 'scribe', 'analyst', 'stats', 'fixtures')`. Add `'presenter_scout'`.

## Agent shape

`services/api/app/scout/presenters.py` — mirrors `loop.py` with a tighter tool palette and a per-channel brief.

**Tools:**
- `web_search` (Anthropic-hosted, capped 3/run)
- `web_fetch` (Anthropic-hosted, capped 3/run)
- `lookup_existing_people` (custom) — fuzzy lookup against `people.canonical_name` + aliases, returns up to 5 matches. Lets the agent flag `existing_person_id` for likely dupes.
- `persist_presenter_candidate` (custom) — required: `channel_id`, `name`, `role`, `evidence` (≥1 `{url, snippet}`), `llm_confidence`. Optional: `existing_person_id`, `notes`.

**Brief seed:** the channel name, URL, description, platform — plus the list of presenters already confirmed for this channel, so the agent doesn't re-file them.

**Bounds:** standard `AgentBounds`, but tighter — `max_turns=8`, `max_tool_calls=20`, `max_budget_usd=0.30`. Per-channel research is a small task; a runaway loop is a bug.

**Stop conditions:** the agent should file 1–6 candidates and stop. Zero filed = failure note in run summary. More than 6 = it's confusing guests with regulars; the prompt forbids it.

## API surface

`services/api/app/routers/presenters.py`:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/admin/presenters/scout/{channel_id}` | Trigger a run for one channel. Sync — returns the run summary. |
| `GET`  | `/api/admin/presenters/candidates?channel_id=…&status=…` | List candidates. |
| `POST` | `/api/admin/presenters/candidates/{id}/confirm` | Body: `{ existing_person_id?: uuid }`. If supplied, links to that Person. Otherwise, creates a new `people` row from `name`, then writes `source_presenters`. |
| `POST` | `/api/admin/presenters/candidates/{id}/reject` | Body: `{ note?: string }`. Sets status. |
| `GET`  | `/api/admin/presenters/by-channel/{channel_id}` | Confirmed + pending side-by-side. |

Mounted under the existing admin auth scope (whatever `routers/sources.py` and friends use).

## Admin UI

New tab on the existing admin client: **"Presenters"**. Mirrors the ChannelCoveragePanel layout.

- Channel picker (top) — defaults to the most-recently-onboarded channel.
- "Run Presenter Scout" button — triggers `POST /api/admin/presenters/scout/{id}`, streams nothing yet (sync API; spinner while it runs).
- Two columns:
  - **Pending candidates** — name, role, confidence, evidence URLs (clickable). Buttons: `Confirm` (opens dropdown to pick existing Person OR confirm-as-new), `Reject`.
  - **Confirmed presenters** — name, role, since, link to Person detail (future — for now just `person_id` as text).

No streaming UI in v1. The agent run is fast (~30s); a spinner is fine.

## Phasing

### Phase 1 — Schema + agent + CLI (this branch)

1. Migration `052_source_presenters.sql` (the two tables + CHECK extension).
2. SQLAlchemy models + re-exports.
3. `presenters.py` agent loop (copy `loop.py`, swap prompt + tools).
4. `presenters_cli.py` + `make scout-presenters CHANNEL_ID=…`.
5. End-to-end test on one channel (the "Bloke In A Bar" Apple/Spotify entry once it's onboarded as a `channels` row, or a YouTube channel like `bloke.shop`).

### Phase 2 — Review API + admin UI

6. FastAPI routes for list / confirm / reject / trigger.
7. React panel on the admin tab.

### Phase 3 — Compound with identification

8. After confirm, expose `(channel_id, person_id)` to the visual_id / voice_id matchers as a strong prior. (This is "if the source's channel has 3 confirmed presenters and one of them face-matches at 0.7, that's enough" — softens the threshold for confirmed roster.)
9. *(Stretch)* Auto-trigger a Presenter Scout run as the last step of `make collect-audio` for any new source whose channel has zero confirmed presenters. Background — never blocks ingestion.

## Open decisions

1. **Anchor at channel or source?** — Channel. (Decided. Episode-level guest tracking is a separate concern; if it ever becomes interesting, add a `source_guests` table without disturbing this one.)
2. **Auto-create the Person on confirm, or force-pick-or-create?** — Auto-create when no `existing_person_id` is supplied; the Person row is cheap and trivially mergeable later. Forcing the reviewer to dedupe at confirm time slows the loop without payoff.
3. **Is `source_id`-as-input supported?** — Yes, as a CLI/API convenience: resolve to `channel_id` server-side. The DB only knows about channels.
4. **Should rejected candidates be re-surfaceable on a re-run?** — Yes. The partial unique index only covers `status='pending'`. A rejected name can re-surface; the reviewer rejects again or changes their mind. Cheap.

## Risks

- **Hallucinated names.** The agent will sometimes invent presenters who don't exist. Mitigation: require ≥1 `{url, snippet}` evidence per candidate; the snippet must contain the name. Reviewer rejects fabrications; no schema damage because it's all staged.
- **"Guests vs regulars" judgment.** Web sources are inconsistent. Mitigation: `role` is one of four typed values — the agent picks; the reviewer corrects on confirm. Don't try to be clever in v1.
- **Person duplication.** Two confirmations of "Denan Kemp" create two `people` rows if the first reviewer didn't pick `existing_person_id`. Mitigation: `lookup_existing_people` tool flags likely dupes during the run; reviewer sees the hint. Acceptable risk in v1; merge tool can land later if needed.

## Documentation Updates

- **NEW `docs/agents/system/presenter-scout.md`** — surface doc: tools, prompt, bounds, hand-off contract (candidate → Person + source_presenters), running, backlog. Mirrors `transcription.md` shape.
- **`docs/agents/crew/analyst.md`** — note that confirmed `source_presenters` rows are surfaced to the visual_id / voice_id matchers as priors (after Phase 3).
- **`docs/agents/system/README.md`** — add Presenter Scout to the agent registry.
- **`docs/operations/data-catalogue.md`** — document `scout_presenter_candidates` and `source_presenters`.
- **`README.md`** — add `make scout-presenters` to the dev cheatsheet.
- **`docs/todo/speaker-identification.md`** — cross-link Phase 5 (cross-modal compounding) with this plan: confirmed presenters are the natural starting roster for face/voice priors.

## Success criteria

- Running `make scout-presenters CHANNEL_ID=<bloke-in-a-bar-channel-id>` writes 3–5 pending candidates (Denan Kemp, plus the regular panel) within 60s and under $0.10.
- Confirming the host candidate creates a `people` row + `source_presenters` row in one POST.
- Re-running on the same channel does *not* re-file the still-pending or already-confirmed presenters.

## Related

- [Speaker Identification](./speaker-identification.md) — the matchers that consume confirmed presenters as priors (Phase 5).
- [Scout (the original source-discovery agent)](../agents/system/ingestion.md) — same loop shape and audit pattern this extends.
