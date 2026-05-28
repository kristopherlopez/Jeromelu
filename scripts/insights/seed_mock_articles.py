"""Seed mock insight articles for UI development.

Usage:
  python scripts/insights/seed_mock_articles.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "packages" / "shared"))

from datetime import UTC, datetime, timedelta

from jeromelu_shared.db import KnowledgeBase
from jeromelu_shared.db.session import SessionLocal

SEASON = 2026

MOCK_ARTICLES = [
    # Round 5
    {
        "kb_type": "article_tips",
        "title": "Round 5 SuperCoach Tips",
        "effective_round": 5,
        "hours_ago": 2,
        "metadata_json": {"article_type": "tips", "round": 5, "season": SEASON, "player_count": 12, "claim_count": 34},
        "content": """## The Big Calls

Round 5 is shaping up to be one of those weeks where the brave get rewarded and the cautious get left behind. Here's what I'm seeing.

### Captain Pick: Isaah Yeo

This isn't even close for me. Yeo at home against the Titans is as safe a captain pick as you'll get this season. His base stats are elite — averaging 62 base over the last three rounds — and Gold Coast's edge defence has been leaking points to second-rowers all year. Lock him in with the C, don't overthink it.

### Must-Have Trade Target: Bradman Best

If you don't have Best by now, you're behind. Price is still climbing ($485k, BE 38), his three-round average is 71, and the Knights have a dream run coming up. The pods are unanimous on this one — every source I've tracked this week has him as a buy.

### The Trap: Reece Walsh

I know, I know. He's Reece Walsh. But hear me out — he's carrying a niggle, the Broncos are playing Thursday which means short turnaround, and his breakeven has ballooned to 68. If he puts up a 40, that's a $30k price drop. The risk-reward isn't there this week. Hold if you have him, but don't you dare bring him in.

### Sneaky Differential: Terrell May

Only 8% ownership and averaging 58 over the last three rounds. The Roosters pack is humming and May is getting 65+ minutes consistently. At $412k with a breakeven of 32, he's printing money. The KingOfSC pod flagged him on Monday and I couldn't agree more.

### Players to Avoid

- **Dylan Edwards** — Bye round looming, breakeven 71, form dipping. Cash out now.
- **Jahrome Hughes** — Calf concern flagged at training. Even if he plays, limited minutes risk.
- **Cameron Murray** — Still building fitness. His PPM is elite when on, but 45-minute caps kill his ceiling.

---

## The Bottom Line

This is a week for conviction. Yeo captain, Best in your team, and start moving out anyone with byes in Round 6-7. The coaches who plan two weeks ahead are the ones lifting the trophy in September.

I've watched everything. I've read everyone. Make your moves.
""",
    },
    {
        "kb_type": "article_captains",
        "title": "Round 5 Captain Picks",
        "effective_round": 5,
        "hours_ago": 3,
        "metadata_json": {
            "article_type": "captains",
            "round": 5,
            "season": SEASON,
            "player_count": 5,
            "claim_count": 18,
        },
        "content": """## Top 5 Captain Picks — Round 5

### 1. Isaah Yeo (Panthers) — HIGH conviction

The safest pick of the round. Yeo's base stats are untouchable right now — 62 base average over three rounds, PPM of 1.12, and he's playing at home against the Titans. Gold Coast concede the most points to locks in the comp. Four of five pods I track have him as their #1 captain pick this week. Lock it in.

**Last 3 scores:** 78, 65, 71 | **Breakeven:** 44 | **Price:** $562k

### 2. Tom Trbojevic (Sea Eagles) — MEDIUM conviction

Turbo at Brookvale against the Cowboys is a mouthwatering matchup. When he's on, nobody in SuperCoach can match his ceiling. But that's the catch — *when he's on*. His floor is lower than Yeo's, and there's always the injury spectre. High upside, moderate risk.

**Last 3 scores:** 92, 34, 81 | **Breakeven:** 56 | **Price:** $621k

### 3. Patrick Carrigan (Broncos) — MEDIUM conviction

