export type TemperatureMode = "straight" | "sharp" | "roast";

export interface ChatMessage {
  id: string;
  role: "user" | "jeromelu";
  text: string;
  sources?: { sourceId: string; title: string; creator?: string }[];
  players?: { entityId: string; name: string }[];
}

export interface AskRequest {
  question: string;
  temperature: TemperatureMode;
}

export interface AskResponse {
  answer: string;
  sources: { source_id: string; title: string; creator_name?: string }[];
  players: { entity_id: string; name: string }[];
  kb_entries_used: string[];
}
