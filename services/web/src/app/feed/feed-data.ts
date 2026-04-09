export type FeedItemType =
  | "watching"
  | "signal"
  | "thinking"
  | "prediction"
  | "action"
  | "review"
  | "sys"
  | "question"
  | "answer";

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

export interface FeedUser {
  name: string;
  color?: string; // hex color for username display (Twitch-style)
}

export interface FeedItem {
  id: string;
  type: FeedItemType;
  text: string;
  timestamp: string; // ISO string
  user?: FeedUser; // who asked (for question items in the shared feed)
  players?: PlayerRef[];
  source?: SourceRef;
  sources?: SourceRef[];
  prediction?: PredictionResolution;
}

export interface FeedResponse {
  items: FeedItem[];
  next_before: string | null;
}

export type TemperatureMode = "straight" | "sharp" | "roast";

export interface FeedAskRequest {
  question: string;
  temperature: TemperatureMode;
}

export interface FeedAskResponse {
  question_item: FeedItem;
  answer_item: FeedItem;
}