Carrigan has been a machine. Averaging 68 over five rounds with elite base stats and tackle counts that would make a spreadsheet blush. The short turnaround (Thursday game) is the only concern, but he's young and fit enough to handle it.

**Last 3 scores:** 72, 64, 69 | **Breakeven:** 48 | **Price:** $548k

### 4. Harry Grant (Storm) — LOW conviction

Grant's upside is obvious — when Melbourne click, he feeds off the attack stats. But the Warriors at home aren't the pushover they used to be, and Grant's base has dipped the last two weeks. He's a fine captain pick, just not my first choice.

**Last 3 scores:** 58, 82, 51 | **Breakeven:** 52 | **Price:** $595k

### 5. Bradman Best (Knights) — LOW conviction

A cheeky differential pick. Best is in career-best form and the matchup against the Tigers is elite. But captaining a centre is inherently riskier — their scoring is more volatile. If you're chasing in your league and need a point of difference, this is your play.

**Last 3 scores:** 74, 68, 71 | **Breakeven:** 38 | **Price:** $485k

---

## My Call

**Yeo. No hesitation.** The floor is 55, the ceiling is 90+, and the matchup is perfect. Don't get cute this week.
""",
    },
    {
        "kb_type": "article_totw",
        "title": "Round 4 Team of the Week",
        "effective_round": 4,
        "hours_ago": 48,
        "metadata_json": {"article_type": "totw", "round": 4, "season": SEASON, "player_count": 13, "claim_count": 0},
        "content": """## Round 4 Team of the Week

What a round. Some absolute monster scores, a few surprise packets, and one performance that had me checking the stats twice.

### Fullback: Dylan Edwards (Panthers) — 89

Edwards chose violence in Round 4. Two try assists, a linebreak, and a tackle bust count that had no right being that high for a fullback. This is the Edwards that wins you leagues. Enjoy it before the bye.

### Centres: Bradman Best (Knights) — 74, Herbie Farnworth (Dolphins) — 68

Best continues his ridiculous run. A try and two try assists from centre is elite production. Farnworth was quieter but still pumped out a 68 through pure base stats — 42 tackles in a tough arm-wrestle.

### Wingers: Zac Lomax (Dragons) — 72, Josh Addo-Carr (Bulldogs) — 65

Lomax is having a career year. His goal-kicking adds a floor that most wingers can only dream of. The Fox got on the end of two tries and looked sharp — value alert if he keeps this up.

### Five-Eighth: Sam Walker (Roosters) — 82

Walker was electric. Controlled the game from start to finish — two try assists, a forced dropout, and a 40/20. This is what you're paying $600k+ for.

### Halfback: Daly Cherry-Evans (Sea Eagles) — 76

DCE rolled back the years. His kicking game was immaculate and he ran for more metres than he has all season. A masterclass in halfback play.

### Hooker: Harry Grant (Storm) — 82

Grant from dummy half is a cheat code. 55 tackles, a try, and a try assist. When Melbourne are on, Grant is SuperCoach royalty.

### Props: James Fisher-Harris (Panthers) — 71, Payne Haas (Broncos) — 67

JFH doing JFH things — elite base, big minutes, zero fuss. Haas was strong off the bench with an 18-minute stint that produced 67. PPM merchants, both of them.

### Second Row: Isaah Yeo (Panthers) — 78, Angus Crichton (Roosters) — 72

Yeo's floor is absurd. Another 78 without even scoring a try. Crichton was excellent on the edge — two linebreaks and a tackle bust masterclass.

### Lock: Patrick Carrigan (Broncos) — 69

Carrigan just doesn't stop. 55 tackles, 62 base, and he's doing it every single week. The most reliable lock in SuperCoach.

---

## Honourable Mentions

- **Terrell May** (Roosters) — 64, sneaking into the conversation
- **Jahrome Hughes** (Storm) — 63, solid without being spectacular
- **Nicho Hynes** (Sharks) — 61, back to his best?
""",
    },
    {
        "kb_type": "article_trades",
        "title": "Round 5 Trade Targets",
        "effective_round": 5,
        "hours_ago": 5,
        "metadata_json": {
            "article_type": "trades",
            "round": 5,
            "season": SEASON,
            "player_count": 10,
            "claim_count": 22,
        },
        "content": """## Top 3 Buys

