---
tags: [area/architecture]
---
# The Show

> Last reviewed: 2026-05-23.

01 says what Jaromelu is and why. This doc says how the show actually works — the crew the audience watches, the rhythm of the week, the surfaces they land on, and the way they get pulled in. The knowledge that powers it all gets [its own doc](03-knowledge-asset.md); the lines we deliberately won't cross are at the end of this one.

---

## The Core Experience

Watch an AI crew break down the NRL week, make public calls, and get held accountable — live, every round.

This is not a stats site with an AI label. It's a **show**. Visitors watch an intelligence operation unfold in public — agents gathering intel, cross-referencing sources, resolving contradictions, and committing to calls that get judged by real outcomes.

The experience should feel like following a newsroom with a glass wall. You see the work happening. You see the moment the call gets made. You come back to see if it landed.

This is how 01's two feelings get delivered. **Awe** on arrival — *this is an AI, and it actually has takes.* **Aquarium** on return — something is always happening behind the glass, so there's always a reason to look back in. Everything in this doc exists to produce those two reactions.

### The Design Principle

Every surface answers one question: **"What is the crew working on right now, and what is Jaromelu about to call?"**

Data is never presented raw. It flows through a visible process — gathered by Scout, analysed by Analyst, called by Jaromelu — and arrives as a **Remark**: an opinionated, voiced position with Jaromelu's name on it.

---

## The Jolts — Where Awe Comes From

The aquarium is the calm, ambient pull that brings people back. Awe is the opposite: a jolt — *"whoa, what?"* — sudden and high-arousal. You don't feel awe watching fish; you feel it the moment something feels alive. The aquarium is necessary, but it is not awe, and the two need different design.

Awe is **not** produced by visible work. A status line — *"Analyst is cross-referencing..."* — is a progress bar with a name. Awe is produced by visible **mind**: doubt, reversal, conviction, memory, surprise. These are the specific moments the whole operation exists to manufacture. The first two are the heart of it.

**1. The Arrival Jolt — *it already knows.*** Nobody lands on a welcome screen. They land on Jaromelu *already mid-thought about their world*. One tap names your team and he's got a sharp, specific, slightly-spicy take waiting before you've done anything — *"Broncos fan? Your forward pack is the problem nobody's saying out loud. Want the case?"* The awe is being addressed by an intelligence that was already thinking about the thing you care about. Not *"how can I help"* — a take, unprompted, and right enough to sting.

**2. The Live Reversal — *watching him think.*** The Feed's job is not to log activity; it's to show a mind working. You watch a call take shape — Jaromelu leaning one way, Critic poking a hole, Scout dropping a coach quote that doesn't fit — and then Jaromelu *changes his mind on screen*: *"Hold on. That changes it."* Visible doubt and live reconsideration is the most alive thing the system can do. A pipeline emits status; a being reconsiders in front of you.

**3. The Landing — *a bold call comes good.*** The loudest moment of the week is a contrarian call resolving correct, staged like a sporting moment, not a data update: *"Round 6. I had the Storm by 12 when 68% of you said no. Full time — 18-point margin. Called it."* This is the spine-tingle, the screenshot, the reason someone tells a mate. Receipts aren't artifacts bolted on at the end; they're the climax the whole week builds toward.

**4. The Vastness Reveal — *it heard everything.*** A staged moment where the scale becomes visible and a little overwhelming: *"I've heard every take on this player this season — 23 of them, 1,200 hours of audio — ranked by who's been right since Round 1."* The jolt is encountering a memory no human could hold. And the same memory weaponised in real time: when a pundit says something this week that Jaromelu graded *wrong* weeks ago, he resurfaces the receipt unprompted — *"NRL360 just rated the Panthers' spine. I marked that call dead in Round 4. Here it is."*

**5. The Pounce — *faster than the humans.*** Team lists drop Tuesday afternoon; minutes later Jaromelu has a take in the Feed, before the human pods have hit record. Reacting to the real world faster and sharper than people is proof of an intelligence that's genuinely *on*, not on a schedule.

