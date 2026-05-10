export function extractVideoId(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    if (u.hostname.includes("youtu.be")) return u.pathname.slice(1);
    if (u.pathname.startsWith("/shorts/")) return u.pathname.split("/")[2] ?? null;
    return u.searchParams.get("v");
  } catch {
    return null;
  }
}
