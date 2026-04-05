# Audience

The audience is not passive. They have a role in the show. They react, challenge, submit, and get held accountable alongside Jeromelu.

---

## Reactions

### Agree / Disagree

Every open Remark has two reaction buttons: **Agree** and **Disagree**. Binary. One tap.

**Where they appear:**
- On the Remark card itself (action buttons at the bottom)
- In the Interaction Bar when a Remark is in viewport (contextual)

**Behaviour:**
- Tap to react. Tap again to undo. Can switch before lock.
- Reaction is instant — optimistic UI, count updates immediately.
- Crowd sentiment bar updates in real time: `👍 142 agree · 👎 89 disagree · 62% agree`
- When the Remark locks, reactions freeze. No more changes.

**After Resolution:**
- Users who reacted are shown whether they were right or wrong.
- This contributes to their personal Alignment Index score.
- Jeromelu can reference the crowd: "68% of you disagreed. Receipts."

### Why Only Two Options

No "like" button. No emoji reactions. No "fire" or "100." Agree or disagree. This forces the audience to take a position — which is what makes the resolution meaningful. You can't claim you were right if you never committed.

---

## Challenges

The audience can challenge Jeromelu's calls directly. This happens through the Interaction Bar.

### How It Works

1. User sees an open Remark in the Stream
2. Interaction Bar shows: `Ask about this call... [→]`
3. User types: "Why are you selling Cleary? His form is fine."
4. A Dialogue Card appears in the Stream:

```
┌─────────────────────────────────────┐
│ 👤 User                     just now│
│ Why are you selling Cleary? His     │
│ form is fine.                       │
├─────────────────────────────────────┤
│ 🎤 Jeromelu                        │
│ "Form doesn't matter when the      │
│  matchup is this bad. His last     │
│  two against Melbourne: 42 and 51. │
│  The Bookkeeper ran the numbers.   │
│  The breakeven says sell. I trust  │
│  the matchup over the form guide." │
│                                     │
│  ▸ Related: Remark — SELL Cleary   │
└─────────────────────────────────────┘
```

### Tone Control

When typing a question, the Interaction Bar shows a temperature toggle:

```
┌─────────────────────────────────────┐
│ Why are you selling Cleary?    [→]  │
│ Tone: [Straight] [Sharp] [Roast]   │
└─────────────────────────────────────┘
```

- **Straight** — helpful, direct, references evidence
- **Sharp** — confident, slightly dismissive, still substantive
- **Roast** — entertaining, will mock the question if it deserves it

Default is Straight. The toggle is small and optional — power users discover it, casual users get good answers without it.

### Context-Free Questions

The audience can also ask questions that aren't about a specific Remark:

- "Should I trade Cleary this week?"
- "Who should I captain?"
- "What do you think of Munster's bye risk?"

These appear as Dialogue Cards in the Stream, not attached to any Remark. Jeromelu responds in character, referencing crew intel and existing Remarks where relevant.

---

## Squad Submission

Users can submit their own SuperCoach squad for Jeromelu to review.

### How It Works

1. User types in the Interaction Bar: "Here's my squad: [list of players]"
2. Or taps a "Submit your squad" prompt (shown periodically as a suggestion)
3. Jeromelu reviews and responds in character:

```
┌─────────────────────────────────────┐
│ 👤 User                            │
│ My squad: Cleary, Munster, Hynes,  │
│ Gutho, Mam, Crichton...            │
├─────────────────────────────────────┤
│ 🎤 Jeromelu                        │
│ "Cleary AND Munster? You're paying │
│  premium prices for two players    │
│  with terrible matchups this week. │
│  Gutho I like — I almost traded    │
│  him last week but he's trending   │
│  up. The real problem is your      │
│  bench. You've got $200k sitting   │
│  there doing nothing."             │
│                                     │
│  ▸ Players referenced: Cleary,     │
│    Munster, Hynes, Gutho           │
└─────────────────────────────────────┘
```

### Tone Matters Here

Squad reviews are where the Roast temperature shines:

- **Straight:** "Cleary's matchup is a concern this week. Consider alternatives."
- **Sharp:** "Cleary against Melbourne? Bold. Wrong, but bold."
- **Roast:** "Cleary against Melbourne. You hate money, don't you?"

---

## Personal Alignment Index

Users who react to Remarks accumulate their own accuracy record.

### How It's Tracked

- Every Agree/Disagree on a Remark is logged
- When the Remark resolves, the user's reaction is graded
- Accuracy is computed: total correct / total reacted

### Where It's Shown

**In the Ledger drill-down** — "You vs Jeromelu" section:

```
YOUR RECORD

Reactions this season: 47
Accuracy: 58%
Jeromelu's accuracy: 67%

You agreed with Jeromelu 72% of the time.
When you disagreed, you were right 35% of the time.
When you agreed, you were right 64% of the time.

Verdict: You should probably trust the crew more.
```

**On resolved Remarks** — a small personal indicator:

```
You disagreed with this call. You were wrong. ✗
```

or

```
You agreed with this call. You were both right. ✓
```

### No Account Required (Initially)

