import { apiFetch } from "@/lib/api";
import SquadClient from "./SquadClient";
import type { SquadResponse } from "./squad-data";

export const metadata = {
  title: "My Squad | Jeromelu",
  description: "Here's my squad. Here's the logic. Judge me.",
};

export const dynamic = "force-dynamic";

export default async function SquadPage() {
  let data: SquadResponse | null = null;
  try {
    data = await apiFetch<SquadResponse>("/api/squad");
  } catch {
    // API may not be running
  }
  return <SquadClient data={data} />;
}
