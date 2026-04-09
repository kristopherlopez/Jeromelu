export type ArticleType =
  | "tips"
  | "totw"
  | "trades"
  | "captains"
  | "stocks"
  | "consensus";

export interface InsightListItem {
  kb_id: string;
  article_type: ArticleType;
  title: string;
  summary: string;
  effective_round: number;
  season: number;
  created_at: string;
  player_count: number;
}

export interface InsightListResponse {
  items: InsightListItem[];
  next_before: string | null;
}

export interface SourceAttribution {
  source_id: string;
  title: string;
  creator_name: string | null;
}

export interface InsightDetail {
  kb_id: string;
  article_type: ArticleType;
  title: string;
  content: string;
  effective_round: number;
  season: number;
  created_at: string;
  metadata: Record<string, unknown>;
  sources: SourceAttribution[];
}

export const ARTICLE_TYPE_LABELS: Record<ArticleType, string> = {
  tips: "SuperCoach Tips",
  totw: "Team of the Week",
  trades: "Trade Targets",
  captains: "Captain Picks",
  stocks: "Stocks Up / Down",
  consensus: "Podcast Consensus",
};

export const ARTICLE_TYPE_COLORS: Record<ArticleType, string> = {
  tips: "#b85c38",
  totw: "#4a9e6e",
  trades: "#5b7fc7",
  captains: "#9b59b6",
  stocks: "#d4a843",
  consensus: "#6c8b9e",
};