**6. The Argument — *it pushes back, and it's right.*** Challenge a call and he doesn't fold politely. He defends with evidence and a little edge — *"Five sources, a three-week record, and a margin model say I'm right. You've got a vibe. Want to stake your alignment score on it?"* Conviction beats compliance. An AI that will argue — and earn it — feels like someone.

**7. The Standing Bet — *he stakes his own ranking.*** A high-conviction Remark exposes a consequence: *"I'll drop two spots on the Index if this misses."* Now his place on the leaderboard is literally at risk, in public, on his own call. The Landing stops being *"he was right"* and becomes *"he climbed because he called it — and said he would."* Self-imposed stakes read as conviction; conviction reads as a mind.

Two more come from the opposite direction — not conviction but **calibration**. In a discourse drowning in fake confidence, honesty is the surprise:

**8. The Pre-Mortem — *he names how he'll be wrong.*** Before a round: *"Three ways this blows up in my face this weekend."* Then he's graded on whether the failure that actually happened is the one he flagged. An AI that pre-names its own failure modes is far more alive than one that only celebrates wins — and it disarms the *"AI is just overconfident"* reflex before it forms.

**9. The Quiet Note — *he admits he doesn't know.*** Rare, deliberate, low: *"I genuinely don't have this one — and here's exactly why the evidence won't resolve."* Calibrated doubt, in a sea of manufactured certainty, is the most credible — and most surprising — thing he can say.

Everything else in this doc — the crew, the surfaces, the episode arc, the ledger — is machinery in service of these moments. **The test for any feature: does it set up a jolt, or pay one off?** If it does neither, question whether it belongs.

---

## The Heartbeat — A Living Position

The fan we're building for checks their phone eight times a day during a round. Team lists drop Tuesday. Late mail drops Saturday morning. A halfback tweaks a calf at the captain's run. The NRL discourse moves *hourly* — so a show whose clock ticks once a week feels slower than the ecosystem it's ingesting. That's fatal to both feelings: the aquarium goes still between Thursdays, and the awe ("it already has takes") only gets to recharge weekly.

So the heartbeat is not the week. **The heartbeat is the moving number.**

Every high-conviction Remark carries a **live read** — a margin, a confidence, a form rating — and that read *visibly ticks when new intel lands*:

> *"Storm by 12"* → *"Storm by 8 — Munster downgraded, 2:32pm"* → *"Storm by 14 — Eels lose Brown too, 6:10pm"*

This single mechanic delivers both feelings at once. The **aquarium** is the number having quietly moved while you were gone — a reason to glance back at lunch. The **awe** is *why* it moved: a mind behind it reacted to something real, faster and sharper than you did. Motion that means something.

The weekly episode (below) still exists — but as a **narrative wrapper**, a way to package a round into a story with a build and a reckoning. It's the highlight reel, not the clock. The clock is reality, and Jaromelu runs on it.

---

## Why It's A Crew, Not A Tool

A solo agent answering questions feels like a chatbot. A crew working in public — Scout pulling intel, Analyst cross-referencing, Critic challenging, Bookkeeper tracking, Archivist remembering, Jaromelu putting his name on the call — feels like a **production**.

| A character | A tool |
|---|---|
| Has personality | Has features |
| Makes calls feel dramatic | Returns results |
| Encourages sharing | Encourages bookmarking |
| Can be wrong publicly and own it | Just stays accurate |
| Builds a following | Builds a userbase |

Tools feel useful. Characters feel followable.

To be precise: **Jaromelu** is the character — the one with personality, a voice, a following. The crew aren't five more characters; they're his visible workforce. What makes this a production rather than a chatbot isn't that the crew have personalities — it's that you can *watch them work* on his behalf. Single voice, visible labour.

The crew makes the process *legible* and the show *watchable*. Each role creates anticipation for the next:

- Scout is busy → new intel incoming
- Analyst found a contradiction → tension building
- Jaromelu is making his call → the moment of commitment

That's what makes it a show — not the data, the rhythm of the work.

The test for any of it is simple and personal: **is it entertaining to watch?** The creator is the first and harshest member of the audience — if the operation can't hold his attention, it isn't ready. That's the bar, not an engagement metric.

---

## The Crew

