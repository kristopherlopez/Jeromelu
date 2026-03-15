const fs = require('fs');

const data = require('./scraped_players_api_raw.json');

// Map SC team abbrevs to our yaml team keys and full names
const TEAM_MAP = {
  BRO: { key: 'brisbane_broncos', name: 'Brisbane Broncos', short: 'Broncos' },
  BUL: { key: 'canterbury_bulldogs', name: 'Canterbury-Bankstown Bulldogs', short: 'Bulldogs' },
  CBR: { key: 'canberra_raiders', name: 'Canberra Raiders', short: 'Raiders' },
  SHA: { key: 'cronulla_sharks', name: 'Cronulla-Sutherland Sharks', short: 'Sharks' },
  DOL: { key: 'dolphins', name: 'Dolphins', short: 'Dolphins' },
  GCT: { key: 'gold_coast_titans', name: 'Gold Coast Titans', short: 'Titans' },
  MNL: { key: 'manly_sea_eagles', name: 'Manly-Warringah Sea Eagles', short: 'Sea Eagles' },
  MEL: { key: 'melbourne_storm', name: 'Melbourne Storm', short: 'Storm' },
  NEW: { key: 'newcastle_knights', name: 'Newcastle Knights', short: 'Knights' },
  NQC: { key: 'north_queensland_cowboys', name: 'North Queensland Cowboys', short: 'Cowboys' },
  PAR: { key: 'parramatta_eels', name: 'Parramatta Eels', short: 'Eels' },
  PTH: { key: 'penrith_panthers', name: 'Penrith Panthers', short: 'Panthers' },
  STH: { key: 'south_sydney_rabbitohs', name: 'South Sydney Rabbitohs', short: 'Rabbitohs' },
  STG: { key: 'st_george_dragons', name: 'St George Illawarra Dragons', short: 'Dragons' },
  SYD: { key: 'sydney_roosters', name: 'Sydney Roosters', short: 'Roosters' },
  NZL: { key: 'new_zealand_warriors', name: 'New Zealand Warriors', short: 'Warriors' },
  WST: { key: 'wests_tigers', name: 'Wests Tigers', short: 'Tigers' },
};

// Group players by team
const byTeam = {};
for (const p of data) {
  const abbrev = p.team.abbrev;
  if (!byTeam[abbrev]) byTeam[abbrev] = [];

  const positions = (p.positions || [])
    .sort((a, b) => a.sort - b.sort)
    .map(pos => pos.position);

  byTeam[abbrev].push({
    name: `${p.first_name} ${p.last_name}`,
    positions,
  });
}

// Sort players alphabetically within each team
for (const abbrev of Object.keys(byTeam)) {
  byTeam[abbrev].sort((a, b) => a.name.localeCompare(b.name));
}

// Generate YAML
const lines = [
  '# NRL 2026 Player Registry',
  '# Source: SuperCoach API (supercoach.com.au)',
  '# Last updated: 2026-03-15',
  '',
  'teams:',
];

// Sort teams by key
const sortedAbbrevs = Object.keys(TEAM_MAP).sort((a, b) =>
  TEAM_MAP[a].key.localeCompare(TEAM_MAP[b].key)
);

for (const abbrev of sortedAbbrevs) {
  const team = TEAM_MAP[abbrev];
  const players = byTeam[abbrev] || [];

  lines.push(`  ${team.key}:`);
  lines.push(`    name: ${team.name}`);
  lines.push(`    short: ${team.short}`);
  lines.push(`    players:`);

  for (const p of players) {
    lines.push(`      - name: ${p.name}`);
    if (p.positions.length > 0) {
      lines.push(`        positions: [${p.positions.join(', ')}]`);
    }
  }

  lines.push('');
}

const yaml = lines.join('\n');
fs.writeFileSync('data/players.yaml', yaml);
console.log(`Generated players.yaml with ${data.length} players across ${sortedAbbrevs.length} teams`);
