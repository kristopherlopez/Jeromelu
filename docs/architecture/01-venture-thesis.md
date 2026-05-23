---
tags: [area/architecture]
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

→ Detail in [Knowledge Asset](03-knowledge-asset.md).

## Why This Is Possible Now

A few things have to be true at once.

- **LLMs are good enough to hold a voice** across thousands of outputs without drifting into generic AI register.
- **Multi-agent orchestration is finally productionable** — the "team of specialists" pattern actually composes coherent output instead of falling apart at the seams.
- **Speaker-diarised transcription is cheap and accurate enough** to ingest the entire NRL podcast ecosystem week after week.
- **Generative voice and video are on a clear cost-down curve** — capture everything in text now, the medium gets richer on top of the same captured data.

None of these were true two years ago. Most are still novel enough that a captivating agentic experience with a home is genuinely an unsolved problem, not a copy-paste.

---

## Related

- [The Show](02-the-show.md) — how the experience works: the crew, surfaces, episode arc, participation, and what we won't build
- [Knowledge Asset](03-knowledge-asset.md) — what compounds, what it unlocks, what it costs
- [Design Principles](../concepts/00-design-principles.md) — visual and editorial rules
- [Audience](../concepts/06-audience.md) — how participation works
- [V1 Scope & Roadmap](09-v1-scope-and-roadmap.md) — what ships first against this thesis