### 1. Bradman Best (Knights) — $485k, BE 38

I sound like a broken record but I'll keep saying it until everyone owns him. Best is averaging 71 over three rounds, his breakeven is 38 (meaning he prints money every week), and the Knights have Titans, Tigers, Cowboys in the next three. That's a dream run for a centre pumping out these numbers. Three of five pods agree — get him in.

### 2. Terrell May (Roosters) — $412k, BE 32

The ultimate value play right now. Only 8% owned, averaging 58, and his breakeven is 32. May is getting genuine first-choice minutes in a Roosters pack that's humming. At his price, he's essentially free money for the next 4-5 weeks. KingOfSC flagged him Monday and the NRLSCTalk boys followed on Wednesday.

### 3. Zac Lomax (Dragons) — $498k, BE 41

Lomax with goal-kicking duties is a different beast. His floor is 45+ just from kicks, and when he bags a try or assist on top, you're looking at 70+. He's risen $46k already this season and there's more to come. The only concern is a tricky Round 7 matchup against Melbourne, but that's two weeks away.

---

## Top 3 Sells

### 1. Dylan Edwards (Panthers) — $612k, BE 71

This hurts to say after his Round 4 heroics, but Edwards has a bye in Round 6 and his breakeven has crept to 71. Cash him out at peak value and reinvest. You can always bring him back post-byes.

### 2. Cameron Murray (Rabbitohs) — $445k, BE 58

Murray's minute caps are killing his SuperCoach value. He's averaging 52 over three rounds — elite per minute, but 45-minute stints mean a ceiling of about 60. At $445k, that money is better spent elsewhere. NRLSCTalk had him as their top sell this week.

### 3. Jahrome Hughes (Storm) — $578k, BE 62

Calf niggle flagged at training, short turnaround with a Friday game, and his form has dipped the last two weeks. Hughes is still a gun when fit, but the risk of a 20-minute cameo or late withdrawal is too high. Park the cash and reassess next week.

---

## The Play

Best in, Edwards out. That's the move of the round. You bank the $127k price difference and upgrade your forward pack.
""",
    },
    {
        "kb_type": "article_stocks",
        "title": "Round 5 Stocks Up / Stocks Down",
        "effective_round": 5,
        "hours_ago": 6,
        "metadata_json": {
            "article_type": "stocks",
            "round": 5,
            "season": SEASON,
            "player_count": 10,
            "claim_count": 15,
        },
        "content": """## Stocks Up

### Bradman Best — $485k (+$32k this round)

Three rounds of 65+ scores. Price rising every week. Dream fixture ahead. Podcast consensus is unanimously bullish. Best is the hottest property in SuperCoach right now and it's not close.

### Terrell May — $412k (+$18k this round)

Quietly building a case as the value pick of the season. His minutes are up, his output is consistent, and at 8% ownership he's the ultimate differential. Two pods have flagged him this week — expect ownership to spike.

### Zac Lomax — $498k (+$22k this round)

Goal-kicking wingers are SuperCoach gold and Lomax is proving it every week. His floor is elite and the Dragons are playing with more structure than they have in years. Trending in the right direction across every metric.

### Sam Walker — $602k (+$15k this round)

Walker's Round 4 masterclass reminded everyone why he's a top-4 half. His PPM is back above 1.0 and the Roosters' attack is clicking. Sentiment has swung sharply positive after a shaky start to the season.

---

## Stocks Down

### Cameron Murray — $445k (-$12k this round)

The minute cap is a killer. Murray's per-minute stats are among the best in the game, but 45-minute stints cap his ceiling at ~60. Three pods have shifted from hold to sell this week. The market is losing patience.

### Dylan Edwards — $612k (flat, but BE 71)

Edwards is at peak price with a bye looming. His breakeven has crept to 71 — meaning he needs a 71+ score just to maintain value. The smart money is cashing out now and reinvesting. Stocks aren't crashing, but the risk is heavily tilted to the downside.

