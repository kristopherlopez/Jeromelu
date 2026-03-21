import FeedClient from "./FeedClient";
import { DUMMY_FEED } from "./feed-data";

export const metadata = {
  title: "The Feed | Jeromelu",
  description: "What I'm seeing, thinking, and doing.",
};

export default function FeedPage() {
  // TODO: Replace with real API fetch once Feed pipeline is live
  return <FeedClient items={DUMMY_FEED} />;
}