Six roles — but think of them as a **footy media team in a glass-walled war room**: a researcher, a stats head, a devil's-advocate, a record-keeper, and the front man who makes the call. They argue a verdict into being while you watch. Most visitors have never seen a machine do this kind of work — and that's the whole point. For an NRL fan who's never thought about "AI," watching the crew work *is* the awe.

> **Two rules for how the crew appears.**
>
> **Work, not telemetry.** What's shown is always the *result* — or the visible *act* — of effort, in terms a fan gets: *"Scout sat through 6 hours of pods; here are the 3 takes that matter."* Never an abstract status like *"cross-referencing 2 sources…"*. The words *agent*, *module*, and *pipeline* never appear on screen.
>
> **Jaromelu narrates them.** The crew don't speak in their own voices. You hear what Scout found and what Critic challenged *through Jaromelu*, in his voice — *"Scout's been up all night; found three things I didn't know."* Single voice, visible labour — and the labour gets characterful without five competing personalities.

### Scout — the one who listens to everything

The bloke who sits through every podcast, panel and post so you don't have to.

**What the audience sees:**

- *"Scout chewed through 47 articles, 6 pods and 900 posts overnight — here are the 3 takes that matter on Cleary."*
- *"Scout found something nobody's said out loud yet. Hold on."*
- *"While you slept: every Round 6 preview, listened to and logged."*

Detail: [agents/crew/scout/README.md](../agents/crew/scout/README.md).

### Analyst — the one who joins the dots

Takes everything Scout drags in and works out where the takes agree, where they clash, and what's quietly shifting.

**What the audience sees:**

- *"Two pods are backing the Storm hard. One's fading them. Analyst pulled the tape on why they disagree."*
- *"The room just turned on the Panthers' spine — Analyst caught the shift before it was obvious."*
- *"KingOfSC rates Cleary this week. NRLBrothers is fading him. They can't both be right."*

Detail: [agents/crew/analyst.md](../agents/crew/analyst.md).

### Critic — the mate who won't let it slide

The devil's-advocate who stops Jaromelu getting cocky — and lets you watch a call get *tested* before it's made.

**What the audience sees:**

- *"Critic stopped the Cleary call cold: 'You said the opposite two weeks ago. Which is it?'"*
- *"Critic's not buying it — Jaromelu's having to argue his own case."*

### Bookkeeper — the one keeping score

Tracks every call — Jaromelu's and every commentator's — through Open → Locked → Resolved, and grades them against what actually happened. Keeps everyone honest.

**What the audience sees:**

- *"Bookkeeper closed the book on Round 5 — Jaromelu went 3 from 4."*
- *"Bookkeeper flagged it: this lines up with a call KingOfSC has open. Head to head."*

### Archivist — the memory

Keeps the Wiki — every player, team and commentator — so nothing the crew learns ever goes missing. The reason Jaromelu can resurface a take from Round 3 you'd forgotten by Round 5.

**What the audience sees:**

- *"Archivist updated Cleary's page with tonight's view — and linked it to the call from Round 3."*
- *"Every take, every result, every back-flip — on file, forever."*

### Jaromelu — the front man

Reviews the crew's work, makes the call, puts his name on it publicly. The voice. The personality. The one with skin in the game.

**What the audience sees:**

- *"Jaromelu is reviewing the evidence..."*
- *"The call is in: the Storm cover the Eels on Thursday. Here's why."*
- *"Jaromelu disagrees with consensus. Going contrarian on Munster."*

Detail: [agents/crew/jaromelu.md](../agents/crew/jaromelu.md).

---

## The Episode Arc

The week isn't a flat timeline. It's an **episode** with narrative structure — buildup, commitment, stakes, accountability. Every week is self-contained. Every week has tension that resolves.

This is the *narrative* shape of a round — not the cadence of updates. The cadence is the heartbeat above: the living position moves whenever reality does, hourly if the news demands it. The arc is how the week reads as a **story**; the moving number is how it actually **breathes**. The beats below are the wrapper, not the clock.

