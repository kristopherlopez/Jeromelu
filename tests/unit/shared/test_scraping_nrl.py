"""Unit tests for jeromelu_shared.scraping.nrl pure helpers.

Covers team-code resolution, name normalisation, numeric parsing, and
deterministic player-id generation. All inputs are static — no IO.
"""

import pytest
from jeromelu_shared.scraping.nrl import (
    JQGRID_COLUMN_MAP,
    STAT_DB_COLUMNS,
    TEAM_CODE_MAP,
    clean_name,
    extract_all_stats,
    generate_player_id,
    normalize_name,
    normalize_team,
    parse_float,
    parse_int,
)

# ---------------------------------------------------------------------------
# normalize_team
# ---------------------------------------------------------------------------


class TestNormalizeTeam:
    @pytest.mark.parametrize(
        "code,expected",
        [
            ("BRO", "Broncos"),
            ("PAR", "Eels"),
            ("MAN", "Sea Eagles"),
            ("PAN", "Panthers"),
            ("WAR", "Warriors"),
            ("NQL", "Cowboys"),
        ],
    )
    def test_known_codes_resolve_to_canonical_name(self, code, expected):
        assert normalize_team(code) == expected

    def test_lowercase_code_resolves(self):
        assert normalize_team("bro") == "Broncos"

    def test_mixed_case_code_resolves(self):
        assert normalize_team("Bro") == "Broncos"

    def test_surrounding_whitespace_stripped(self):
        assert normalize_team("  BRO  ") == "Broncos"

    def test_unknown_team_returned_stripped(self):
        assert normalize_team("  Made-Up FC  ") == "Made-Up FC"

    def test_empty_string_returns_empty(self):
        assert normalize_team("") == ""

    def test_canonical_name_passthrough(self):
        # Already-canonical names aren't in the code map, so they fall
        # through the .strip() branch unchanged.
        assert normalize_team("Broncos") == "Broncos"

    def test_team_code_map_covers_all_17_clubs(self):
        # Sanity check: the 17 NRL clubs must all be reachable. If the NRL
        # adds an 18th team, this guard reminds us to update the map.
        assert len(set(TEAM_CODE_MAP.values())) == 17


# ---------------------------------------------------------------------------
# clean_name
# ---------------------------------------------------------------------------


class TestCleanName:
    def test_plain_text_unchanged(self):
        assert clean_name("Tom Trbojevic") == "Tom Trbojevic"

    def test_strips_simple_html_tags(self):
        assert clean_name("<b>Tom Trbojevic</b>") == "Tom Trbojevic"

    def test_strips_nested_html(self):
        assert clean_name("<a href='x'>Tom <i>T</i></a>") == "Tom T"

    def test_collapses_repeated_spaces(self):
        assert clean_name("Tom    Trbojevic") == "Tom Trbojevic"

    def test_collapses_tabs_and_newlines(self):
        assert clean_name("Tom\t\nTrbojevic") == "Tom Trbojevic"

    def test_strips_outer_whitespace(self):
        assert clean_name("   Tom Trbojevic   ") == "Tom Trbojevic"

    def test_html_with_attributes(self):
        assert clean_name('<span class="player">Latrell Mitchell</span>') == "Latrell Mitchell"


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------


class TestNormalizeName:
    def test_last_first_swapped_to_first_last(self):
        assert normalize_name("Lopez, Kris") == "Kris Lopez"

    def test_no_comma_returned_unchanged(self):
        assert normalize_name("Tom Trbojevic") == "Tom Trbojevic"

    def test_multiple_first_names_kept_together(self):
        assert normalize_name("Cleary, Nathan James") == "Nathan James Cleary"

    def test_no_space_after_comma_still_swaps(self):
        assert normalize_name("Lopez,Kris") == "Kris Lopez"

    def test_extra_whitespace_around_parts_stripped(self):
        assert normalize_name("  Lopez  ,  Kris  ") == "Kris Lopez"

    def test_only_first_comma_used_for_split(self):
        # Trailing commas in the first-name half are preserved verbatim.
        assert normalize_name("Smith, Bob, Jr") == "Bob, Jr Smith"

    def test_empty_string_unchanged(self):
        assert normalize_name("") == ""


# ---------------------------------------------------------------------------
# parse_int
# ---------------------------------------------------------------------------


class TestParseInt:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (5, 5),
            (5.7, 5),
            (-3, -3),
            ("5", 5),
            ("5,000", 5000),
            ("$5,000", 5000),
            ("  $5,000  ", 5000),
            ("$1,000,000", 1_000_000),
        ],
    )
    def test_valid_inputs(self, value, expected):
        assert parse_int(value) == expected

    @pytest.mark.parametrize("garbage", ["abc", "", None, "N/A", "--"])
    def test_garbage_returns_zero(self, garbage):
        assert parse_int(garbage) == 0


# ---------------------------------------------------------------------------
# parse_float
# ---------------------------------------------------------------------------


class TestParseFloat:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (5, 5.0),
            (5.7, 5.7),
            ("5.7", 5.7),
            ("1,234.56", 1234.56),
            ("$1,234.56", 1234.56),
            ("  3.14  ", 3.14),
        ],
    )
    def test_valid_inputs(self, value, expected):
        assert parse_float(value) == pytest.approx(expected)

    @pytest.mark.parametrize("garbage", ["abc", "", None, "N/A"])
    def test_garbage_returns_zero(self, garbage):
        assert parse_float(garbage) == 0.0