### Jahrome Hughes — $578k (-$8k this round)

Calf concern + form dip + short turnaround = sell signal. Hughes averaged 78 in the first three rounds but has dropped to 55 average over the last two. If the calf flares up and he misses, that's a $30k+ hit.

### Reece Walsh — $590k (-$5k this round)

Walsh isn't bad — but he's not $590k good right now. His breakeven is 68 and the Broncos' attack has been inconsistent. Two pods have him as a hold, one as a sell. Nobody is calling him a buy, which tells you everything.

### Nathan Cleary — $645k (-$18k this round)

The elephant in the room. Cleary's been managed since his return and the Panthers seem content with 55-minute stints. At $645k with a breakeven of 74, he's a luxury you can't afford unless he's playing 80. Sentiment is split — some pods still believe, others have moved on.
""",
    },
    {
        "kb_type": "article_consensus",
        "title": "Round 5 Podcast Consensus",
        "effective_round": 5,
        "hours_ago": 8,
        "metadata_json": {
            "article_type": "consensus",
            "round": 5,
            "season": SEASON,
            "player_count": 15,
            "claim_count": 42,
        },
        "content": """## What The Pods Are Saying — Round 5

I've tracked five major SuperCoach podcasts this week. Here's where they agree, where they diverge, and what it means for your team.

### Sources Tracked

- **KingOfSC** (Monday episode)
- **NRLSCTalk** (Tuesday episode)
- **SC Playbook** (Wednesday episode)
- **The SuperCoach Clubhouse** (Monday episode)
- **Pod of the Century** (Tuesday episode)

---

### Universal Agreement (5/5 pods)

**Isaah Yeo — Captain** | Every single pod has Yeo as their top captain pick this week. That kind of unanimity is rare. When the entire analyst community agrees, you listen.

**Bradman Best — Buy** | All five pods flagged Best as a must-have. The consensus is that if you don't own him by Round 5, you're actively falling behind.

### Strong Consensus (4/5 pods)

**Dylan Edwards — Sell** | Four of five say cash out now before the bye. Only SC Playbook disagrees, arguing his Round 4 score (89) justifies holding one more week. I side with the majority — peak value, sell.

**Terrell May — Buy** | Four pods flagged May as the value pick of the round. Pod of the Century was the holdout, noting his tackle bust numbers are inconsistent. Fair point, but at $412k the risk is minimal.

### Split Opinion (3/2)

**Jahrome Hughes — Sell vs Hold** | Three pods (KingOfSC, NRLSCTalk, Clubhouse) say sell based on the calf concern. SC Playbook and Pod of the Century say hold — arguing one soft tissue scare shouldn't trigger a panic sell. My take: the risk outweighs the reward this week. Sell.

**Harry Grant — Captain vs Safe Hold** | Three pods have Grant in their top 3 captain picks, two don't mention him at all. The Warriors matchup is polarising — some see it as a trap game, others see easy points. I have him at #4 this week.

### The Contrarian Calls

**SC Playbook** is the most bullish pod on Nathan Cleary this week, arguing the Panthers will unleash him for 70+ minutes against the Titans. Nobody else agrees. Bold call — I'm not buying it.

**KingOfSC** is pushing Nicho Hynes as a sneaky captain pick. The reasoning: Sharks at home against a depleted Raiders. It's not crazy, but it's a risk most coaches won't take.

---

## Consensus Summary

| Player | Buy | Sell | Hold | Captain |
|--------|-----|------|------|---------|
| Isaah Yeo | — | — | 5 | **5** |
| Bradman Best | **5** | — | — | — |
| Dylan Edwards | — | **4** | 1 | — |
| Terrell May | **4** | — | 1 | — |
| Jahrome Hughes | — | **3** | 2 | — |
| Harry Grant | — | — | 2 | **3** |
| Cameron Murray | — | **3** | 2 | — |
| Nathan Cleary | — | 2 | **3** | — |
| Reece Walsh | — | 1 | **4** | — |

## My Take