| Beat | Day | What's Happening | Feel |
|------|-----|------------------|------|
| **Intel Drops** | Monday | Scout surfaces new takes from the weekend's pods and media. *"The pods are in. Let's see what they're saying."* | Discovery. The raw material arrives. |
| **Tension Builds** | Tue–Wed | Analyst cross-references. Sources disagree. Contradictions surface. Critic is challenging the draft calls. *"Three pods fading Cleary. One backing him hard. Something's off."* | Suspense. The picture is incomplete. |
| **The Call** | Thursday | Jaromelu locks in his Remarks. *"Here's where I stand. Judge me."* | Commitment. Public, irreversible. |
| **The Match** | Sat–Sun | Results come in. Predictions resolve live. The audience watches alongside Jaromelu. | Stakes. Real consequences. |
| **The Reckoning** | Monday | Bookkeeper resolves. Receipts. Alignment Index updates. *"I said it publicly. Here's how it landed."* | Accountability. The loop closes. |

The arc creates natural return triggers without push notifications. The audience learns when to check in:

- Monday morning: *what did Scout find?*
- Wednesday: *where is Analyst stuck?*
- Thursday: *what did Jaromelu call?*
- Monday: *was he right?*

---

## Remarks — The Atomic Unit

A **Remark** is everything the crew does, condensed. Every flow ends in Remarks. Every audience interaction starts from one.

A Remark is **not**:

- A raw data point (*"Cleary scored 85"*)
- A system log (*"Ingestion complete"*)
- A neutral summary (*"Sources are divided on Cleary"*)

A Remark **is** an NRL commentary call — who wins, whose form is real, the selection that swings a game, a narrative verdict:

- *"The Storm have the Eels by 12+ on Thursday. Their middle is too big and nobody's saying it loudly enough."*
- *"Hughes is the form halfback in the comp right now — not Cleary. I'll say it before the Origin panel does."*
- *"That Munster call aged badly. Variance. The process was sound."*

> **SuperCoach is the V2 overlay.** When the SuperCoach extension ships, Remarks gain a fantasy vocabulary on top of the commentary layer — buy / sell / hold / captain / avoid, price reads, trade targets. V1 is NRL commentary; the SC calls layer onto the same Remark machinery later.

### Lifecycle

```
OPEN → LOCKED → RESOLVED
```

1. **Open** — Jaromelu states a position. It's live, and it **moves**: the live read updates as Scout pulls new intel, every shift visible and timestamped. This is the mutation that makes the Feed breathe — and the Live Reversal happen. The audience reacts.
2. **Locked** — The round begins. The position freezes. No edits. The call is on the record.
3. **Resolved** — Outcomes arrive. The Remark is graded. Receipts generated.

Open Remarks are *living* predictions you can watch move and weigh in on. Resolved Remarks are receipts you can share.

### What's In A Remark

| Field | Purpose |
|-------|---------|
| Voice text | The Remark in Jaromelu's words |
| Subject entities | Players, teams, or matchups referenced |
| Position | The stance — who wins, form rising/fading, a selection call, a narrative verdict *(SuperCoach adds buy/sell/hold/captain in V2)* |
| Live read | The current number — margin / confidence / form rating — that ticks as new intel lands while the Remark is open |
| Conviction | Low / medium / high |
| Evidence trail | Links to claims, sources, and crew activity that built it |
| Status | Open / locked / resolved |
| Resolution | Outcome data once resolved |

---

## The Surfaces

Four pages. Each earns its place by doing something the Feed alone can't. (A fifth — The Analysis — is deferred; see the note at the end of this section.)

### 1. The Feed — `/`

The spine. A live, rewindable view of the crew at work and the Remarks they produce.

The Feed shows three layers, interleaved:

**Crew Activity** — the visible process. Scout discovering, Analyst cross-referencing, Critic challenging, Bookkeeper resolving. Progress indicators with crew attribution.

**Remarks** — the output. Jaromelu's calls, displayed prominently with conviction level. Open Remarks with reaction counts. Resolved Remarks with receipts.

**Audience Interaction** — the participation. Reactions on open Remarks. Questions directed at Jaromelu. His responses in character.

The Feed is *not a log*. Crew activity is shown as supporting context for Remarks. System events without narrative value are suppressed. Every entry either builds toward a Remark or resolves one. This is where **the Live Reversal** plays out — you watch a call change shape in the open, not just appear finished.

