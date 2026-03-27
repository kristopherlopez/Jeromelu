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

export interface FeedItem {
  id: string;
  type: FeedItemType;
  text: string;
  timestamp: string; // ISO string
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
