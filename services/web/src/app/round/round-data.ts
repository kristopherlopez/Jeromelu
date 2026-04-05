export interface CrewAgent {
  id: string;
  name: string;
  icon: string;
  status: "active" | "dormant";
  action: string | null;
  last_activity: {
    summary: string;
    timestamp: string;
    activity_type: string;
  } | null;
  next_run: string;
}

export interface CrewStatusResponse {
  agents: CrewAgent[];
}

export interface ActivityLogEntry {
  activity_id: string;
  agent_id: string;
  agent_name: string;
  activity_type: string;
  summary: string;
  detail_json: Record<string, unknown>;
  created_at: string;
}

export interface ConsensusPlayer {
  entity_id: string;
  name: string;
  buy: number;
  sell: number;
  hold: number;
  captain: number;
  avoid: number;
  breakout: number;
  matchup_edge: number;
}

export interface RoundSource {
  source_id: string;
  title: string;
  creator_name: string | null;
  claim_count: number;
}

export interface RoundSignal {
  total_claims: number;
  buy: number;
  sell: number;
  hold: number;
  captain: number;
  avoid: number;
  breakout: number;
  matchup_edge: number;
}

export interface RoundOverviewResponse {
  round: number;
  season: number;
  status: "pending" | "in_progress" | "complete";
  crew_summary: Record<string, { completed: number; failed: number; name: string }>;
  signal: RoundSignal;
  consensus: ConsensusPlayer[];
  sources: RoundSource[];
  activity_log: ActivityLogEntry[];
}
