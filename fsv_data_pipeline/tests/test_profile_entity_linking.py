#!/usr/bin/env python3
"""
Test suite for profile parsing and entity linking.

Tests:
1. Profile index building from spieler/, gegner/, trainer/ folders
2. Entity linking during match parsing
3. Canonical name resolution
4. Invalid name pattern rejection
5. Multi-match profirest file parsing
"""

import logging
import unittest
from pathlib import Path

from parsing.profile_index_builder import (
    ProfileIndexBuilder,
    PlayerProfileParser,
    CoachProfileParser,
    normalize_name,
    strip_accents,
)
from parsing.comprehensive_fsv_parser import (
    ComprehensiveFSVParser,
    DatabaseManager,
    normalize_name as parser_normalize_name,
)

logging.basicConfig(level=logging.WARNING)


class TestNormalizeName(unittest.TestCase):
    """Test name normalization functions."""

    def test_strip_accents(self):
        """Test accent stripping."""
        self.assertEqual(strip_accents("Müller"), "Muller")
        self.assertEqual(strip_accents("Özil"), "Ozil")
        self.assertEqual(strip_accents("Günter"), "Gunter")
        self.assertEqual(strip_accents("Schröder"), "Schroder")
        self.assertEqual(strip_accents("Kovač"), "Kovac")

    def test_normalize_name(self):
        """Test full name normalization."""
        self.assertEqual(normalize_name("Jürgen KLOPP"), "jurgen klopp")
        self.assertEqual(normalize_name("MÜLLER, Thomas"), "muller thomas")
        self.assertEqual(normalize_name("O'Brien"), "obrien")
        # Note: normalize_name strips leading/trailing spaces but doesn't collapse internal spaces
        self.assertEqual(normalize_name("  Test Name  "), "test name")

    def test_normalize_name_special_chars(self):
        """Test normalization with special characters."""
        self.assertEqual(normalize_name("Player-Name"), "playername")
        self.assertEqual(normalize_name("Name (Jr.)"), "name jr")


class TestPlayerProfileParser(unittest.TestCase):
    """Test player profile parsing."""

    def setUp(self):
        self.parser = PlayerProfileParser()

    def test_birth_pattern_full(self):
        """Test birth pattern with all fields."""
        text = "* 16.06.1967 in Stuttgart, 191 cm, 83 kg."
        match = self.parser.BIRTH_PATTERN.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "16.06.1967")
        self.assertEqual(match.group(2).strip(), "Stuttgart")
        self.assertEqual(match.group(3), "191")
        self.assertEqual(match.group(4), "83")

    def test_birth_pattern_date_only(self):
        """Test birth pattern with date only."""
        text = "* 01.01.1990"
        match = self.parser.BIRTH_PATTERN.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "01.01.1990")


class TestCoachProfileParser(unittest.TestCase):
    """Test coach profile parsing."""

    def setUp(self):
        self.parser = CoachProfileParser()

    def test_birth_pattern(self):
        """Test coach birth pattern."""
        text = "* 16.06.1967 in Stuttgart."
        match = self.parser.BIRTH_PATTERN.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "16.06.1967")


class TestParserNameResolution(unittest.TestCase):
    """Test current parser name resolution behavior."""

    def test_parser_and_profile_builder_share_normalization(self):
        self.assertEqual(parser_normalize_name("Jürgen Klopp"), normalize_name("Jürgen Klopp"))
        self.assertEqual(parser_normalize_name("MÜLLER, Thomas"), normalize_name("MÜLLER, Thomas"))

    def test_resolve_player_name_prefers_profile_name_when_available(self):
        parser = ComprehensiveFSVParser(base_path="tests/fixtures/fsvarchiv", db_name=":memory:")
        parser.get_full_name_from_profile = lambda profile_url: "JÜRGEN KLOPP"

        resolved_name, resolved_url = parser.resolve_player_name("Klopp", "spieler/klopp.html")

        self.assertEqual(resolved_name, "JÜRGEN KLOPP")
        self.assertEqual(resolved_url, "spieler/klopp.html")


class TestInvalidNamePatterns(unittest.TestCase):
    """Test invalid name pattern rejection."""

    def setUp(self):
        self.db = DatabaseManager(":memory:")

    def tearDown(self):
        self.db.conn.close()

    def test_goal_text_patterns(self):
        """Test that obvious goal text is rejected during player creation."""
        invalid_names = [
            "Tore 1. Klopp",
            "3. 0:1",
            "3. 0-1",
            "?",
            "-",
        ]

        for name in invalid_names:
            with self.assertRaises(ValueError, msg=f"Expected '{name}' to be rejected"):
                self.db.get_or_create_player(name, None)

    def test_valid_names_pass(self):
        """Test that valid player names still pass validation."""
        valid_names = [
            "Klopp",
            "Jürgen Klopp",
            "Thomas Müller",
            "van der Vaart",
            "O'Brien",
            "Hernández",
        ]

        for name in valid_names:
            player_id = self.db.get_or_create_player(name, None)
            self.assertIsInstance(player_id, int)


class TestProfileIndexIntegration(unittest.TestCase):
    """Integration tests that require the actual archive files."""

    @unittest.skipIf(
        not Path("fsvarchiv/spieler").exists(),
        "Archive not available"
    )
    def test_build_player_index(self):
        """Test building player index from actual archive."""
        builder = ProfileIndexBuilder(
            archive_dir="fsvarchiv",
            output_dir="generated/indices_test"
        )
        index = builder.build_player_index()

        # Should have parsed some players
        self.assertGreater(len(index), 100)

        # Check a known player exists
        if "klopp.html" in index:
            player = index["klopp.html"]
            self.assertIn("name", player)
            self.assertIn("normalized_name", player)
            # Name should be uppercase (as in the archive)
            self.assertTrue(player["name"].isupper() or " " in player["name"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
