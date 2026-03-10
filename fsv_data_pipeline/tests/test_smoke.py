import io
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import contextmanager, redirect_stdout
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import check_pg_status
from parsing.comprehensive_fsv_parser import ComprehensiveFSVParser, prepare_input_source
from parsing.entity_linking_report import EntityLinkingReporter
from database import sync_sqlite_to_postgres


FIXTURE_ARCHIVE = Path(__file__).parent / "fixtures" / "fsvarchiv"
REAL_ARCHIVE = Path(__file__).resolve().parents[2] / "fsvarchiv"


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


class TestPipelineSmoke(unittest.TestCase):
    def test_parser_runs_against_tiny_fixture_archive(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "fixture.db"

            parser = ComprehensiveFSVParser(
                source=str(FIXTURE_ARCHIVE),
                db_name=str(db_path),
                seasons=["2010-11"],
            )
            parser.run()

            self.assertTrue(db_path.exists())

            with sqlite3.connect(db_path) as conn:
                season_count = conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0]
                competition_count = conn.execute("SELECT COUNT(*) FROM competitions").fetchone()[0]
                match_count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]

            self.assertEqual(season_count, 1)
            self.assertGreaterEqual(competition_count, 1)
            self.assertEqual(match_count, 0)

    def test_prepare_input_source_mirrors_remote_archive_to_local_tree(self):
        with serve_directory(FIXTURE_ARCHIVE.parent) as base_url:
            prepared = prepare_input_source(f"{base_url}/fsvarchiv/")
            try:
                mirrored_season_file = prepared.local_root / "2010-11" / "profiliga.html"
                self.assertTrue(mirrored_season_file.exists())
                self.assertIn("http://", prepared.display_source)
            finally:
                prepared.cleanup()

    def test_parser_runs_against_tiny_fixture_website(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "fixture.db"
            with serve_directory(FIXTURE_ARCHIVE.parent) as base_url:
                parser = ComprehensiveFSVParser(
                    source=f"{base_url}/fsvarchiv/",
                    db_name=str(db_path),
                    seasons=["2010-11"],
                )
                parser.run()

            self.assertTrue(db_path.exists())

    def test_entity_linking_report_runs_against_minimal_fixture_data(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            db_path = tmp_path / "fixture.db"
            indices_dir = tmp_path / "indices"
            output_dir = tmp_path / "reports"
            indices_dir.mkdir()

            (indices_dir / "players.json").write_text(
                json.dumps({"player-1": {"normalized_name": "test player"}}),
                encoding="utf-8",
            )
            (indices_dir / "coaches.json").write_text(
                json.dumps({"coach-1": {"normalized_name": "test coach"}}),
                encoding="utf-8",
            )
            (indices_dir / "teams.json").write_text(
                json.dumps({"team-1": {"normalized_name": "test team"}}),
                encoding="utf-8",
            )

            with sqlite3.connect(db_path) as conn:
                conn.executescript(
                    """
                    CREATE TABLE players (
                        player_id INTEGER PRIMARY KEY,
                        name TEXT,
                        normalized_name TEXT,
                        profile_url TEXT
                    );
                    CREATE TABLE coaches (
                        coach_id INTEGER PRIMARY KEY,
                        name TEXT,
                        normalized_name TEXT,
                        profile_url TEXT
                    );
                    CREATE TABLE teams (
                        team_id INTEGER PRIMARY KEY,
                        name TEXT,
                        normalized_name TEXT,
                        profile_url TEXT
                    );
                    INSERT INTO players VALUES (1, 'Test Player', 'test player', NULL);
                    INSERT INTO coaches VALUES (1, 'Test Coach', 'test coach', NULL);
                    INSERT INTO teams VALUES (1, 'Test Team', 'test team', NULL);
                    """
                )

            reporter = EntityLinkingReporter(
                db_path=str(db_path),
                indices_dir=str(indices_dir),
                output_dir=str(output_dir),
            )
            report = reporter.generate_report()

            self.assertEqual(report["summary"]["total_entities_in_db"], 3)
            self.assertEqual(report["summary"]["total_linked_to_profiles"], 3)
            self.assertTrue(Path(reporter.save_report(report)).exists())

    @unittest.skipIf(not REAL_ARCHIVE.exists(), "Local archive not available")
    def test_parser_parses_real_league_detail_page_from_local_archive(self):
        parser = ComprehensiveFSVParser(
            source=str(REAL_ARCHIVE),
            db_name=":memory:",
        )
        try:
            season_path = REAL_ARCHIVE / "2010-11"
            metadata, lineups, substitutions, goals, cards = parser.parse_match_detail(
                season_path / "profiliga01.html",
                {"stage": "Bundesliga", "matchday": "1"},
                season_path,
            )
        finally:
            parser.db.close()
            parser.prepared_source.cleanup()

        self.assertEqual(metadata.home_team, "FSV")
        self.assertEqual(metadata.away_team, "VfB Stuttgart")
        self.assertEqual(metadata.home_goals, 2)
        self.assertEqual(metadata.away_goals, 0)
        self.assertGreaterEqual(len(lineups["home"]), 11)
        self.assertGreaterEqual(len(lineups["away"]), 11)
        self.assertGreaterEqual(len(substitutions), 2)
        self.assertGreaterEqual(len(goals), 2)

    @unittest.skipIf(not REAL_ARCHIVE.exists(), "Local archive not available")
    def test_parser_parses_real_profirest_detail_page_from_local_archive(self):
        parser = ComprehensiveFSVParser(
            source=str(REAL_ARCHIVE),
            db_name=":memory:",
        )
        try:
            season_path = REAL_ARCHIVE / "1982-83"
            metadata, lineups, substitutions, goals, cards = parser.parse_match_detail(
                season_path / "profirest01.html",
                {"stage": "Freundschaftsspiele", "matchday": None},
                season_path,
            )
        finally:
            parser.db.close()
            parser.prepared_source.cleanup()

        self.assertEqual(metadata.home_team, "Auswahl Brixental")
        self.assertEqual(metadata.away_team, "FSV")
        self.assertEqual(metadata.home_goals, 2)
        self.assertEqual(metadata.away_goals, 12)
        self.assertTrue(lineups["home"] or lineups["away"])

    @unittest.skipIf(not REAL_ARCHIVE.exists(), "Local archive not available")
    def test_parser_keeps_profirest_multi_match_boundaries_in_local_archive(self):
        parser = ComprehensiveFSVParser(
            source=str(REAL_ARCHIVE),
            db_name=":memory:",
        )
        try:
            season_path = REAL_ARCHIVE / "2010-11"
            metadata, lineups, substitutions, goals, cards = parser.parse_match_detail(
                season_path / "profirest09.html",
                {"stage": "Freundschaftsspiele", "matchday": None},
                season_path,
            )
        finally:
            parser.db.close()
            parser.prepared_source.cleanup()

        self.assertEqual(metadata.home_team, "MSV Duisburg")
        self.assertEqual(metadata.away_team, "FSV")
        self.assertEqual(metadata.home_goals, 2)
        self.assertEqual(metadata.away_goals, 3)
        self.assertEqual(len(substitutions), 3)
        self.assertEqual(len(goals), 5)
        self.assertEqual(goals[-1].score_home, 2)
        self.assertEqual(goals[-1].score_away, 3)
        self.assertTrue(lineups["away"])

    @unittest.skipIf(not REAL_ARCHIVE.exists(), "Local archive not available")
    def test_parser_collects_multiple_profirest_entries_for_persistence(self):
        parser = ComprehensiveFSVParser(
            source=str(REAL_ARCHIVE),
            db_name=":memory:",
        )
        try:
            season_path = REAL_ARCHIVE / "2010-11"
            detail_path = season_path / "profirest09.html"
            entries = parser._parse_detail_entries(
                detail_path,
                "2010-11/profirest09.html",
                {"stage": "Freundschaftsspiele", "matchday": None},
                season_path,
            )
        finally:
            parser.db.close()
            parser.prepared_source.cleanup()

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0][0], "2010-11/profirest09.html#match1")
        self.assertEqual(entries[1][0], "2010-11/profirest09.html#match2")
        self.assertEqual(entries[0][1][0].home_team, "MSV Duisburg")
        self.assertEqual(entries[1][1][0].home_team, "SG Rot-Weiß Olympia Alzey")

    @unittest.skipIf(not REAL_ARCHIVE.exists(), "Local archive not available")
    def test_parser_cleans_goal_annotation_artifacts_from_real_archive_pages(self):
        parser = ComprehensiveFSVParser(
            source=str(REAL_ARCHIVE),
            db_name=":memory:",
        )
        try:
            season_path = REAL_ARCHIVE / "2015-16"
            metadata, lineups, substitutions, goals, cards = parser.parse_match_detail(
                season_path / "profiliga11.html",
                {"stage": "Bundesliga", "matchday": 11},
                season_path,
            )
            friendly_path = REAL_ARCHIVE / "2016-17"
            friendly_entries = parser._parse_detail_entries(
                friendly_path / "profirest09.html",
                "2016-17/profirest09.html",
                {"stage": "Freundschaftsspiele", "matchday": None},
                friendly_path,
            )
        finally:
            parser.db.close()
            parser.prepared_source.cleanup()

        self.assertEqual(metadata.home_team, "FC Augsburg")
        self.assertEqual(goals[2].scorer, "Verhaegh")
        self.assertEqual(goals[2].assist, "de Blasis")
        self.assertIsNone(goals[2].scorer_profile_url)
        self.assertEqual(friendly_entries[0][1][3][0].assist, "Kuijt")
        self.assertIsNone(friendly_entries[0][1][3][1].assist)

    @unittest.skipIf(not REAL_ARCHIVE.exists(), "Local archive not available")
    def test_parser_skips_wrapper_cells_in_old_lineup_layouts(self):
        parser = ComprehensiveFSVParser(
            source=str(REAL_ARCHIVE),
            db_name=":memory:",
        )
        try:
            season_path = REAL_ARCHIVE / "1959-60"
            metadata, lineups, substitutions, goals, cards = parser.parse_match_detail(
                season_path / "profiliga21.html",
                {"stage": "Oberliga Südwest", "matchday": 21},
                season_path,
            )
        finally:
            parser.db.close()
            parser.prepared_source.cleanup()

        self.assertEqual(metadata.home_team, "FSV")
        self.assertEqual(metadata.away_team, "SV Eintracht Trier")
        self.assertEqual(len(lineups["home"]), 11)
        self.assertEqual(len(lineups["away"]), 11)
        self.assertNotIn(
            "Klawun Konrad May Eichhorn K. Jakobi Stoll Dr. Baumgart Matzat Pidancet Weber Butscheidt",
            lineups["home"],
        )
        self.assertIn("Natale", lineups["home"])
        self.assertIn("Klawun", lineups["away"])

    def test_sync_cli_passes_dry_run_flag_to_engine(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            sqlite_path = Path(tmp_dir) / "fixture.db"
            sqlite_path.touch()

            with patch.object(sync_sqlite_to_postgres, "POSTGRES_URL", "postgresql://example"):
                with patch.object(sync_sqlite_to_postgres, "SyncEngine") as engine_cls:
                    engine = engine_cls.return_value
                    with patch(
                        "sys.argv",
                        [
                            "sync_sqlite_to_postgres.py",
                            "--dry-run",
                            "--sqlite",
                            str(sqlite_path),
                        ],
                    ):
                        sync_sqlite_to_postgres.main()

            engine_cls.assert_called_once_with(str(sqlite_path), "postgresql://example", dry_run=True)
            engine.sync_all.assert_called_once()
            engine.close.assert_called_once()

    def test_status_command_handles_missing_postgres_configuration(self):
        output = io.StringIO()
        config_stub = type("ConfigStub", (), {"PG_ENABLED": False})
        with patch.object(check_pg_status, "Config", return_value=config_stub()):
            with redirect_stdout(output):
                check_pg_status.main()

        rendered = output.getvalue()
        self.assertIn("PostgreSQL is not enabled", rendered)


if __name__ == "__main__":
    unittest.main()
