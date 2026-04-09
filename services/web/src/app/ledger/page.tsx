import LedgerClient from "./LedgerClient";
import { MOCK_LEDGER } from "./ledger-data";

export const metadata = {
  title: "The Ledger | Jaromelu",
  description:
    "Predictions, outcomes, receipts. Every call tracked. Every source ranked.",
};

export default function LedgerPage() {
  // TODO: Replace with API fetch once /api/ledger exists
  return <LedgerClient data={MOCK_LEDGER} />;
}
