# Cleaning Workbench

The cleaning stage turns raw, garbled originals into clean text that downstream extraction can reason about. This doc is the **workbench** — how we run cleaning, how we judge it, and how we iterate on it.

---

## Current Approach

The `/clean-transcript` Claude Code skill drives cleaning today. It combines:

1. **Deterministic NLP pass** — Python, pre-LLM. Fixes known auto-caption garbles using the registry in [patterns.md](patterns.md) + the authoritative `data/players.yaml` list.
2. **LLM review pass** — model reviews the deterministic output, catches what rules missed, produces the final cleaned text.

Input: raw transcript JSON in S3 (timestamped segments from YouTube Data API).
Output: cleaned text, same segment structure preserved, back to S3.

Cleaning is **currently skill-driven, not automated**. Each transcript is cleaned interactively, reviewed, then promoted. Automation happens after the approach is proven (see [iteration](#the-iteration-loop)).

---

## What "Good" Looks Like

The cleaning pass must meet four bars:

### 1. Name accuracy (zero tolerance)

Every player name, team name, and advisor name in the cleaned text must match the canonical form in `data/players.yaml`. Mis-spelled names poison extraction and break attribution.

Example: `"Moses Suley"` (auto-caption garble) → `"Moses Suli"` (canonical).

### 2. Claim preservation

Every SuperCoach-relevant claim in the original must survive cleaning. If a host says "I'd sell Cleary," the cleaned text must retain that statement. Cleaning removes noise; it does not summarise.

### 3. Timestamp integrity

Segment start/end timestamps must remain accurate. Citations depend on them. Reformatting or consolidating segments is acceptable only if timestamps update correctly.

### 4. Protected terms preserved

Slang, nicknames, and NRL-specific jargon must not be "corrected" by the LLM. Example: `"PVL"` is an actual term, not a typo. See [patterns.md § Protected Terms](patterns.md#protected-terms).

---

## Known Failure Modes

| Failure | Example | How to spot |
|---------|---------|-------------|
| Name substitution | `"Reece Walsh"` → `"Reese Walsh"` (spelling drift) | Diff against `data/players.yaml` canonical names |
| Claim loss | Host's throwaway aside stripped because it "sounded unimportant" | Diff length + claim count vs raw |
| Timestamp drift | LLM merges segments without updating timestamps | Assert monotonic increase on output |
| Slang "correction" | `"PVL"` → `"Payroll"` (LLM confused) | Allow-list check against [patterns.md § Protected Terms](patterns.md#protected-terms) |
| Hallucinated names | LLM invents a player who isn't in `data/players.yaml` | Assert every player mention ∈ canonical registry |
| Advisor context drift | "KingOfSC said X" becomes "Someone said X" | Speaker attribution diff |

Each failure mode should have an automated check in the evaluation pass.

---

## The Iteration Loop

```
Spot issue  →  Log pattern  →  Update skill  →  Re-run test set  →  Compare
    ↑                                                                   │
    └───────────────────────────────────────────────────────────────────┘
```

**Spot issue** — during review of a cleaning pass, notice a name was mangled, a claim was dropped, or a term was over-corrected.

**Log pattern** — add the correction (or the "do not correct") to [patterns.md](patterns.md). If it's cross-conversational, also add to memory (`reference_transcript_corrections.md` or `reference_nrl_slang.md`).

**Update skill** — modify `/clean-transcript` so the pattern is applied going forward. Deterministic patterns go into the Python pre-pass; judgment patterns go into the LLM prompt.

**Re-run test set** — a small, stable set of representative transcripts. Clean them with the updated skill, compare output.

**Compare** — eyeball diff on the test set. Verify:
- The specific issue is fixed
- No regression on previously-good cases
- Name accuracy still 100%

**Commit** — pattern merged. Test set grows over time.

---

## Evaluation Metrics

As the test set stabilises, the following metrics should be measured on each cleaning-skill change:

| Metric | How measured | Target |
|--------|--------------|--------|
| Name accuracy | % of player mentions matching canonical | 100% |
| Claim preservation | Claims in raw vs claims in cleaned (per annotated gold) | ≥ 98% |
| Timestamp drift | Avg Δ between raw and cleaned segment timestamps | ≤ 0.5s |
| Garble rate | Count of known-bad strings remaining in output | 0 |
| Over-correction rate | Count of protected terms modified | 0 |

Measurement tooling is not yet built. `DeepEval` or a bespoke diffing script is the expected shape.

---

## Test Set

A small set of transcripts representative of the variety we see:

- 1 SC-focused dense podcast (high player mention density)
- 1 game-review podcast (high narrative content, low claim density)
- 1 post-round recap (high claim density, contradictions across sources)
- 1 tangent-heavy episode (low signal, high "do not over-correct" risk)
- 1 transcript with a rare slang/nickname term ([PVL](patterns.md#protected-terms) class)

Committed gold-standard cleaned versions become the reference. **Stored under `data/transcripts/gold/<slug>.json`** (not docs — this is operational data).

---

## Integration with Extraction

Cleaning output feeds [the extraction stage](../agents/system/extraction.md). A bad clean cascades: lost claims can't be extracted; renamed players link to wrong entities; garbled text confuses claim-type classification.

Extraction issues often surface cleaning issues. When verification (`/verify-claims`) flags a FAIL, check whether the problem is the raw text, the cleaning, or the extraction model — in that order.

---

## Open Questions

- [ ] When does cleaning become automated (worker activity) vs stay skill-driven (interactive review)?
- [ ] What's the cost model for LLM-based cleaning at scale?
- [ ] Should we cache cleaned versions keyed by (raw hash, skill version) to avoid re-cleaning when raw hasn't changed?
- [ ] How do we version cleaned outputs? Re-clean when the skill improves?
- [ ] Should diarisation (speaker attribution) happen during cleaning, or as a separate stage before extraction?
