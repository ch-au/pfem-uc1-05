import io
import json
import logging
import tempfile
import threading
import unittest
from contextlib import contextmanager, redirect_stdout
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from parsing.database_manager import DatabaseManager
from parsing.entity_linking_report_renderer import (
    build_report_payload,
    print_report_summary,
    save_report_file,
)
from parsing.html_utils import normalize_name, normalize_whitespace, parse_int, parse_minute
from parsing.parser_match_helpers import MatchParsingMixin
from parsing.match_types import MatchMetadata
from parsing.parser_profile_enrichment import ProfileEnrichmentMixin
from parsing.profile_index_builder import ProfileIndexBuilder
from parsing.profile_parsers import PlayerProfileParser
from parsing.source_preparation import prepare_input_source


FIXTURE_ARCHIVE = Path(__file__).parent / "fixtures" / "fsvarchiv"


@contextmanager
def serve_directory(directory: Path):
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class RendererStub:
    db_path = Path("fixture.db")
    indices_dir = Path("generated/indices")
    players_index = {"a": {"normalized_name": "player a"}}
    coaches_index = {"b": {"normalized_name": "coach b"}}
    teams_index = {"c": {"normalized_name": "team c"}}

    def analyze_players(self):
        return {
            "total": 1,
            "linked_to_profile": 1,
            "no_profile_match": 0,
            "has_full_name": 1,
            "surname_only": 0,
            "link_rate_percent": 100.0,
            "full_name_rate_percent": 100.0,
        }

    def analyze_coaches(self):
        return {
            "total": 1,
            "linked_to_profile": 1,
            "no_profile_match": 0,
            "has_full_name": 1,
            "link_rate_percent": 100.0,
            "full_name_rate_percent": 100.0,
        }

    def analyze_teams(self):
        return {
            "total": 1,
            "linked_to_profile": 1,
            "no_profile_match": 0,
            "link_rate_percent": 100.0,
        }

    def find_potential_duplicates(self):
        return {"player_potential_duplicates": []}


class MatchHelperHarness(MatchParsingMixin):
    def __init__(self):
        self.logger = logging.getLogger("MatchHelperHarness")


class ProfileHarness(ProfileEnrichmentMixin):
    def __init__(self, base_path: Path, db: DatabaseManager):
        self.base_path = base_path
        self.db = db
        self.logger = logging.getLogger("ProfileHarness")
        self.player_file_index = self.build_player_index()


class TestHtmlUtils(unittest.TestCase):
    def test_normalization_helpers(self):
        self.assertEqual(normalize_whitespace(" a \n  b "), "a b")
        self.assertEqual(normalize_name("Jean-Luc O'Brien"), "jean luc o brien")
        self.assertEqual(parse_int("12.345"), 12345)
        self.assertEqual(parse_minute("90+2."), (90, 2))


class TestSourcePreparation(unittest.TestCase):
    def test_prepare_input_source_uses_local_directory(self):
        prepared = prepare_input_source(str(FIXTURE_ARCHIVE))
        try:
            self.assertEqual(prepared.local_root, FIXTURE_ARCHIVE.resolve())
            self.assertTrue((prepared.local_root / "2010-11" / "profiliga.html").exists())
        finally:
            prepared.cleanup()

    def test_prepare_input_source_mirrors_remote_archive(self):
        with serve_directory(FIXTURE_ARCHIVE.parent) as base_url:
            prepared = prepare_input_source(f"{base_url}/fsvarchiv/")
            try:
                mirrored_file = prepared.local_root / "2010-11" / "profiliga.html"
                self.assertTrue(mirrored_file.exists())
                self.assertEqual(mirrored_file.read_text(encoding="utf-8").strip()[:5], "<html")
            finally:
                prepared.cleanup()


