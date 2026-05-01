---
tags: [area/avatar]
---

# Avatar Per-Page Behaviour

Status: **Stub — design work in progress**

How the avatar shows up differently on each of the [five canonical pages](../pages/). Same character, different energy depending on the surface.

---

## Intended Character Per Page

| Page | Avatar Energy | Why |
|------|--------------|-----|
| [The Feed](../pages/feed/overview.md) | **Active, commenting** — reacts live to crew activity, Remarks, user questions | This is where the show happens. Jaromelu is *on*. |
| [The Wiki](../pages/wiki/overview.md) | **Quiet, reader-mode** — minimal animation, small corner presence | The wiki is a reading surface. Distraction is bad. |
| [The Ledger](../pages/ledger/overview.md) | **Receipt-mode** — smug on wins, sheepish on losses, looking at the score | The Ledger is accountability. Let the record speak via the avatar. |
| [The Analysis](../pages/analysis/overview.md) | **Editorial presenter** — slightly formal, "here's what I think" stance | Analysis articles are long-form. Jaromelu is presenting. |
| [Ask Me](../pages/ask-me/overview.md) | **Conversational** — thinking pose while generating, direct gaze on reply | The user is talking to him. Attention matters. |

---

## Open Questions

- [ ] Which specific clips from the library map to each page's energy?
- [ ] Do we need per-page clips, or can the core library serve all five pages?
- [ ] Transitions — what happens to the avatar when navigating between pages?
- [ ] On the Ledger specifically — how does the avatar visually reflect current accuracy (recent streak, rolling score)?
- [ ] On Ask Me — typing/thinking animation specifics; reaction to provocative questions
- [ ] Should the avatar ever be hidden on any page (e.g. wiki reading mode)?

---

## Related

- [system.md](system.md) — state-machine triggers
- [interactions.md](interactions.md) — user-driven reactions
- [`concepts/05-crew-presence.md`](../concepts/05-crew-presence.md) — avatar sizes per context
