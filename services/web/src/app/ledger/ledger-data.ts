/* ── Types ── */

export type PredictionStatus = "pending" | "correct" | "wrong";
export type PredictionCategory = "captain" | "trade" | "score" | "bold";
export type PredictorKind = "ai" | "expert" | "podcast" | "community";

export interface Predictor {
  id: string;
  name: string;
  kind: PredictorKind;
}

export interface Prediction {
  id: string;
  text: string;
  status: PredictionStatus;
  category: PredictionCategory;
  confidence: "high" | "med" | "low";
  predictor: Predictor;
  round: string; // e.g. "R7"
  timestamp: string; // ISO
}

export interface ScoreboardEntry {
  predictor: Predictor;
  accuracy: number; // 0–100
  totalCalls: number;
  streak: string; // e.g. "W5", "L2", "—"
  streakType: "hot" | "cold" | "neutral";
  trend: "up" | "down" | "flat";
}

export interface HotZone {
  predictor: Predictor;
  scope: string; // e.g. "Parramatta Eels players"
  accuracy: number;
  overallDelta: number; // how much above their overall
  calls: number;
  correct: number;
}

export interface CategoryBreakdown {
  category: PredictionCategory;
  accuracy: number;
  totalCalls: number;
  bestPredictor: Predictor;
  bestAccuracy: number;
}

export interface LedgerSummary {
  totalPredictions: number;
  totalSources: number;
  avgAccuracy: number;
  avgAccuracyDelta: number; // vs last season
  currentRound: string;
  season: string;
  pending: number;
}

export interface LedgerResponse {
  summary: LedgerSummary;
  scoreboard: ScoreboardEntry[];
  predictions: Prediction[];
  hotZones: HotZone[];
  categories: CategoryBreakdown[];
}

/* ── Category display labels ── */

export const CATEGORY_LABELS: Record<PredictionCategory, string> = {
  captain: "Captain Picks",
  trade: "Trades",
  score: "Score Tips",
  bold: "Bold Calls",
};

export const KIND_LABELS: Record<PredictorKind, string> = {
  ai: "AI",
  expert: "Expert",
  podcast: "Podcast",
  community: "Community",
};

/* ── Mock data ── */

const PREDICTORS: Record<string, Predictor> = {
  jaromelu: { id: "jaromelu", name: "Jaromelu", kind: "ai" },
  kingofsc: { id: "kingofsc", name: "KingOfSC", kind: "expert" },
  scplaybook: { id: "scplaybook", name: "SC Playbook", kind: "podcast" },
  tomfrommelb: { id: "tomfrommelb", name: "TomFromMelb", kind: "community" },
  nrlmole: { id: "nrlmole", name: "NRL Mole", kind: "podcast" },
  coachdave: { id: "coachdave", name: "CoachDave", kind: "expert" },
  triplemnrl: { id: "triplemnrl", name: "TripleMNRL", kind: "podcast" },
};