Personal tracking works with a browser fingerprint / local storage for anonymous users. No sign-up wall. If a user clears their data, they lose their record — that's fine for V1.

Future: optional account creation to persist across devices and appear on a public leaderboard.

---

## Shareable Receipts

Bold calls that resolve create receipt cards — purpose-built shareable content.

### When They're Generated

- Every resolved Remark gets a receipt card
- High-conviction calls get visually enhanced receipts
- Notable calls (streaks, upsets, spectacular misses) get special treatment

### How to Share

The Share button on resolved Remarks generates:
1. **A receipt card image** — downloadable, screenshottable (see [02-remarks.md](02-remarks.md) for layout)
2. **A share link** — `jeromelu.com/remark/abc123` — loads the Stream scrolled to that Remark
3. **Platform-specific sharing** — native share sheet on mobile, copy-to-clipboard on desktop

### Open Graph / Social Cards

When a Remark link is shared on social platforms, the preview card shows:
- Jeromelu's voice text (the headline)
- Position + subject + conviction
- Result (if resolved)
- "jeromelu.com" branding

This must look good in:
- iMessage / WhatsApp previews
- Twitter / X cards
- Facebook / Instagram link previews
- Discord embeds

### Pre-Game Sharing

Open Remarks can also be shared before resolution:
- "Jeromelu is calling SELL on Cleary this week. Do you agree?"
- This drives traffic back to the site for people to react

---

## Crowd Moments

The crew references the crowd in the show. This makes the audience feel like participants, not observers.

### Vindication

When Jeromelu is right and the crowd disagreed:
- A Stream card from Jeromelu: "68% of you disagreed with the Cleary sell. The 32% who backed me — respect."
- This appears during The Reckoning beat.

### Collective Miss

When the crowd and Jeromelu both got it wrong:
- "82% of you agreed with me on Munster. We all ate it together. Respect for going down as a group."

### Contrarian Crowd

When a small minority of the crowd was right against both Jeromelu and the majority:
- "Only 12% of you backed the Hynes call. You saw something I didn't. Credit where it's due."

### Crowd Accuracy Updates

Periodic Stream cards from the Archivist about crowd performance:
- "The crowd has been more accurate than Jeromelu on captain picks this month. 71% vs 60%."
- "When the crowd disagrees with Jeromelu, Jeromelu has been right 65% of the time this season."

These moments make the audience feel like their participation matters. They come back to see how their record is tracking — and to see if Jeromelu calls them out.

### Crowd Moment Video Clips

The most impactful crowd callouts get video treatment:
- **Vindication**: A short clip of Jeromelu pointing at camera — "Receipts." Then the crowd stat card.
- **Collective miss**: Jeromelu shaking his head, then looking at camera with a "we're in this together" expression.
- **Contrarian crowd was right**: Jeromelu slow-clapping. Genuine respect.

---

## Easter Eggs and Personality Quirks

The site should reward exploration and repeated engagement with small moments of character. These are not features — they're personality.

### Scroll Behaviours

- **Scroll to the very top** (oldest content in the Stream): Jeromelu's Crew Bar avatar glances up. Status text: "Going through the archives? Respect. Most people just look at the latest call."
- **Rapid scrolling up and down**: After 3+ fast direction changes, status text: "Make up your mind."
- **Sitting at the bottom of the Stream for 30+ seconds without scrolling**: Jeromelu's avatar gives a subtle nod — acknowledgment that you're watching live.

### Interaction Quirks

- **Submit an empty question** (hit send with no text): Jeromelu responds inline: "I can't read minds. Yet."
- **Ask "who are you?"**: A special response with more personality than usual — not a product description, but Jeromelu introducing himself in character.
- **Ask about the Critic**: "He's useful. I'd never tell him that."
- **Rapid agree/disagree switching** (toggling 3+ times on the same Remark): Status text: "Commit. This isn't hard."

### Time-Based Quirks

- **Visit at 3am**: Crew Bar status: "You're up late. So am I. The crew never sleeps."
- **Visit on Christmas Day / NYE**: A special idle state: "Even the crew takes a break. Almost."
- **Visit on grand final day**: Heightened energy — all crew avatars are active even if nothing is running. Status: "Grand Final day. Everyone's watching."

### Streak Reactions

- **User agrees with Jeromelu 5+ times in a row**: Status text: "You're catching on." Jeromelu's avatar gives a brief approving nod.
- **User disagrees with Jeromelu 5+ times in a row**: "Contrarian. I can respect that." Slight smirk.
- **User's accuracy exceeds Jeromelu's over 10+ Remarks**: "You might be better at this than me. Don't let it go to your head." (Only shown once per season.)

### The 404 Page

If someone hits a broken link: Jeromelu's avatar with a confused expression. "This page doesn't exist. Even I make mistakes. But not this one — you typed the URL wrong."

### Long-Term Engagement

- **100th visit**: A subtle Stream card from the Archivist: "You've been here 100 times this season. That's dedication. Jeromelu appreciates the audience."
- **User who has reacted to every Remark in a round**: "You didn't miss a single call this round. That's commitment." Brief Jeromelu avatar thumbs-up.