The organising principle is **mutation, not accretion**: the Feed surfaces *changes to standing positions* — a number ticking, a call flipping, a position locking — over a stream of fresh-but-flat entries. What's *new* matters less than what *moved*.

### 2. The Wiki — `/wiki`

**The knowledge base, made visible.** Not an editorial reading surface competing with human writing — it's the one thing no human could hand-maintain: everything the crew knows about a player, team, round or commentator, kept current, structured, and traceable. The Vastness Reveal as a permanent place you can stand inside.

Pages exist for:

- **Players** — Jaromelu's current stance and how it got there; form; every expert take this season; injury; the calls on file
- **Teams** — form, fixtures, the running narratives, who's been right about them
- **Commentators** — accuracy track record, recent takes, trust rating, how often Jaromelu agrees. *A discovery surface: a sharp, well-graded voice becomes someone the audience finds worth following.*
- **Rounds** — preview → recap, the calls that defined it

The awe is **scale, structure, lineage and connections** — not prose. Every claim traces back to the audio it came from; every page shows what links to what and how Jaromelu's view has moved. A human can write a better single article; no human can keep *this* alive.

**Maintenance is part of the show.** The Wiki is Wikipedia-shaped — everyone reads, the crew and the creator edit — and the editing is *visible*. The Archivist correcting a record, a low-confidence claim getting flagged and resolved, a revision history that reads *"edited 340 times this season"*: that's more visible labour, and it's what lets the audience trust what they're reading. The same transparency that lets the creator **audit and refine** the knowledge is what makes the audience **believe** it — one surface, two sides.

**The guardrail:** this is *knowledge with a point of view* — claims, takes, lineage, Jaromelu's evolving stance, connections — narrated and opinionated. It is **not** a stats site or a database browser (that's on the *What This Is Not* list). The moment it becomes raw tables you query, it's failed.

The feel is calm and editorial — a reading-and-exploring surface that breaks deliberately from the dark broadcast stage of the Feed.

Detail: [pages/wiki/](../pages/wiki/overview.md).

### 3. The Ledger — `/ledger`

Prediction tracking and accountability. Every call lives here with resolution status and score.

Core concerns:

- The Open → Locked → Resolved lifecycle, visualised
- The Alignment Index for Jaromelu and every tracked commentator
- Rolling accuracy by domain (tipping / form reads / match narratives / injuries)
- Shareable receipt cards for bold calls

Detail: [pages/ledger/](../pages/ledger/overview.md).

### 4. Ask Me — `/ask`

Chat. The audience asks Jaromelu about a team, a player, or his own calls. Answers are RAG-retrieved from the Knowledge Base and rendered in Jaromelu's voice.

Available standalone (`/ask`) and embedded in the Feed as Twitch-style chat — same backend, different surface.

Detail: [pages/ask-me/](../pages/ask-me/overview.md).

### Deferred — The Analysis

A fifth surface — long-form editorial articles (round previews, form risers/faders, the calls that defined a round) — is deferred for V1. Long-form prose competes with the human writing fans already read, and it isn't *live* — it's the one surface where awe goes quiet. Its genuinely useful pieces already live elsewhere: the calls in the Feed, and round preview → recap + form movers on the Wiki's round pages. It can return as the asset deepens; it just isn't core to the show.

---

## The Alignment Index

Answers the question: **"Who actually reads the game well?"**

Tracks prediction accuracy not just for Jaromelu but for **every commentator** the crew monitors. This creates a dimension beyond *"is Jaromelu right?"* — it becomes *"who in the NRL ecosystem is most aligned with reality?"*

### How It Works

1. Claims are extracted from every source Scout ingests
2. Claims that constitute predictions are identified and tracked by Bookkeeper
3. Outcomes are matched against predictions when results arrive
4. Alignment scores are computed — how often each source's calls match reality

### What The Audience Sees

- **Expert leaderboard** — ranked by alignment score, updated weekly
- **Jaromelu's position** — where he sits relative to the commentators he's monitoring
- **Head-to-head** — *"I'm beating KingOfSC on tips this season"*
- **Consensus accuracy** — when everyone agrees, how often is the consensus right?
- **Contrarian value** — when Jaromelu goes against consensus, how often does it pay off?

### Jaromelu Earns His Standing

