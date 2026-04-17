# Avatar Interactions

Status: **Stub — design work in progress**

How the avatar reacts to things the user does (as opposed to [system.md](system.md) which covers reactions to what the *system* is doing).

---

## Scope

- Click reactions (tap the avatar → does what?)
- Hover reactions (desktop — cursor lingers over the avatar)
- Long-dwell reactions (user idle on a page for N seconds)
- First-visit moments vs returning-visitor easter eggs
- Reactions to specific user actions on the page (submitting a question, reacting to a Remark, opening a drill-down panel)
- Accessibility — avatar behaviour must not interfere with screen readers or keyboard nav

---

## Open Questions

- [ ] Is the avatar clickable? What does tapping it do on each page?
- [ ] Should the avatar respond differently to logged-in vs anonymous users?
- [ ] How do we handle reduced-motion preferences?
- [ ] Idle easter eggs — how rare should they be, and how are they triggered?
- [ ] Does the avatar ever speak on hover (floating text), or is voice reserved for Remarks?
- [ ] Does it react to scroll events (e.g. glance when new content arrives)?
- [ ] Mobile: is the avatar tappable or purely decorative?

---

## Related

- [system.md](system.md) — system-state triggered behaviour
- [per-page.md](per-page.md) — how behaviour varies across pages
- [`concepts/06-audience.md`](../concepts/06-audience.md) — broader audience interaction patterns
