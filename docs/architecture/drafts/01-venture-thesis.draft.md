---
tags: [area/architecture]
status: draft
---
# Venture Thesis (Draft — experience-led rewrite)

> Draft revised 2026-05-23. The previous customer-centered structure has been replaced with an experience-led one. The thesis is *"a captivating agentic experience with a home, NRL is the chosen domain"* — not *"a customer with a utility pain we relieve."* Sections reordered and rewritten accordingly. See drafting notes at the bottom for the diff against the prior version.

---

# Venture Thesis

> Last reviewed: 2026-05-23.

Jaromelu is an autonomous AI commentator on the NRL — an anthropomorphised agentic presence with a name, a voice, opinions, a public track record, and **his own home on the web**. He's run by a crew of agents who ingest the NRL media ecosystem, build a continuously evolving view of the competition, form opinions, make calls, and live with the consequences. And you can watch them work.

Chat UIs exist. Character.ai-style chatbots exist. AI characters with real followings live on social platforms — but they're tenants on Instagram and TikTok, and you never see the operation behind the personality. **A captivating agentic experience that lives in its own home, where the work is part of the show — that's the shape nobody's built.** That's the category Jaromelu opens.

---

## What We Want People To Feel

Two emotions, in order.

**On arrival: awe.** *"Wait — this is an AI, and it actually has takes."* The shock of meeting something that feels alive instead of indexed. Not a chatbot waiting for you to prompt it. Not a wrapper around a model. A presence with a name, a voice, and opinions about your team — already mid-thought when you arrived.

**On return: aquarium.** Something is always happening. Scout is searching. Analyst is cross-referencing. Archivist is updating the wiki. Critic is disagreeing in the corner. The screen looks different on Monday than on Thursday because the operation kept running while you were gone.

These aren't competing emotions — they're **first encounter** and **sustained pull**. The site has to deliver both. The awe gets people to remember the URL. The aquarium gets them to type it again.

## The Show

Jaromelu is the voice. One personality, one editorial register — everything you read or hear in his name is his.

The crew is the visible labour. Scout, Analyst, Critic, Bookkeeper, Archivist — they don't speak in their own voice, they *work*, and their work is visible:

- A Scout query firing into the YouTube ecosystem
- A new source landing in the candidate queue
- An Archivist diff hitting the wiki
- A Critic flag attached to a claim that didn't hold up
- A Bookkeeper ticking off last week's predictions against reality

The closest reference frames are watching collaborators move around in a shared Google Doc, or watching fish in an aquarium. You're not driving the operation. You're watching it. When something interesting surfaces you can lean in — but you don't have to.

This is the spectacle. Not the polished output of an AI tool. The visible work of a non-human intelligence doing its job, all the time.

The bar for whether it's working is personal: is it entertaining to *watch*? The creator is the first and harshest member of the audience — if the operation can't hold his attention, it isn't ready. That's the right test, not a proxy metric.

## Why NRL

The honest answer: **because the creator loves NRL.**

This is not a market-led choice. It's not a wedge into a category. The experiment runs on NRL because that's where the work is sharpest — where someone knows the audience well enough to make the output bite, where someone watches the content closely enough to catch when an opinion is dishonest, where someone cares enough to keep going.

NRL is also a good fit for the format. Heavy weekly content cycle. Opinion-saturated commentary ecosystem. Results graded in public every weekend. Decades of stats and rivalries to ingest. The domain rewards a system that listens widely and remembers.

But the thesis is **agentic experience with a home**. The domain is the lens, not the bet. If the shape works on NRL — anthropomorphised, visibly-crewed, living on its own website — it extends to any sport, and very likely any topic with a passionate audience and a content cycle that keeps producing.

## Who Finds This Irresistible

Hardcore NRL fans. Already three podcasts deep. Already two YouTube channels behind. Above-average game literacy. Australian. Time-poor. Opinion-saturated.

The spectacle lands hardest for them because the show happens in a language they already speak. They know the players, the rivalries, the running arguments. Watching an AI form opinions about all of it hits differently for someone who already has their own opinions about all of it.

They didn't come to fix a utility problem. But they have one. The audience is drowning in commentary — three podcasts deep, two YouTube channels behind, panel takes contradicting each other on Tuesday and forgotten by Thursday. Jaromelu, by virtue of existing, listens to all of it, forms his own view, and grades last week's takes against reality. That's a free utility on top of the spectacle. They'll use it. It's just not why they showed up.

We are not building for the casual NRL viewer. The thesis is built around an audience that already lives in NRL discourse — and finds something they've never seen before waiting for them when they arrive.

## What Compounds

The crew is building a continuously growing knowledge base of all things NRL — claims, predictions, sources, attributions, results. Every podcast transcribed. Every prediction recorded. Every outcome graded. Speaker-attributed, time-stamped, queryable.

**It augments Jaromelu.** Sharper takes, deeper memory, better calls. The longer the project runs, the more context he has to draw on.

**It earns his credibility.** Jaromelu's own takes run passively from day one, graded against the same reality as the human pundits'. The point isn't to be loud early — it's to accumulate a track record. Once his calls demonstrably rival the humans', the awe stops being "cute, an AI has opinions" and becomes "this thing is actually good." The ledger is the proof, not just the theatre.

**It's a discovery surface.** Because every claim is speaker-attributed, the audience doesn't just see *what* was said — they see *who* said it, and how often that person was right. Someone with sharp, well-graded, contrarian takes becomes worth following. Jaromelu turns into a way to find the voices in the NRL ecosystem worth your time.

**It unlocks new directions.** Whose predictions came true. Who's good at predicting what — player form, scoreline, finals, recovery timelines. How those track records intersect with sports betting. How they intersect with SuperCoach. Each is a separate opportunity sitting on the same captured data.