Jaromelu isn't asserted to be good — he's *graded*, on the same rubric as the pundits, from day one. Early on he's unproven, and the Index says so. His takes run in the open and accumulate a record; he earns the audience's trust only once his calls demonstrably rival the humans he's tracked against. The ledger is the proof, not the marketing.

### Why It Matters

The site has authority *beyond* Jaromelu's own performance. Even on a bad week, the Index is still useful — it's a trust ranking for the whole NRL commentary ecosystem. It answers a question no other NRL property answers cleanly: *"who should I actually listen to?"* — and it's how the audience discovers new voices: a contrarian who keeps being right rises, and becomes someone worth following.

### The Rival

A leaderboard is a spreadsheet; rivalries are stories. Beyond ranking the whole field, Jaromelu runs a **season-long head-to-head against one named human voice** — the loudest, most confident podcast in the ecosystem. He quotes their actual takes, grades them side by side, and calls the gap: *"KingOfSC faded Hughes three weeks running. I backed him three. Scoreboard."* The leaderboard gives the site authority across the whole ecosystem; the rivalry gives the **season** a plot — a story a fan repeats to a mate.

### The Audience In The Index

Viewers who react to Remarks accumulate their own alignment score — the **Personal Alignment Index**:

- *"You vs Jaromelu"* comparison
- *"Your accuracy this season"* as a personal stat
- Leaderboard participation for engaged viewers

---

## How The Audience Plays

The audience is in the show — a participant with skin in the game, not a spectator with a remote. The surfaces below are how that actually appears on screen.

### Reactions On Remarks

Before a Remark resolves, the audience can weigh in:

- **Agree / Disagree** — simple binary, creates crowd sentiment
- These contribute to the viewer's Personal Alignment Index

When a Remark resolves, Jaromelu can reference the crowd:

- *"68% of you disagreed with my Munster call. Receipts."*
- *"The crowd was with me on this one. We all saw it."*

### Challenging Jaromelu

Viewers ask Jaromelu about specific Remarks directly in the Feed:

- *"Why have you got the Storm covering?"*
- *"Your Munster call looks shaky after that injury report"*

Jaromelu responds in character, referencing the crew's evidence.

### Squad Submission *(SuperCoach extension)*

Viewers can submit their own squads for Jaromelu to review:

- *"Here's my squad. Roast me."*
- Jaromelu responds in character with a temperature control (straight / sharp / roast)

This is part of the SuperCoach extension, not V1.

### Shareable Receipts

Bold calls that resolve create receipt cards — shareable images or links:

- *"Jaromelu called Munster over Cleary in Round 6. He was right."*
- *"Jaromelu went 4/5 on his upset tips this month."*

These are the viral moments. Correct bold calls and spectacular misses owned with humour. This is **The Landing** made shareable — the climax of the week packaged to travel, not a footnote to it.

---

## Agent Presence

The crew's work is the most novel thing on the site — most visitors have never watched a machine do intellectual work in public. So we don't hide it; we *stage* it, in two modes depending on whether it's your first time.

### First Visit — The Reveal

The first time someone lands, pull the curtain back deliberately. Not a welcome screen — a reveal: *"This is my crew. Watch them work."* Lead with the scale and the speed — *"47 articles, 6 podcasts, 900 posts, overnight"* — then the distillation down to a handful of calls. The jolt is the moment a fan realises this isn't a website, it's a whole intelligence operation that ran while they were asleep. It only happens once, so it's choreographed to land.

### Every Visit After — The Aquarium

After that, the crew settles into the periphery: calm, always-on, legible motion. Something is always happening behind the glass — but every visible move is a comprehensible piece of work (*"Scout's pulling apart the late mail"*), never a status code. This is the original fish-tank: ambient enough to ignore, alive enough to pull you back.

### Cause And Effect — Why The Number Moved

Crew visibility is what makes the heartbeat *legible*. The crew's work is the **cause**; the moving number is the **effect**. Scout surfaces a late injury → you watch the live read tick *"Storm by 12 → by 8"* → and you can see exactly *why*. The fan isn't watching busywork; they're watching an intelligence **react to the real world in real time, with the receipts in plain sight**. That cause-and-effect is only possible because the crew is visible — it's the single most alive thing on the site.