class TestProfileParsers(unittest.TestCase):
    def test_player_profile_parser_extracts_core_fields(self):
        html = """
        <html><body>
        <b>Jürgen Klopp</b>
        * 16.06.1967 in Stuttgart, 191 cm, 83 kg.
        <b>Position:</b><br><br>Verteidiger
        Nationalität: Deutschland
        <img src="klopp.jpg" />
        </body></html>
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            profile_path = Path(tmp_dir) / "klopp.html"
            profile_path.write_text(html, encoding="utf-8")
            profile = PlayerProfileParser().parse(profile_path)

        self.assertIsNotNone(profile)
        self.assertEqual(profile.name, "Jürgen Klopp")
        self.assertTrue(profile.position.startswith("Verteidiger"))
        self.assertEqual(profile.image_url, "klopp.jpg")

    def test_profile_index_builder_skips_navigation_team_pages(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive_dir = Path(tmp_dir) / "archive"
            gegner_dir = archive_dir / "gegner"
            output_dir = Path(tmp_dir) / "indices"
            gegner_dir.mkdir(parents=True)
            (gegner_dir / "gegnerfr.html").write_text("<html><frameset></frameset></html>", encoding="utf-8")
            (gegner_dir / "gegnertop.html").write_text("<html><body>Alle Gegner</body></html>", encoding="utf-8")
            (gegner_dir / "gegner.html").write_text("<html><body>Index</body></html>", encoding="utf-8")
            (gegner_dir / "testclub.html").write_text("<html><body><b>Test Club</b></body></html>", encoding="utf-8")

            summary = ProfileIndexBuilder(str(archive_dir), str(output_dir)).build_all_indices()
            teams = json.loads((output_dir / "teams.json").read_text(encoding="utf-8"))

        self.assertEqual(summary["stats"]["teams_parsed"], 1)
        self.assertEqual(summary["stats"]["teams_failed"], 0)
        self.assertEqual(list(teams.keys()), ["testclub.html"])


class TestDatabaseManager(unittest.TestCase):
    def test_get_or_create_player_reuses_profile_url(self):
        db = DatabaseManager(":memory:")
        try:
            first_id = db.get_or_create_player("Jürgen Klopp", "spieler/klopp.html")
            second_id = db.get_or_create_player("Klopp", "spieler/klopp.html")
            self.assertEqual(first_id, second_id)
        finally:
            db.close()


class TestMatchParsingMixin(unittest.TestCase):
    def test_parse_header_score_extracts_halftime(self):
        harness = MatchHelperHarness()
        parsed = harness.parse_header_score("FSV Mainz 05 - FC Bayern 2:1 (1:0)")
        self.assertEqual(parsed, ("FSV Mainz 05", "FC Bayern", 2, 1, 1, 0))

    def test_parse_goal_table_cleans_assist_descriptors(self):
        harness = MatchHelperHarness()
        metadata = MatchMetadata(
            home_team="FC Augsburg",
            away_team="FSV",
            home_goals=3,
            away_goals=3,
            half_home=1,
            half_away=2,
            date=None,
            kickoff=None,
            attendance=None,
            referee=None,
            referee_link=None,
            home_coach=None,
            home_coach_link=None,
            away_coach=None,
            away_coach_link=None,
            matchday=11,
            round_name="11. Spieltag",
            leg=None,
        )
        html = """
        <html><body>
        <table><tr><td><b>Tore</b></td></tr></table>
        <table><tr>
        <td>42. 1:2 Verhaegh (Elfmeter, <a href="../spieler/deblasis.html">de Blasis</a>)</td>
        <td>56. 1:0 Berghuis (ind. FS, Kuijt)</td>
        <td>60. 2:0 Spieler (FE im Nachschuss, s.u.)</td>
        </tr></table>
        </body></html>
        """
        from bs4 import BeautifulSoup

        goals = harness.parse_goal_table(BeautifulSoup(html, "lxml"), metadata)

        self.assertEqual(goals[0].assist, "de Blasis")
        self.assertEqual(goals[1].assist, "Kuijt")
        self.assertIsNone(goals[2].assist)
        self.assertEqual(harness._clean_goal_participant_text("FE, Fathi an Şahan, im Nachschuss, Pieckenhagen hatte gehalten"), "Şahan")

    def test_parse_goal_table_handles_early_score_only_layout(self):
        harness = MatchHelperHarness()
        metadata = MatchMetadata(
            home_team="FSV",
            away_team="1. FC Idar",
            home_goals=5,
            away_goals=0,
        )
        html = """
        <html><body>
        <table><tr><td><b>Tore</b></td></tr></table>
        <table><tr>
        <td>1:0 <a href="../spieler/murtas.html">Murtas</a></td>
        <td>2:0 <a href="../spieler/lipponerjr.html">Lipponer</a></td>
        <td><a href="../spieler/lipponerjr.html">Lipponer</a></td>
        <td><a href="../spieler/lipponerjr.html">Lipponer</a></td>
        <td><a href="../spieler/barth.html">Barth</a></td>
        </tr></table>
        </body></html>
        """
        from bs4 import BeautifulSoup

        goals = harness.parse_goal_table(BeautifulSoup(html, "lxml"), metadata)

        self.assertEqual(len(goals), 5)
        self.assertEqual([(goal.score_home, goal.score_away) for goal in goals], [(1, 0), (2, 0), (3, 0), (4, 0), (5, 0)])
        self.assertEqual([goal.scorer for goal in goals], ["Murtas", "Lipponer", "Lipponer", "Lipponer", "Barth"])

    def test_parse_team_block_skips_missing_lineup_placeholder_text(self):
        harness = MatchHelperHarness()
        from bs4 import BeautifulSoup

        html = """
        <table>
          <tr>
            <td>Die Aufstellung des FV 03 liegt nicht vor.</td>
            <td><a href="../spieler/test.html">Testspieler</a></td>
          </tr>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        parsed = harness.parse_team_block(soup.find("table"))

        self.assertNotIn("Die Aufstellung des FV 03 liegt nicht vor.", parsed["players"])


