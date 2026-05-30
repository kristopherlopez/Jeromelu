"""Strict Pydantic model for the SuperCoach extracted-stats shape (D8 drift contract).

Strict over the **extracted** dict shape (the output of
`jeromelu_shared.scraping.nrl.extract_all_stats` plus identity/base fields),
not over the raw 95-field jqGrid response. Reasoning: the raw response
includes ~46 fields we never use (Avg11to18, CVRd, StdDevRd, etc.) that
change frequently as the SC product evolves. Validating those would
generate false-positive drift signals.

What we DO catch: if SuperCoach renames or removes a column we depend on
(any key in `JQGRID_COLUMN_MAP`), `extract_all_stats` returns `None` for
that DB column, and the strict model fails the required field — that's
the D8 drift signal.

What we DON'T catch: SuperCoach adds a new column. That's not a breakage;
it's an opportunity. We add it to JQGRID_COLUMN_MAP when we want it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SuperCoachPlayerStats(BaseModel):
    """Extracted-row shape — one row per player per round.

    Identity + base are required (player_id is deterministic from
    name+team; player_name/team/position are always present in the
    upstream). Stat columns are nullable: empty cells in the upstream
    table get extracted as None.
    """

    model_config = ConfigDict(extra="forbid")

    # Identity
    player_id: int
    player_name: str
    team: str
    position: str

    # Base (jqGrid: Price, BE, Score, Time)
    price: int | None
    breakeven: int | None
    score: int | None
    minutes: int | None

    # SC breakdown (jqGrid: Base, Attack, Playmaking, Power, Negative)
    base: int | None
    attack: int | None
    playmaking: int | None
    power: int | None
    negative: int | None

    # Scoring (TR, TS, GO, MG, FG, MF)
    tries: int | None
    try_assists: int | None
    goals: int | None
    missed_goals: int | None
    field_goals: int | None
    missed_field_goals: int | None

    # Attack (LB, LA, LT, TB, OL, IO, H8, HU, KB)
    line_breaks: int | None
    line_break_assists: int | None
    last_touch: int | None
    tackle_busts: int | None
    offloads: int | None
    ineffective_offloads: int | None
    hitups_8m: int | None
    hitups_under_8m: int | None
    kick_metres: int | None

    # Defence (TA, MT, IT)
    tackles_made: int | None
    missed_tackles: int | None
    intercepts: int | None

    # Discipline (FD, FT, KD, PC, ER, SS, HG)
    forced_dropouts: int | None
    forty_twentys: int | None
    kicked_dead: int | None
    penalties: int | None
    errors: int | None
    sin_bins: int | None
    handover_given: int | None

    # Derived (PPM, BPPM, BasePower, BasePowerPPM)
    ppm: float | None
    base_ppm: float | None
    base_power: int | None
    base_power_ppm: float | None

    # Averages (AvgScore, TwoRdAvg, ThreeRdAvg, FiveRdAvg, SeasonAvg)
    avg_score: float | None
    two_rd_avg: float | None
    three_rd_avg: float | None
    five_rd_avg: float | None
    season_avg: float | None

    # Percentages (H8percent, TBPERCENT, MTPERCENT, OLILPERCENT, BasePercent)
    hitup_8m_pct: float | None
    tackle_bust_pct: float | None
    missed_tackle_pct: float | None
    offload_involvement_pct: float | None
    base_pct: float | None

    # Price (StartPrice, EndPrice, RoundPriceChange, SeasonPriceChange, MagicNumber)
    start_price: int | None
    end_price: int | None
    round_price_change: int | None
    season_price_change: int | None
    magic_number: int | None

    # Context (vs, Venue, weather, Surface, Jersey, ByeRd)
    opposition: str | None
    venue: str | None
    weather: str | None
    surface: str | None
    jersey: int | None
    bye_round: str | None