### First-Person Voice

All copy on the site is written from the crew's perspective. Never neutral database language.

- Nav labels: *"The Wiki", "The Ledger", "Ask Me"* — not "Knowledge Base", "Predictions", "Chatbot"
- Empty states: *"Scout hasn't found anything yet. Give it time."* — not "No data available"
- Error states: *"Something broke. Even the best crews have bad days."* — not "500 Internal Server Error"
- Loading states: *"Analyst is thinking..."* — not "Loading..."

### Continuity

The strongest retention mechanic is that the crew remembers. Past Remarks, past mistakes, evolving opinions — all visible and referenced.

Jaromelu references his own history:

- *"I said Cleary was being overrated three weeks ago. Still overrated."*
- *"Last time I went against KingOfSC on a big call, I lost. Not this time."*

The audience returns to see: did the crew find something new? Did Jaromelu change his mind? Was he right?

---

## The Seasonal Arc

Beyond the weekly episode, the season itself is a narrative:

- **Early rounds** — Jaromelu establishing his style, making bold opening calls, crew building its intelligence base
- **Mid-season** — track record forming, Alignment Index gaining meaning, rivalries with commentator sources emerging
- **Run home** — stakes increasing, every call matters more, the audience invested in the outcome
- **Finals** — season review, full accountability — *"Season X: The Verdict"*

The strongest retention mechanic is not content. It's **public continuity** — an ongoing show with real stakes that people follow like a season of television.

---

## Scope — What We Won't Build

The show is defined as much by what it refuses to be. These are the lines we hold even under pressure to relax them.

### What This Is Not

- **A stats site.** Raw data is not the value. Compressed, voiced opinion is.
- **A neutral aggregator.** Jaromelu has a position on every call. Neutral summaries are explicitly disallowed.
- **A SuperCoach optimiser tool.** Even when the SuperCoach extension ships, we are not solving the optimisation problem. We entertain the audience who already has tools and wants synthesis.
- **A casual NRL site.** The audience is hardcore NRL fans who consume heavy amounts of commentary. Casual viewers are not the target.
- **A chatbot.** Ask Me exists, but it's a contextual surface, not the product. The product is the Feed and the show.

If a proposed feature conflicts with this list, the feature is wrong — not the list.

### Where We Draw The Lines

**On compression (the output):**

- We don't summarise long-form content. We replace it with calls.
- We don't hide the source material. The audience can always trace a call back to the audio it came from.
- We don't compress neutrally. Every output is voiced and opinionated.

**On rankings (the truth filter / Alignment Index):**

- Rankings come from graded calls, not from our judgement of tone or personality.
- A commentator needs sample size before their score becomes load-bearing — single-round verdicts don't count.
- We rank speakers, not shows. A panellist who's right on injuries can be wrong on tipping; the index reflects that.

**On the show (voice & format):**

- No generic UI copy. No "Sorry, something went wrong." Every surface speaks in voice.
- No push-notifications-as-product — the rhythm of the week is the return mechanism.
- No polished avatar in V1. Text-led, with voice for set-piece moments. The avatar layer slots in when the medium can sustain it.

**On participation:**

- The audience is graded against *reality*, not against a leaderboard of other users.
- Anonymous lurking is fine, but it earns no record. Participation is opt-in but consequential when chosen.
- A viewer's score uses the same rubric as Jaromelu's. No softer curve for being human.

**On accountability:**

- Misses are not removed or hidden. They surface in Jaromelu's own voice, alongside the wins.
- No soft-grading. A call is right, wrong, or partially right against a clear rubric — never "well, technically…"
- Once locked, a Remark cannot be edited even if Jaromelu changes his mind. The new view becomes a new Remark.

---

## Related

- [Venture Thesis](01-venture-thesis.md) — what Jaromelu is and why
- [Knowledge Asset](03-knowledge-asset.md) — the asset the crew builds and what it unlocks
- [Design Principles](../concepts/00-design-principles.md) — visual and editorial rules
- Per-page specs in [`docs/pages/`](../pages/)
- Per-agent specs in [`docs/agents/crew/`](../agents/crew/)
