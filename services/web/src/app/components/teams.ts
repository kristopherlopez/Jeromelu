export interface TeamColours {
  slug: string;
  name: string;
  short: string;
  primary: string;
  secondary: string;
}

export const TEAMS: TeamColours[] = [
  { slug: "brisbane_broncos",          name: "Brisbane Broncos",            short: "Broncos",     primary: "#6F0F2E", secondary: "#FCB63B" },
  { slug: "canterbury_bulldogs",       name: "Canterbury Bulldogs",         short: "Bulldogs",    primary: "#005BBB", secondary: "#FFFFFF" },
  { slug: "canberra_raiders",          name: "Canberra Raiders",            short: "Raiders",     primary: "#97D700", secondary: "#1B2854" },
  { slug: "cronulla_sharks",           name: "Cronulla Sharks",             short: "Sharks",      primary: "#00A0DE", secondary: "#000000" },
  { slug: "dolphins",                  name: "Dolphins",                    short: "Dolphins",    primary: "#BE0F34", secondary: "#00A4A7" },
  { slug: "gold_coast_titans",         name: "Gold Coast Titans",           short: "Titans",      primary: "#2DBDDD", secondary: "#C9A76A" },
  { slug: "manly_sea_eagles",          name: "Manly Sea Eagles",            short: "Sea Eagles",  primary: "#6F0F2E", secondary: "#FFFFFF" },
  { slug: "melbourne_storm",           name: "Melbourne Storm",             short: "Storm",       primary: "#1B1464", secondary: "#5E2D91" },
  { slug: "newcastle_knights",         name: "Newcastle Knights",           short: "Knights",     primary: "#DA1A32", secondary: "#003478" },
  { slug: "new_zealand_warriors",      name: "New Zealand Warriors",        short: "Warriors",    primary: "#0D318D", secondary: "#03673F" },
  { slug: "north_queensland_cowboys",  name: "North Queensland Cowboys",    short: "Cowboys",     primary: "#002952", secondary: "#FBB034" },
  { slug: "parramatta_eels",           name: "Parramatta Eels",             short: "Eels",        primary: "#003F87", secondary: "#FBE122" },
  { slug: "penrith_panthers",          name: "Penrith Panthers",            short: "Panthers",    primary: "#1B1B1B", secondary: "#00A39B" },
  { slug: "south_sydney_rabbitohs",    name: "South Sydney Rabbitohs",      short: "Rabbitohs",   primary: "#007A33", secondary: "#B81235" },
  { slug: "st_george_illawarra_dragons", name: "St George Illawarra Dragons", short: "Dragons",   primary: "#DC1F26", secondary: "#FFFFFF" },
  { slug: "sydney_roosters",           name: "Sydney Roosters",             short: "Roosters",    primary: "#DA1A32", secondary: "#002B5B" },
  { slug: "wests_tigers",              name: "Wests Tigers",                short: "Tigers",      primary: "#1B1B1B", secondary: "#F58220" },
];

export const DEFAULT_TEAM_SLUG = "wests_tigers";

export const TEAM_BY_SLUG: Record<string, TeamColours> = Object.fromEntries(
  TEAMS.map((t) => [t.slug, t]),
);

export function getTeam(slug: string | null | undefined): TeamColours {
  if (slug && TEAM_BY_SLUG[slug]) return TEAM_BY_SLUG[slug];
  return TEAM_BY_SLUG[DEFAULT_TEAM_SLUG];
}