Follow the consensus on Yeo (captain) and Best (buy). The Edwards sell is the right move even if it hurts. And watch May — he's the sneaky pick that could define your season.
""",
    },
    # Round 4 extra articles
    {
        "kb_type": "article_tips",
        "title": "Round 4 SuperCoach Tips",
        "effective_round": 4,
        "hours_ago": 170,
        "metadata_json": {"article_type": "tips", "round": 4, "season": SEASON, "player_count": 10, "claim_count": 28},
        "content": """## Round 4 Preview

### Captain Pick: Tom Trbojevic

Turbo at home against a leaky Cowboys defence is the play. When Des has Manly humming at Brookvale, Trbojevic is unstoppable. His ceiling is the highest in the game — we saw 92 in Round 2 and this matchup screams another big one.

### Trade Target: Bradman Best

I'm banging this drum again. Best is averaging 68 after three rounds and his price is still climbing. The Knights have found structure under their new coach and Best is the chief beneficiary. Get him in before the price locks you out.

### Watch Out For

- **Short turnaround games** — Three teams on 5-day breaks this round. Check your squad for anyone backing up Thursday to Monday.
- **Payne Haas** off the bench — Broncos are managing his minutes. If you're expecting 70, you might get 45.

### Avoid

- **Latrell Mitchell** — Still building match fitness. His PPM is fine but the minutes aren't there yet. Give him two more weeks.
- **Luke Brooks** — New club, still finding his feet. Breakeven is 52 and he's averaging 38. Cut him.

---

I watched six hours of tape this week. Trust the process. Make your moves.
""",
    },
    {
        "kb_type": "article_consensus",
        "title": "Round 4 Podcast Consensus",
        "effective_round": 4,
        "hours_ago": 175,
        "metadata_json": {
            "article_type": "consensus",
            "round": 4,
            "season": SEASON,
            "player_count": 12,
            "claim_count": 38,
        },
        "content": """## What The Pods Are Saying — Round 4

### Universal Agreement

**Tom Trbojevic — Captain** | 5/5 pods. Brookvale + Cowboys = points. Simple maths.

**Bradman Best — Buy** | 4/5 pods. The lone holdout (Pod of the Century) argues his price has already risen enough. They're wrong.

### The Debate

**Patrick Carrigan — Captain contender** | 3 pods have him in their top 3. The other 2 prefer Grant. Carrigan's consistency is undeniable but his ceiling is lower than the premium options.

**Cameron Murray — Buy or Avoid?** | This is the most polarising call of the week. KingOfSC and SC Playbook say buy the dip — his per-minute stats are elite. NRLSCTalk and Clubhouse say avoid until the minute cap lifts. I'm in the avoid camp.

### Sleeper Pick

**SC Playbook** flagged Terrell May as one to watch. At $394k with rising minutes, he could be a sneaky buy in the next 2-3 weeks. Filing that one away.

---

| Player | Buy | Sell | Hold | Captain |
|--------|-----|------|------|---------|
| Tom Trbojevic | — | — | 5 | **5** |
| Bradman Best | **4** | — | 1 | — |
| Patrick Carrigan | — | — | 5 | **3** |
| Cameron Murray | 2 | — | **3** | — |
| Harry Grant | — | — | 5 | **2** |
""",
    },
]


def main():
    db = SessionLocal()
    try:
        # Clean existing mock articles
        db.query(KnowledgeBase).filter(KnowledgeBase.kb_type.like("article_%")).delete(synchronize_session=False)
        db.commit()
        print("Cleared existing articles")

        now = datetime.now(UTC)
        count = 0

        for article in MOCK_ARTICLES:
            entry = KnowledgeBase(
                kb_type=article["kb_type"],
                title=article["title"],
                content=article["content"],
                effective_round=article["effective_round"],
                season=SEASON,
                metadata_json=article["metadata_json"],
                source_claim_ids=[],
                created_at=now - timedelta(hours=article["hours_ago"]),
            )
            db.add(entry)
            count += 1
            print(f"  + {article['title']}")

        db.commit()
        print(f"\nSeeded {count} mock articles")

    finally:
        db.close()


if __name__ == "__main__":
    main()
