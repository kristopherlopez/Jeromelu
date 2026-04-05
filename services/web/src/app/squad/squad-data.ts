export interface PlayerInfo {
  entity_id: string;
  name: string;
  team: string | null;
  price: number | null;
  avg_score: number | null;
  last_score: number | null;
  price_change: number | null;
}

export interface ConsensusInfo {
  buy: number;
  sell: number;
  hold: number;
  captain: number;
  avoid: number;
}

export interface SquadSlot {
  slot_index: number;
  position: string;
  is_bench: boolean;
  player: PlayerInfo;
  is_captain: boolean;
  is_vice_captain: boolean;
  rationale: string | null;
  conviction: "low" | "medium" | "high";
  added_round: number | null;
  consensus: ConsensusInfo;
}

export interface CaptainPick {
  entity_id: string;
  name: string;
  rationale: string | null;
  conviction: "low" | "medium" | "high";
}

export interface TradeEntry {
  round: number;
  player_out: string;
  player_in: string;
  rationale: string | null;
  created_at: string;
}

export interface SquadPlan {
  text: string;
  round: number | null;
}

export interface SquadResponse {
  roster: SquadSlot[];
  captain: CaptainPick | null;
  recent_trades: TradeEntry[];
  plan: SquadPlan | null;
  season: number;
  current_round: number;
}