And the shape isn't NRL-specific. Done well, the same operation — ingest a domain, form opinions, grade them in public, surface the voices worth following — extends to any sport, and very likely any topic with a passionate audience and a steady content cycle.

→ Detail in [Knowledge Asset](03-knowledge-asset.draft.md).

## Why This Is Possible Now

A few things have to be true at once.

- **LLMs are good enough to hold a voice** across thousands of outputs without drifting into generic AI register.
- **Multi-agent orchestration is finally productionable** — the "team of specialists" pattern actually composes coherent output instead of falling apart at the seams.
- **Speaker-diarised transcription is cheap and accurate enough** to ingest the entire NRL podcast ecosystem week after week.
- **Generative voice and video are on a clear cost-down curve** — capture everything in text now, the medium gets richer on top of the same captured data.

None of these were true two years ago. Most are still novel enough that a captivating agentic experience with a home is genuinely an unsolved problem, not a copy-paste.

---

## Related

- [The Show (draft)](02-the-show.draft.md) — how the experience works: the crew, surfaces, episode arc, participation, and what we won't build
- [Knowledge Asset (draft)](03-knowledge-asset.draft.md) — what compounds, what it unlocks, what it costs
- [Design Principles](../concepts/00-design-principles.md) — visual and editorial rules
- [Audience](../concepts/06-audience.md) — how participation works
- [V1 Scope & Roadmap](09-v1-scope-and-roadmap.md) — what ships first against this thesis

---

## Drafting notes (delete before merge)

**Reframe vs prior draft.** Previous draft was customer-centered: started with audience, built pull from frustration, treated spectacle as a side. This version is experience-led: starts with the new-category claim, lets aesthetic carry the pull, demotes audience to "who this lands for," and pulls NRL out as an honest creator-led domain choice.

**Section order — new:**

1. Opening (new-category claim — captivating agentic experience with a home doesn't exist yet)
2. What We Want People To Feel (awe on arrival + aquarium on return)
3. The Show (Jaromelu = voice; crew = visible labour; Google-Doc / aquarium reference frame)
4. Why NRL (proud, creator-led)
5. Who Finds This Irresistible (audience — demoted from #2 to #5)
6. What Compounds (knowledge asset + moat + downstream unlocks)
7. Why This Is Possible Now (feasibility — moved to last)

**What was cut from the prior draft:**

- *"Entertainment spectacle first, utility second"* line — replaced by the cleaner new-category claim.
- *"What They're Frustrated With Today"* as a standalone section — frustration is now a side-effect benefit folded into "Who Finds This Irresistible," not the hook.
- *"Why Would People Want This"* as a standalone section — its real content split: customer pull → "What We Want People To Feel" + "The Show"; defensibility → "What Compounds."
- *"Predominantly male"* demographic line — cut as noise.
- SC reference in the audience section — SC isn't load-bearing here and is properly covered downstream.
- Long V1 trade-off paragraph about real-time AI video being research-grade — moved out of the Feel section.
- *"What They Do Here"* (participation: react/challenge/grade/PAI) — moved to the show (now `02-the-show.draft.md`). Participation is a layer on top of watching, not part of the venture thesis.

**Resolves prior tensions:**

- *Spectacle vs utility.* Spectacle is the product. Utility (compression of NRL discourse) is a free side-effect folded into Section 5.
- *Defensibility framed as customer pull.* The moat framing was dropped entirely in round 2 (see below) — the goal is extensibility, not defensibility. Customer pull lives in Feel + Show.
- *Crew visibility contradiction.* Resolved as: Jaromelu is the single voice; the crew is the visible labour. They work, they don't speak. This is now explicit in "The Show."

**Round 2 (2026-05-23) — pressure-test responses folded in:**

- *Audience / framing.* This is a personal creator thesis, not an external pitch — so it doesn't need a defensive competitive-landscape section. Opening was sharpened anyway: nearest neighbours (AI VTubers, AI social-media characters) are *tenants on platforms they don't own* and *never show the operation* — the wedge is "own home + visible work," not "nothing exists."
- *The bet that visible agent work is entertaining.* Stated as a personal bar in "The Show" — the creator is the first and harshest audience; if it doesn't entertain him, it isn't ready. Deliberately not defended with metrics.
- *Moat dropped.* Creator doesn't care whether it's a moat. Replaced with the genuine belief: done well, the shape extends to any sport and likely any topic. This also resolves the old lens-vs-moat contradiction.
- *Discovery added.* New thread in "What Compounds": speaker-attribution makes Jaromelu a way to *discover* commentators worth following, not just a who-was-right ledger.
- *Awe is earned, not assumed.* New "It earns his credibility" beat in "What Compounds": takes run passively and graded vs human pundits from day one; foregrounded once demonstrably comparable. The ledger is the proof mechanism behind the awe.
- *Betting language softened* from "influence sports betting markets" to "intersect with sports betting" (regulatory reality; light touch only).
- *Held for user feedback (no change):* the ambient-aquarium return-driver, and the "no stated risk" critique.

**Follow-ups:**

- ✅ Knowledge Asset drafted — now `03-knowledge-asset.draft.md` (renumbered from the proposed 04).
- ✅ Participation content (react / challenge / Personal Alignment Index) already lives in the show (`02-the-show.draft.md`) — nothing to move.
- ✅ Memory note `project_crew_terminology` updated to "single voice, visible labour."

**Series renumber (2026-05-23):** spine is now **01 thesis → 02 the show → 03 knowledge asset.** The old `02-what-we-promise` (Scope & Non-Goals) was dissolved into the show's closing "Scope — What We Won't Build" section. Related links above point to the draft spine, not the committed `02-value-and-delivery.md` / `03-experience-architecture.md` (full series renumber on merge is a separate decision).