class TestProfileEnrichmentMixin(unittest.TestCase):
    def test_get_full_name_from_profile_reads_html_header(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            player_dir = base_path / "spieler"
            player_dir.mkdir()
            (player_dir / "klopp.html").write_text("<html><body><b>Jürgen Klopp</b></body></html>", encoding="utf-8")
            harness = ProfileHarness(base_path, DatabaseManager(":memory:"))
            try:
                self.assertEqual(harness.get_full_name_from_profile("spieler/klopp.html"), "Jürgen Klopp")
            finally:
                harness.db.close()

    def test_parse_player_profile_prefers_explicit_profile_url(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_path = Path(tmp_dir)
            player_dir = base_path / "spieler"
            player_dir.mkdir()
            (player_dir / "alias.html").write_text(
                "<html><body><b>Jürgen Klopp</b>* 16.06.1967 in Stuttgart</body></html>",
                encoding="utf-8",
            )
            db = DatabaseManager(":memory:")
            harness = ProfileHarness(base_path, db)
            try:
                player_id = db.get_or_create_player("Alias Name", "spieler/alias.html")
                harness.parse_player_profile("Completely Different Name", base_path, "spieler/alias.html")
                row = db.conn.execute(
                    "SELECT birth_place FROM players WHERE player_id = ?",
                    (player_id,),
                ).fetchone()
                self.assertEqual(row[0], "Stuttgart")
            finally:
                db.close()


class TestEntityLinkingRenderer(unittest.TestCase):
    def test_renderer_builds_saves_and_prints_report(self):
        report = build_report_payload(RendererStub())
        self.assertEqual(report["summary"]["overall_link_rate_percent"], 100.0)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            path = save_report_file(output_dir, report)
            saved_report = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(saved_report["summary"]["total_entities_in_db"], 3)

        output = io.StringIO()
        with redirect_stdout(output):
            print_report_summary(report)
        self.assertIn("ENTITY LINKING REPORT", output.getvalue())