# ---------------------------------------------------------------------------
# generate_player_id
# ---------------------------------------------------------------------------


class TestGeneratePlayerId:
    def test_deterministic_same_input(self):
        a = generate_player_id("Tom Trbojevic", "Sea Eagles")
        b = generate_player_id("Tom Trbojevic", "Sea Eagles")
        assert a == b

    def test_different_name_different_id(self):
        a = generate_player_id("Tom Trbojevic", "Sea Eagles")
        b = generate_player_id("Jake Trbojevic", "Sea Eagles")
        assert a != b

    def test_different_team_different_id(self):
        a = generate_player_id("Tom Trbojevic", "Sea Eagles")
        b = generate_player_id("Tom Trbojevic", "Broncos")
        assert a != b

    def test_whitespace_normalised(self):
        a = generate_player_id("Tom Trbojevic", "Sea Eagles")
        b = generate_player_id("  Tom Trbojevic  ", "  Sea Eagles  ")
        assert a == b

    def test_case_normalised(self):
        a = generate_player_id("tom trbojevic", "sea eagles")
        b = generate_player_id("TOM TRBOJEVIC", "SEA EAGLES")
        assert a == b

    def test_id_fits_signed_int32(self):
        # 31-bit positive int — safe for any DB int column.
        for name, team in [
            ("Tom Trbojevic", "Sea Eagles"),
            ("Nathan Cleary", "Panthers"),
            ("Reece Walsh", "Broncos"),
            ("a", "b"),
        ]:
            pid = generate_player_id(name, team)
            assert 0 <= pid <= 0x7FFFFFFF


# ---------------------------------------------------------------------------
# extract_all_stats / JQGRID_COLUMN_MAP
# ---------------------------------------------------------------------------


class TestJqgridColumnMap:
    def test_no_duplicate_db_columns(self):
        # Two jqGrid keys mapping to the same DB column would silently
        # overwrite each other in the persist dict — guard against that.
        cols = [col for col, _ in JQGRID_COLUMN_MAP.values()]
        assert len(cols) == len(set(cols))

    def test_stat_db_columns_matches_map(self):
        # STAT_DB_COLUMNS is the persist-helper's source of truth and must
        # stay in lock-step with the map. If someone adds a key to the map
        # but forgets to refresh the export, this fails loudly.
        assert set(STAT_DB_COLUMNS) == {col for col, _ in JQGRID_COLUMN_MAP.values()}

    def test_sample_keys_present(self):
        # Spot-check that core SC columns are mapped — drift from the SC
        # response shape would quietly zero stats otherwise.
        for jq_key in ["TR", "TS", "Base", "PPM", "StartPrice", "TA"]:
            assert jq_key in JQGRID_COLUMN_MAP, f"{jq_key} dropped from map"


class TestExtractAllStats:
    def test_extracts_mapped_keys_with_correct_parsers(self):
        row = {
            "Base": "42",
            "TR": "34",  # 2 tries × 17pts
            "PPM": "1.23",
            "StartPrice": "$523,400",
            "Venue": "  Suncorp Stadium  ",
        }
        stats = extract_all_stats(row)
        assert stats["base"] == 42
        assert stats["tries"] == 34
        assert stats["ppm"] == pytest.approx(1.23)
        assert stats["start_price"] == 523400
        assert stats["venue"] == "Suncorp Stadium"

    def test_unmapped_keys_ignored(self):
        # An unexpected key from the SC response shouldn't crash extraction.
        stats = extract_all_stats({"Base": "10", "MysteryColumn": "junk"})
        assert stats["base"] == 10
        assert "MysteryColumn" not in stats

    def test_missing_keys_return_none(self):
        # Keys not present in the input → None in the output (so persist
        # logic can distinguish "not reported" from a real zero).
        stats = extract_all_stats({"Base": "10"})
        # All other mapped DB columns must exist as None.
        for col in STAT_DB_COLUMNS:
            if col == "base":
                continue
            assert stats[col] is None, f"{col} should be None when absent from row"

    def test_empty_string_treated_as_missing(self):
        # SC returns "" for nullable cells (e.g. byes). These must surface
        # as None, not parse to 0 — they're semantically different from
        # "scored zero tries this round".
        stats = extract_all_stats({"TR": ""})
        assert stats["tries"] is None

    def test_whitespace_only_string_treated_as_missing(self):
        stats = extract_all_stats({"TR": "   "})
        assert stats["tries"] is None

    def test_string_columns_stripped(self):
        stats = extract_all_stats({"vs": "  PAN  "})
        assert stats["opposition"] == "PAN"

    def test_full_row_yields_value_for_every_mapped_column(self):
        # If we feed every mapped key with a parseable value, every DB
        # column should land non-None. Catches parsers that incorrectly
        # treat valid input as missing.
        row = {}
        for jq_key, (_, parser) in JQGRID_COLUMN_MAP.items():
            row[jq_key] = "1" if parser is not str else "x"
        stats = extract_all_stats(row)
        missing = [col for col in STAT_DB_COLUMNS if stats[col] is None]
        assert missing == [], f"columns came back None despite valid input: {missing}"
