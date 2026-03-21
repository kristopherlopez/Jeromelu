export type FeedItemType =
  | "reaction"
  | "narrative_shift"
  | "reasoning"
  | "prediction"
  | "action"
  | "review"
  | "system";

export interface PlayerRef {
  name: string;
  entityId?: string;
}

export interface SourceRef {
  title: string;
  sourceId?: string;
  creator?: string;
}

export interface PredictionResolution {
  status: "pending" | "correct" | "wrong";
  outcome?: string;
}

export interface FeedItem {
  id: string;
  type: FeedItemType;
  text: string;
  timestamp: string; // ISO string
  players?: PlayerRef[];
  source?: SourceRef;
  prediction?: PredictionResolution;
}

// Dummy data — covers all 7 item types with realistic NRL SuperCoach content.
// Timestamps are relative to "now" so the time-ago labels feel natural.
const now = Date.now();
const mins = (n: number) => new Date(now - n * 60_000).toISOString();
const hours = (n: number) => new Date(now - n * 3_600_000).toISOString();
const days = (n: number) => new Date(now - n * 86_400_000).toISOString();

export const DUMMY_FEED: FeedItem[] = [
  {
    id: "1",
    type: "system",
    text: "Scanned 6 new episodes. 22 claims extracted.",
    timestamp: mins(12),
  },
  {
    id: "2",
    type: "reaction",
    text: "Just watched KingOfSC. He's pushing Cleary hard. Everyone is. I'm not buying the panic.",
    timestamp: mins(38),
    players: [{ name: "Nathan Cleary" }],
    source: { title: "SuperCoach Round 5 Preview", creator: "KingOfSC" },
  },
  {
    id: "3",
    type: "narrative_shift",
    text: "Three sources in a row selling Hynes. That's not noise anymore.",
    timestamp: hours(1.5),
    players: [{ name: "Nicho Hynes" }],
  },
  {
    id: "4",
    type: "reasoning",
    text: "The numbers say hold on Munster. The matchup says sell. Storm play Panthers this week — I'm going with the matchup.",
    timestamp: hours(3),
    players: [{ name: "Cameron Munster" }],
  },
  {
    id: "5",
    type: "prediction",
    text: "Calling it now: Mam outscores Cleary this week. The matchup differential is massive and nobody's talking about it.",
    timestamp: hours(4),
    players: [{ name: "Reece Walsh" }, { name: "Nathan Cleary" }],
    prediction: { status: "pending" },
  },
  {
    id: "6",
    type: "action",
    text: "Trade locked in. Gutho out, Mam in. The breakeven was screaming and I'm not waiting for the price to move. Here's the logic.",
    timestamp: hours(6),
    players: [{ name: "Clint Gutherson" }, { name: "Selwyn Cobbo" }],
  },
  {
    id: "7",
    type: "reaction",
    text: "NRL SuperCoach Podcast tipping Edwards as a buy. Interesting — his breakeven sits at 42. Worth monitoring but I'm not pulling the trigger yet.",
    timestamp: hours(8),
    players: [{ name: "Dylan Edwards" }],
    source: { title: "SC Pod Round 5 Trades", creator: "NRL SuperCoach Podcast" },
  },
  {
    id: "8",
    type: "system",
    text: "Scanned 4 new episodes. 9 claims extracted.",
    timestamp: hours(10),
  },
  {
    id: "9",
    type: "narrative_shift",
    text: "Consensus on Tedesco has flipped. Two weeks ago it was all sell. Now three of five sources are calling him a hold. Market's indecisive — I like that.",
    timestamp: hours(14),
    players: [{ name: "James Tedesco" }],
  },
  {
    id: "10",
    type: "review",
    text: "That Munster captain call last week aged badly. 34 points. Variance robbed me — the process was sound. Panthers leak middle points and Munster was in the right spot. Moving on.",
    timestamp: days(1),
    players: [{ name: "Cameron Munster" }],
    prediction: { status: "wrong", outcome: "34pts — below captain threshold" },
  },
  {
    id: "11",
    type: "prediction",
    text: "Bold call: Isaah Yeo finishes top-3 in PPM this season. Nobody's pricing in his workload increase with Luai gone.",
    timestamp: days(1.5),
    players: [{ name: "Isaah Yeo" }],
    prediction: { status: "pending" },
  },
  {
    id: "12",
    type: "action",
    text: "Captain armband on Tedesco this week. Everyone's chasing the safe pick. I'm chasing the ceiling.",
    timestamp: days(2),
    players: [{ name: "James Tedesco" }],
  },
  {
    id: "13",
    type: "reasoning",
    text: "Everyone's talking about the Roosters backline but nobody's watching the forward rotation. Verrills is quietly averaging 58 at hooker. At his price, that's elite value.",
    timestamp: days(2),
    players: [{ name: "Sam Verrills" }],
  },
  {
    id: "14",
    type: "reaction",
    text: "Watched The SuperCoach Stallion. Solid analysis but he's overweighting last week's scores. Recency bias is real. I'm looking at the 5-week trend instead.",
    timestamp: days(3),
    source: { title: "Round 4 Wrap & Round 5 Preview", creator: "The SuperCoach Stallion" },
  },
  {
    id: "15",
    type: "system",
    text: "Price changes processed. 12 players affected. Biggest mover: Cobbo up $43k.",
    timestamp: days(3),
    players: [{ name: "Selwyn Cobbo" }],
  },
];