export const MOCK_LEDGER: LedgerResponse = {
  summary: {
    totalPredictions: 847,
    totalSources: 12,
    avgAccuracy: 64.2,
    avgAccuracyDelta: 2.1,
    currentRound: "R7",
    season: "2026",
    pending: 38,
  },
  scoreboard: [
    { predictor: PREDICTORS.jaromelu, accuracy: 72.4, totalCalls: 152, streak: "W5", streakType: "hot", trend: "up" },
    { predictor: PREDICTORS.kingofsc, accuracy: 69.1, totalCalls: 186, streak: "W3", streakType: "hot", trend: "flat" },
    { predictor: PREDICTORS.scplaybook, accuracy: 65.8, totalCalls: 134, streak: "—", streakType: "neutral", trend: "up" },
    { predictor: PREDICTORS.tomfrommelb, accuracy: 62.0, totalCalls: 89, streak: "L2", streakType: "cold", trend: "down" },
    { predictor: PREDICTORS.nrlmole, accuracy: 58.3, totalCalls: 96, streak: "L4", streakType: "cold", trend: "down" },
    { predictor: PREDICTORS.coachdave, accuracy: 54.7, totalCalls: 112, streak: "L1", streakType: "cold", trend: "down" },
    { predictor: PREDICTORS.triplemnrl, accuracy: 51.2, totalCalls: 78, streak: "—", streakType: "neutral", trend: "flat" },
  ],
  predictions: [
    { id: "p1", text: "Ponga to score 85+ in Round 7 — backs are flying this week", status: "pending", category: "captain", confidence: "high", predictor: PREDICTORS.jaromelu, round: "R7", timestamp: "2026-04-08T09:00:00Z" },
    { id: "p2", text: "Sell Haas before Round 6 — price peak incoming after soft draw", status: "correct", category: "trade", confidence: "med", predictor: PREDICTORS.kingofsc, round: "R5", timestamp: "2026-03-25T14:30:00Z" },
    { id: "p3", text: "Cleary back to 70+ SuperCoach points post-Origin — form is locked in", status: "correct", category: "score", confidence: "high", predictor: PREDICTORS.jaromelu, round: "R5", timestamp: "2026-03-24T10:00:00Z" },
    { id: "p4", text: "Broncos to cover -4.5 against Warriors — they'll blow them off the park", status: "wrong", category: "bold", confidence: "high", predictor: PREDICTORS.scplaybook, round: "R4", timestamp: "2026-03-18T08:00:00Z" },
    { id: "p5", text: "Tedesco captain in Round 4 — he feasts on the Tigers every time", status: "correct", category: "captain", confidence: "med", predictor: PREDICTORS.jaromelu, round: "R4", timestamp: "2026-03-17T11:00:00Z" },
    { id: "p6", text: "Luai to outscore Cleary over the next 3 rounds — watch the minutes", status: "wrong", category: "bold", confidence: "low", predictor: PREDICTORS.nrlmole, round: "R3", timestamp: "2026-03-10T16:00:00Z" },
    { id: "p7", text: "Mitchell Moses top-5 halfback by Round 10 — trust the process", status: "pending", category: "bold", confidence: "med", predictor: PREDICTORS.tomfrommelb, round: "R6", timestamp: "2026-04-01T13:00:00Z" },
    { id: "p8", text: "Grant to average 60+ in the next 4 rounds — hooker workload is peaking", status: "correct", category: "score", confidence: "high", predictor: PREDICTORS.coachdave, round: "R3", timestamp: "2026-03-09T07:00:00Z" },
    { id: "p9", text: "Papenhuijzen VC loop every week until Origin — set and forget", status: "pending", category: "captain", confidence: "high", predictor: PREDICTORS.triplemnrl, round: "R6", timestamp: "2026-03-31T09:00:00Z" },
    { id: "p10", text: "Hold Crichton through Round 8 — back row premiums are thin", status: "correct", category: "trade", confidence: "med", predictor: PREDICTORS.jaromelu, round: "R5", timestamp: "2026-03-23T12:00:00Z" },
    { id: "p11", text: "Panthers backline to average 55+ as a unit through Rounds 5-8", status: "wrong", category: "score", confidence: "low", predictor: PREDICTORS.nrlmole, round: "R5", timestamp: "2026-03-22T15:00:00Z" },
    { id: "p12", text: "Dolphins to upset Roosters in Round 6 — home ground advantage", status: "correct", category: "bold", confidence: "low", predictor: PREDICTORS.tomfrommelb, round: "R6", timestamp: "2026-03-30T10:00:00Z" },
  ],
  hotZones: [
    { predictor: PREDICTORS.coachdave, scope: "Parramatta Eels players", accuracy: 83.3, overallDelta: 28.6, calls: 18, correct: 15 },
    { predictor: PREDICTORS.nrlmole, scope: "Captain picks — Round 1–4", accuracy: 87.5, overallDelta: 29.2, calls: 8, correct: 7 },
    { predictor: PREDICTORS.triplemnrl, scope: "Fullback trades", accuracy: 80.0, overallDelta: 28.8, calls: 10, correct: 8 },
    { predictor: PREDICTORS.tomfrommelb, scope: "Melbourne Storm players", accuracy: 76.9, overallDelta: 14.9, calls: 13, correct: 10 },
    { predictor: PREDICTORS.jaromelu, scope: "Bold calls — prop forwards", accuracy: 90.0, overallDelta: 17.6, calls: 10, correct: 9 },
    { predictor: PREDICTORS.scplaybook, scope: "Score tips — hookers", accuracy: 78.6, overallDelta: 12.8, calls: 14, correct: 11 },
  ],
  categories: [
    { category: "captain", accuracy: 68.3, totalCalls: 241, bestPredictor: PREDICTORS.jaromelu, bestAccuracy: 74.1 },
    { category: "trade", accuracy: 71.2, totalCalls: 189, bestPredictor: PREDICTORS.kingofsc, bestAccuracy: 76.8 },
    { category: "score", accuracy: 59.4, totalCalls: 278, bestPredictor: PREDICTORS.scplaybook, bestAccuracy: 63.2 },
    { category: "bold", accuracy: 48.6, totalCalls: 139, bestPredictor: PREDICTORS.jaromelu, bestAccuracy: 55.0 },
  ],
};
