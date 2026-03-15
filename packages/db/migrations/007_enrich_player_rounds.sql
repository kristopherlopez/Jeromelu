-- 007: Add full jqGrid stat columns to player_rounds
-- Values are SC points, not raw stat counts.

-- SC Breakdown
ALTER TABLE player_rounds ADD COLUMN base integer;
ALTER TABLE player_rounds ADD COLUMN attack integer;
ALTER TABLE player_rounds ADD COLUMN playmaking integer;
ALTER TABLE player_rounds ADD COLUMN power integer;
ALTER TABLE player_rounds ADD COLUMN negative integer;

-- Scoring
ALTER TABLE player_rounds ADD COLUMN tries integer;
ALTER TABLE player_rounds ADD COLUMN try_assists integer;
ALTER TABLE player_rounds ADD COLUMN goals integer;
ALTER TABLE player_rounds ADD COLUMN missed_goals integer;
ALTER TABLE player_rounds ADD COLUMN field_goals integer;
ALTER TABLE player_rounds ADD COLUMN missed_field_goals integer;

-- Attack
ALTER TABLE player_rounds ADD COLUMN line_breaks integer;
ALTER TABLE player_rounds ADD COLUMN line_break_assists integer;
ALTER TABLE player_rounds ADD COLUMN last_touch integer;
ALTER TABLE player_rounds ADD COLUMN tackle_busts integer;
ALTER TABLE player_rounds ADD COLUMN offloads integer;
ALTER TABLE player_rounds ADD COLUMN ineffective_offloads integer;
ALTER TABLE player_rounds ADD COLUMN hitups_8m integer;
ALTER TABLE player_rounds ADD COLUMN hitups_under_8m integer;
ALTER TABLE player_rounds ADD COLUMN kick_metres integer;

-- Defence
ALTER TABLE player_rounds ADD COLUMN tackles_made integer;
ALTER TABLE player_rounds ADD COLUMN missed_tackles integer;
ALTER TABLE player_rounds ADD COLUMN intercepts integer;

-- Discipline
ALTER TABLE player_rounds ADD COLUMN forced_dropouts integer;
ALTER TABLE player_rounds ADD COLUMN forty_twentys integer;
ALTER TABLE player_rounds ADD COLUMN kicked_dead integer;
ALTER TABLE player_rounds ADD COLUMN penalties integer;
ALTER TABLE player_rounds ADD COLUMN errors integer;
ALTER TABLE player_rounds ADD COLUMN sin_bins integer;
ALTER TABLE player_rounds ADD COLUMN handover_given integer;

-- Derived
ALTER TABLE player_rounds ADD COLUMN ppm double precision;
ALTER TABLE player_rounds ADD COLUMN base_ppm double precision;
ALTER TABLE player_rounds ADD COLUMN base_power integer;
ALTER TABLE player_rounds ADD COLUMN base_power_ppm double precision;

-- Averages
ALTER TABLE player_rounds ADD COLUMN avg_score double precision;
ALTER TABLE player_rounds ADD COLUMN two_rd_avg double precision;
ALTER TABLE player_rounds ADD COLUMN three_rd_avg double precision;
ALTER TABLE player_rounds ADD COLUMN five_rd_avg double precision;
ALTER TABLE player_rounds ADD COLUMN season_avg double precision;

-- Percentages
ALTER TABLE player_rounds ADD COLUMN hitup_8m_pct double precision;
ALTER TABLE player_rounds ADD COLUMN tackle_bust_pct double precision;
ALTER TABLE player_rounds ADD COLUMN missed_tackle_pct double precision;
ALTER TABLE player_rounds ADD COLUMN offload_involvement_pct double precision;
ALTER TABLE player_rounds ADD COLUMN base_pct double precision;

-- Price
ALTER TABLE player_rounds ADD COLUMN start_price integer;
ALTER TABLE player_rounds ADD COLUMN end_price integer;
ALTER TABLE player_rounds ADD COLUMN round_price_change integer;
ALTER TABLE player_rounds ADD COLUMN season_price_change integer;
ALTER TABLE player_rounds ADD COLUMN magic_number integer;

-- Context
ALTER TABLE player_rounds ADD COLUMN opposition text;
ALTER TABLE player_rounds ADD COLUMN venue text;
ALTER TABLE player_rounds ADD COLUMN weather text;
ALTER TABLE player_rounds ADD COLUMN surface text;
ALTER TABLE player_rounds ADD COLUMN jersey integer;
ALTER TABLE player_rounds ADD COLUMN bye_round text;
