import logging
import re
import sqlite3
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple

from parsing.html_utils import normalize_name
from parsing.match_types import GoalEvent, MatchMetadata, PlayerAppearance

MAINZ_TEAM_KEY = "1. FSV Mainz 05"


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.create_schema()
        self.team_cache: Dict[str, int] = {}
        self.competition_cache: Dict[str, int] = {}
        self.coach_cache: Dict[str, int] = {}
        self.referee_cache: Dict[str, int] = {}
        self.player_cache: Dict[str, int] = {}
        self.player_profile_cache: Dict[str, int] = {}
        self.team_profile_cache: Dict[str, int] = {}
        self.coach_profile_cache: Dict[str, int] = {}
        self.current_season: Optional[str] = None
        self.player_creation_stats: Dict[str, Dict[str, int]] = {}
        self.MIN_DEBUT_AGE = 15

    def _get_season_start_year(self) -> Optional[int]:
        if not self.current_season:
            return None
        try:
            return int(self.current_season[:4])
        except (ValueError, IndexError):
            return None

    def _is_temporally_feasible(self, birth_date: Optional[str], match_year: Optional[int] = None) -> bool:
        if not birth_date:
            return True
        if match_year is None:
            match_year = self._get_season_start_year()
        if match_year is None:
            return True
        try:
            birth_year = int(birth_date[:4])
            return (match_year - birth_year) >= self.MIN_DEBUT_AGE
        except (ValueError, IndexError):
            return True

    def create_schema(self) -> None:
        cursor = self.conn.cursor()
        self.conn.execute("PRAGMA foreign_keys = OFF;")
        drop_order = [
            "season_matchdays", "match_notes", "cards", "goals", "match_substitutions", "match_lineups",
            "match_referees", "match_coaches", "matches", "season_squads", "coach_careers",
            "player_careers", "player_aliases", "players", "coaches", "referees",
            "season_competitions", "seasons", "competitions", "teams",
            "Season_matchdays", "Match_notes", "Cards", "Goals", "Substitutions", "Match_Lineups",
            "Match_Referees", "Match_Coaches", "Matches", "Season_Squads", "Player_Careers",
            "Player_Aliases", "Players", "Coaches", "Referees", "Season_Competitions",
            "Seasons", "Competitions", "Teams", "Opponents", "Player_Season_Stats",
        ]
        for table in drop_order:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        self.conn.commit()
        self.conn.execute("PRAGMA foreign_keys = ON;")

        schema_statements = [
            """
            CREATE TABLE teams (
                team_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                normalized_name TEXT UNIQUE,
                team_type TEXT,
                profile_url TEXT
            )
            """,
            """
            CREATE TABLE competitions (
                competition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                normalized_name TEXT UNIQUE,
                level TEXT,
                gender TEXT
            )
            """,
            """
            CREATE TABLE seasons (
                season_id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT UNIQUE,
                start_year INTEGER,
                end_year INTEGER,
                team_id INTEGER,
                FOREIGN KEY (team_id) REFERENCES teams(team_id)
            )
            """,
            """
            CREATE TABLE season_competitions (
                season_competition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                season_id INTEGER,
                competition_id INTEGER,
                stage_label TEXT,
                source_path TEXT,
                UNIQUE (season_id, competition_id),
                FOREIGN KEY (season_id) REFERENCES seasons(season_id),
                FOREIGN KEY (competition_id) REFERENCES competitions(competition_id)
            )
            """,
            """
            CREATE TABLE referees (
                referee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                normalized_name TEXT UNIQUE,
                profile_url TEXT
            )
            """,
            """
            CREATE TABLE coaches (
                coach_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                normalized_name TEXT UNIQUE,
                birth_date TEXT,
                birth_place TEXT,
                nationality TEXT,
                profile_url TEXT
            )
            """,
            """
            CREATE TABLE players (
                player_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                normalized_name TEXT UNIQUE,
                birth_date TEXT,
                birth_place TEXT,
                height_cm INTEGER,
                weight_kg INTEGER,
                primary_position TEXT,
                nationality TEXT,
                profile_url TEXT,
                image_url TEXT
            )
            """,
            """
            CREATE TABLE player_aliases (
                alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                alias TEXT,
                normalized_alias TEXT,
                UNIQUE (player_id, normalized_alias),
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
            """,
            """
            CREATE TABLE player_careers (
                career_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                team_name TEXT,
                start_year INTEGER,
                end_year INTEGER,
                notes TEXT,
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
            """,
            """
            CREATE TABLE coach_careers (
                career_id INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id INTEGER,
                team_name TEXT,
                start_date TEXT,
                end_date TEXT,
                role TEXT,
                FOREIGN KEY (coach_id) REFERENCES coaches(coach_id)
            )
            """,
            """
            CREATE TABLE season_squads (
                season_squad_id INTEGER PRIMARY KEY AUTOINCREMENT,
                season_competition_id INTEGER,
                player_id INTEGER,
                position_group TEXT,
                shirt_number INTEGER,
                status TEXT,
                notes TEXT,
                UNIQUE (season_competition_id, player_id, position_group),
                FOREIGN KEY (season_competition_id) REFERENCES season_competitions(season_competition_id),
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
            """,
            """
            CREATE TABLE matches (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                season_competition_id INTEGER,
                round_name TEXT,
                matchday INTEGER,
                leg INTEGER,
                match_date TEXT,
                kickoff_time TEXT,
                venue TEXT,
                attendance INTEGER,
                referee_id INTEGER,
                home_team_id INTEGER,
                away_team_id INTEGER,
                home_score INTEGER,
                away_score INTEGER,
                halftime_home INTEGER,
                halftime_away INTEGER,
                extra_time_home INTEGER,
                extra_time_away INTEGER,
                penalties_home INTEGER,
                penalties_away INTEGER,
                source_file TEXT,
                UNIQUE (season_competition_id, source_file),
                FOREIGN KEY (season_competition_id) REFERENCES season_competitions(season_competition_id),
                FOREIGN KEY (referee_id) REFERENCES referees(referee_id),
                FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
                FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
            )
            """,
            """
            CREATE TABLE match_coaches (
                match_coach_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                team_id INTEGER,
                coach_id INTEGER,
                role TEXT,
                FOREIGN KEY (match_id) REFERENCES matches(match_id),
                FOREIGN KEY (team_id) REFERENCES teams(team_id),
                FOREIGN KEY (coach_id) REFERENCES coaches(coach_id)
            )
            """,
            """
            CREATE TABLE match_referees (
                match_referee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                referee_id INTEGER,
                role TEXT,
                FOREIGN KEY (match_id) REFERENCES matches(match_id),
                FOREIGN KEY (referee_id) REFERENCES referees(referee_id)
            )
            """,
            """
            CREATE TABLE match_lineups (
                lineup_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                team_id INTEGER,
                player_id INTEGER,
                shirt_number INTEGER,
                is_starter INTEGER,
                minute_on INTEGER,
                stoppage_on INTEGER,
                minute_off INTEGER,
                stoppage_off INTEGER,
                FOREIGN KEY (match_id) REFERENCES matches(match_id),
                FOREIGN KEY (team_id) REFERENCES teams(team_id),
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
            """,
            """
            CREATE TABLE match_substitutions (
                substitution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                team_id INTEGER,
                minute INTEGER,
                stoppage INTEGER,
                player_on_id INTEGER,
                player_off_id INTEGER,
                FOREIGN KEY (match_id) REFERENCES matches(match_id),
                FOREIGN KEY (team_id) REFERENCES teams(team_id),
                FOREIGN KEY (player_on_id) REFERENCES players(player_id),
                FOREIGN KEY (player_off_id) REFERENCES players(player_id)
            )
            """,
            """
            CREATE TABLE goals (
                goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                team_id INTEGER,
                player_id INTEGER,
                assist_player_id INTEGER,
                minute INTEGER,
                stoppage INTEGER,
                score_home INTEGER,
                score_away INTEGER,
                event_type TEXT,
                FOREIGN KEY (match_id) REFERENCES matches(match_id),
                FOREIGN KEY (team_id) REFERENCES teams(team_id),
                FOREIGN KEY (player_id) REFERENCES players(player_id),
                FOREIGN KEY (assist_player_id) REFERENCES players(player_id)
            )
            """,
            """
            CREATE TABLE cards (
                card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                team_id INTEGER,
                player_id INTEGER,
                minute INTEGER,
                stoppage INTEGER,
                card_type TEXT,
                FOREIGN KEY (match_id) REFERENCES matches(match_id),
                FOREIGN KEY (team_id) REFERENCES teams(team_id),
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
            """,
            """
            CREATE TABLE match_notes (
                note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                note TEXT,
                note_type TEXT,
                FOREIGN KEY (match_id) REFERENCES matches(match_id)
            )
            """,
            """
            CREATE TABLE season_matchdays (
                season_matchday_id INTEGER PRIMARY KEY AUTOINCREMENT,
                season_competition_id INTEGER,
                matchday INTEGER,
                date TEXT,
                position INTEGER,
                points INTEGER,
                goals_for INTEGER,
                goals_against INTEGER,
                goal_difference INTEGER,
                FOREIGN KEY (season_competition_id) REFERENCES season_competitions(season_competition_id)
            )
            """,
        ]
        for statement in schema_statements:
            cursor.execute(statement)
        self.conn.commit()

    def get_or_create_team(self, name: str, team_type: str = "club", profile_url: Optional[str] = None) -> int:
        name_clean = name.strip()
        name_lower = name_clean.lower()
        mainz_patterns = [
            'mainzer fc hassia', 'mainzer fußballclub hassia', 'mainzer fussballverein hassia',
            'mainzer fußball- und sportverein', 'mainzer fußball und sportverein', 'mainzer fsv',
            'mainzer fv', '1. mainzer fc', '1. mainzer fv', '1. mainzer fsv', 'viktoria 05 mainz',
            'reichsbahn', 'luftwaffe-sv mainz', 'mainzer tv', 'spvgg weisenau mainz',
        ]
        is_mainz_team = (
            any(pattern in name_lower for pattern in mainz_patterns)
            or (name_lower.startswith('1.') and 'mainz' in name_lower and '05' in name_lower)
            or ('mainz' in name_lower and '05' in name_lower and ('tsv' in name_lower or 'fsv' in name_lower))
            or (name_lower == 'fsv')
        )
        if is_mainz_team:
            name_clean = MAINZ_TEAM_KEY
        normalized = normalize_name(name_clean)
        normalized_profile_url = profile_url.replace("../", "") if profile_url else None

        if normalized_profile_url:
            if normalized_profile_url in self.team_profile_cache:
                return self.team_profile_cache[normalized_profile_url]
            cursor = self.conn.cursor()
            cursor.execute("SELECT team_id, name FROM teams WHERE profile_url = ?", (normalized_profile_url,))
            row = cursor.fetchone()
            if row:
                team_id, existing_name = row
                self.team_profile_cache[normalized_profile_url] = team_id
                self.team_cache[normalize_name(existing_name)] = team_id
                return team_id

        if normalized in self.team_cache:
            return self.team_cache[normalized]
        cursor = self.conn.cursor()
        cursor.execute("SELECT team_id FROM teams WHERE normalized_name = ?", (normalized,))
        row = cursor.fetchone()
        if row:
            team_id = row[0]
            if normalized_profile_url:
                cursor.execute(
                    "UPDATE teams SET profile_url = COALESCE(profile_url, ?) WHERE team_id = ?",
                    (normalized_profile_url, team_id),
                )
                self.conn.commit()
                self.team_profile_cache[normalized_profile_url] = team_id
        else:
            cursor.execute(
                """
                INSERT INTO teams (name, normalized_name, team_type, profile_url)
                VALUES (?, ?, ?, ?)
                """,
                (name_clean, normalized, team_type, normalized_profile_url),
            )
            team_id = cursor.lastrowid
            self.conn.commit()
        self.team_cache[normalized] = team_id
        if normalized_profile_url:
            self.team_profile_cache[normalized_profile_url] = team_id
        return team_id

    def get_or_create_competition(self, name: str, level: str, gender: str = "male") -> int:
        normalized = normalize_name(name)
        if normalized in self.competition_cache:
            return self.competition_cache[normalized]
        cursor = self.conn.cursor()
        cursor.execute("SELECT competition_id FROM competitions WHERE normalized_name = ?", (normalized,))
        row = cursor.fetchone()
        if row:
            competition_id = row[0]
        else:
            cursor.execute(
                """
                INSERT INTO competitions (name, normalized_name, level, gender)
                VALUES (?, ?, ?, ?)
                """,
                (name, normalized, level, gender),
            )
            competition_id = cursor.lastrowid
            self.conn.commit()
        self.competition_cache[normalized] = competition_id
        return competition_id

    def get_or_create_coach(self, name: Optional[str], profile_url: Optional[str]) -> Optional[int]:
        if not name:
            return None
        normalized = normalize_name(name)
        normalized_profile_url = profile_url.replace("../", "") if profile_url else None
        if normalized_profile_url:
            if normalized_profile_url in self.coach_profile_cache:
                return self.coach_profile_cache[normalized_profile_url]
            cursor = self.conn.cursor()
            cursor.execute("SELECT coach_id, name FROM coaches WHERE profile_url = ?", (normalized_profile_url,))
            row = cursor.fetchone()
            if row:
                coach_id, existing_name = row
                self.coach_profile_cache[normalized_profile_url] = coach_id
                self.coach_cache[normalize_name(existing_name)] = coach_id
                return coach_id
        if normalized in self.coach_cache:
            return self.coach_cache[normalized]
        cursor = self.conn.cursor()
        cursor.execute("SELECT coach_id FROM coaches WHERE normalized_name = ?", (normalized,))
        row = cursor.fetchone()
        if row:
            coach_id = row[0]
            if normalized_profile_url:
                cursor.execute(
                    "UPDATE coaches SET profile_url = COALESCE(profile_url, ?) WHERE coach_id = ?",
                    (normalized_profile_url, coach_id),
                )
                self.conn.commit()
                self.coach_profile_cache[normalized_profile_url] = coach_id
        else:
            cursor.execute(
                """
                INSERT INTO coaches (name, normalized_name, profile_url)
                VALUES (?, ?, ?)
                """,
                (name, normalized, normalized_profile_url),
            )
            coach_id = cursor.lastrowid
            self.conn.commit()
        self.coach_cache[normalized] = coach_id
        if normalized_profile_url:
            self.coach_profile_cache[normalized_profile_url] = coach_id
        return coach_id

    def get_or_create_referee(self, name: Optional[str], profile_url: Optional[str]) -> Optional[int]:
        if not name:
            return None
        normalized = normalize_name(name)
        if normalized in self.referee_cache:
            return self.referee_cache[normalized]
        cursor = self.conn.cursor()
        cursor.execute("SELECT referee_id FROM referees WHERE normalized_name = ?", (normalized,))
        row = cursor.fetchone()
        if row:
            referee_id = row[0]
        else:
            cursor.execute(
                """
                INSERT INTO referees (name, normalized_name, profile_url)
                VALUES (?, ?, ?)
                """,
                (name, normalized, profile_url),
            )
            referee_id = cursor.lastrowid
            self.conn.commit()
        self.referee_cache[normalized] = referee_id
        return referee_id

    def get_or_create_player(self, name: str, profile_url: Optional[str]) -> int:
        if not name or not name.strip():
            raise ValueError("Player name cannot be empty")
        name_clean = re.sub(r"^\d+\s+", "", name.strip())
        if name_clean.startswith('?'):
            name_clean = name_clean[1:].strip()
            if not name_clean:
                raise ValueError("Player name cannot be empty after removing '?'")
        if name_clean in {"", "-"}:
            raise ValueError("Player name cannot be '-' (placeholder)")
        name_clean = re.sub(r'^wdh\.\s*', '', name_clean, flags=re.IGNORECASE).strip()
        name_lower = name_clean.lower()
        if any(pattern in name_lower for pattern in ['trainer:', 'fsv-trainer', 'coach:', '-trainer']):
            raise ValueError(f"Invalid player name (trainer): {name_clean}")
        if any(pattern in name_lower for pattern in ['schiedsrichter:', 'schiedsrichterin:', 'referee:']):
            raise ValueError(f"Invalid player name (referee): {name_clean}")
        if name_lower.startswith('tore ') or re.match(r'^\d+\.\s*\d+:\d+', name_clean):
            raise ValueError(f"Invalid player name (goal text): {name_clean}")
        name_clean = re.sub(r'^(FE|ET|HE),\s*', '', name_clean, flags=re.IGNORECASE).strip()
        if ' an ' in name_clean.lower():
            parts = re.split(r'\s+an\s+', name_clean, flags=re.IGNORECASE)
            if len(parts) > 1 and parts[-1].strip():
                name_clean = parts[-1].strip()
        if not name_clean or name_clean == "-":
            raise ValueError("Player name cannot be empty after cleaning")
        import unicodedata
        if name_clean and not unicodedata.category(name_clean[0]).startswith('L'):
            raise ValueError(f"Invalid player name (doesn't start with letter): {name_clean}")
        if len(name_clean) < 2:
            raise ValueError(f"Invalid player name (too short): {name_clean}")
        if len(name_clean) > 100:
            raise ValueError(f"Invalid player name (too long): {name_clean}")
        if ',' in name_clean and not re.search(r'\s+an\s+', name_clean, re.IGNORECASE):
            logging.getLogger("PlayerValidation").warning(
                "Player name contains comma (might be parsing error): %s", name_clean
            )

        normalized = normalize_name(name_clean)
        normalized_profile_url = profile_url.replace("../", "") if profile_url else None
        if normalized_profile_url:
            if normalized_profile_url in self.player_profile_cache:
                cached_id = self.player_profile_cache[normalized_profile_url]
                cursor = self.conn.cursor()
                cursor.execute("SELECT birth_date FROM players WHERE player_id = ?", (cached_id,))
                bd_row = cursor.fetchone()
                if bd_row and self._is_temporally_feasible(bd_row[0]):
                    return cached_id
            else:
                cursor = self.conn.cursor()
                cursor.execute("SELECT player_id, normalized_name, name, birth_date FROM players WHERE profile_url = ?", (normalized_profile_url,))
                row = cursor.fetchone()
                if row:
                    player_id, existing_normalized, existing_name, existing_birth_date = row
                    if self._is_temporally_feasible(existing_birth_date):
                        self.player_profile_cache[normalized_profile_url] = player_id
                        if normalize_name(existing_name) != normalized:
                            self.add_player_alias(player_id, name_clean)
                        self.player_cache[existing_normalized] = player_id
                        return player_id
                    logging.getLogger("DatabaseManager").info(
                        "Skipping profile match for '%s' (birth: %s) - temporally infeasible for season %s",
                        existing_name, existing_birth_date, self.current_season,
                    )

        if normalized in self.player_cache:
            pid = self.player_cache[normalized]
            if normalized_profile_url:
                cursor = self.conn.cursor()
                cursor.execute("UPDATE players SET profile_url = COALESCE(profile_url, ?) WHERE player_id = ?", (normalized_profile_url, pid))
                self.conn.commit()
                self.player_profile_cache[normalized_profile_url] = pid
            return pid

        cursor = self.conn.cursor()
        cursor.execute("SELECT player_id FROM players WHERE normalized_name = ?", (normalized,))
        row = cursor.fetchone()
        if row:
            player_id = row[0]
            self.player_cache[normalized] = player_id
            if normalized_profile_url:
                cursor.execute(
                    "UPDATE players SET profile_url = COALESCE(profile_url, ?) WHERE player_id = ?",
                    (normalized_profile_url, player_id),
                )
                self.conn.commit()
                self.player_profile_cache[normalized_profile_url] = player_id
            return player_id

        season_year = self._get_season_start_year()
        if ' ' not in name_clean and season_year and season_year >= 1990:
            cursor.execute(
                """
                SELECT player_id, name, birth_date FROM players
                WHERE profile_url IS NOT NULL
                  AND normalized_name LIKE ?
                ORDER BY LENGTH(name) DESC
                LIMIT 1
                """,
                (f'% {normalized}',),
            )
            row = cursor.fetchone()
            if row:
                player_id, existing_name, existing_birth_date = row
                if self._is_temporally_feasible(existing_birth_date):
                    logging.getLogger("DatabaseManager").debug(
                        "Matched surname '%s' to existing player '%s' (ID: %d)",
                        name_clean, existing_name, player_id,
                    )
                    self.player_cache[normalized] = player_id
                    return player_id
                logging.getLogger("DatabaseManager").debug(
                    "Skipping surname match '%s' -> '%s' (temporally infeasible)",
                    name_clean, existing_name,
                )

        cursor.execute(
            """
            INSERT INTO players (name, normalized_name, profile_url)
            VALUES (?, ?, ?)
            """,
            (name_clean, normalized, normalized_profile_url),
        )
        player_id = cursor.lastrowid
        self.conn.commit()
        self.player_cache[normalized] = player_id
        if normalized_profile_url:
            self.player_profile_cache[normalized_profile_url] = player_id
        if self.current_season:
            stats = self.player_creation_stats.setdefault(self.current_season, {"with_url": 0, "without_url": 0})
            if normalized_profile_url:
                stats["with_url"] += 1
            else:
                stats["without_url"] += 1
        return player_id

    def add_player_alias(self, player_id: int, alias: str) -> None:
        if not alias or not alias.strip():
            return
        normalized_alias = normalize_name(alias)
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO player_aliases (player_id, alias, normalized_alias)
            VALUES (?, ?, ?)
            """,
            (player_id, alias.strip(), normalized_alias),
        )
        self.conn.commit()

    def ensure_season(self, label: str, start_year: int, end_year: int, team_id: int) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT season_id FROM seasons WHERE label = ?", (label,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute(
            """
            INSERT INTO seasons (label, start_year, end_year, team_id)
            VALUES (?, ?, ?, ?)
            """,
            (label, start_year, end_year, team_id),
        )
        season_id = cursor.lastrowid
        self.conn.commit()
        return season_id

    def ensure_season_competition(self, season_id: int, competition_id: int, stage_label: str, source_path: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT season_competition_id FROM season_competitions
            WHERE season_id = ? AND competition_id = ?
            """,
            (season_id, competition_id),
        )
        row = cursor.fetchone()
        if row:
            season_competition_id = row[0]
            cursor.execute(
                "UPDATE season_competitions SET stage_label = ?, source_path = ? WHERE season_competition_id = ?",
                (stage_label, source_path, season_competition_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO season_competitions (season_id, competition_id, stage_label, source_path)
                VALUES (?, ?, ?, ?)
                """,
                (season_id, competition_id, stage_label, source_path),
            )
            season_competition_id = cursor.lastrowid
        self.conn.commit()
        return season_competition_id

    def insert_match(
        self,
        season_competition_id: int,
        metadata: MatchMetadata,
        detail_path: str,
        referee_id: Optional[int],
        home_team_id: int,
        away_team_id: int,
    ) -> int:
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO matches
                (season_competition_id, round_name, matchday, leg, match_date, kickoff_time, venue, attendance,
                 referee_id, home_team_id, away_team_id, home_score, away_score,
                 halftime_home, halftime_away, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (season_competition_id, source_file) DO UPDATE SET
                    round_name = excluded.round_name,
                    matchday = excluded.matchday,
                    leg = excluded.leg,
                    match_date = excluded.match_date,
                    kickoff_time = excluded.kickoff_time,
                    venue = excluded.venue,
                    attendance = excluded.attendance,
                    referee_id = excluded.referee_id,
                    home_team_id = excluded.home_team_id,
                    away_team_id = excluded.away_team_id,
                    home_score = excluded.home_score,
                    away_score = excluded.away_score,
                    halftime_home = excluded.halftime_home,
                    halftime_away = excluded.halftime_away
                """,
                (
                    season_competition_id, metadata.round_name, metadata.matchday, metadata.leg, metadata.date,
                    metadata.kickoff, None, metadata.attendance, referee_id, home_team_id, away_team_id,
                    metadata.home_goals, metadata.away_goals, metadata.half_home, metadata.half_away, detail_path,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise sqlite3.IntegrityError(
                f"Failed inserting match {detail_path}: season_competition_id={season_competition_id}, "
                f"home_team_id={home_team_id}, away_team_id={away_team_id}, referee_id={referee_id}"
            ) from exc
        match_id = cursor.lastrowid
        if not match_id:
            cursor.execute(
                """
                SELECT match_id FROM matches
                WHERE season_competition_id = ? AND source_file = ?
                """,
                (season_competition_id, detail_path),
            )
            row = cursor.fetchone()
            if row:
                match_id = row[0]
            else:
                raise sqlite3.IntegrityError(
                    f"Unable to resolve match_id after upsert for {detail_path} "
                    f"(season_competition_id={season_competition_id})"
                )
        return match_id

    def add_match_coach(self, match_id: int, team_id: int, coach_id: Optional[int], role: str, parser_stats: Optional[Dict] = None) -> bool:
        if coach_id is None:
            return False
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM match_coaches
            WHERE match_id = ? AND team_id = ? AND coach_id = ? AND role = ?
            """,
            (match_id, team_id, coach_id, role),
        )
        exists = cursor.fetchone()[0] > 0
        if not exists:
            cursor.execute(
                """
                INSERT INTO match_coaches (match_id, team_id, coach_id, role)
                VALUES (?, ?, ?, ?)
                """,
                (match_id, team_id, coach_id, role),
            )
            return True
        if parser_stats:
            parser_stats['duplicates_skipped']['coaches'] += 1
        return False

    def add_match_referee(self, match_id: int, referee_id: Optional[int], role: str = "referee") -> None:
        if referee_id is None:
            return
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM match_referees
            WHERE match_id = ? AND referee_id = ? AND role = ?
            """,
            (match_id, referee_id, role),
        )
        if cursor.fetchone()[0] > 0:
            return
        cursor.execute(
            """
            INSERT INTO match_referees (match_id, referee_id, role)
            VALUES (?, ?, ?)
            """,
            (match_id, referee_id, role),
        )

    def add_lineup_entry(self, match_id: int, team_id: int, player_id: int, appearance: PlayerAppearance) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM match_lineups
            WHERE match_id = ? AND player_id = ? AND team_id = ?
            """,
            (match_id, player_id, team_id),
        )
        if cursor.fetchone()[0] > 0:
            return
        cursor.execute(
            """
            INSERT INTO match_lineups
            (match_id, team_id, player_id, shirt_number, is_starter, minute_on, stoppage_on, minute_off, stoppage_off)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id, team_id, player_id, appearance.shirt_number, 1 if appearance.is_starter else 0,
                appearance.minute_on, appearance.stoppage_on, appearance.minute_off, appearance.stoppage_off,
            ),
        )

    def add_substitution(
        self,
        match_id: int,
        team_id: int,
        minute: Optional[int],
        stoppage: Optional[int],
        player_on_id: Optional[int],
        player_off_id: Optional[int],
    ) -> None:
        if minute is None:
            return
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM match_substitutions
            WHERE match_id = ? AND player_on_id = ? AND player_off_id = ? AND minute = ? AND COALESCE(stoppage, -1) = COALESCE(?, -1)
            """,
            (match_id, player_on_id, player_off_id, minute, stoppage),
        )
        if cursor.fetchone()[0] > 0:
            return
        cursor.execute(
            """
            INSERT INTO match_substitutions
            (match_id, team_id, minute, stoppage, player_on_id, player_off_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (match_id, team_id, minute, stoppage, player_on_id, player_off_id),
        )

    def add_goal(self, match_id: int, team_id: int, goal: GoalEvent, player_id: Optional[int], assist_id: Optional[int]) -> None:
        cursor = self.conn.cursor()
        if player_id is None:
            cursor.execute(
                """
                SELECT COUNT(*) FROM goals
                WHERE match_id = ? AND player_id IS NULL AND minute = ? AND COALESCE(stoppage, -1) = COALESCE(?, -1)
                """,
                (match_id, goal.minute, goal.stoppage),
            )
        else:
            cursor.execute(
                """
                SELECT COUNT(*) FROM goals
                WHERE match_id = ? AND player_id = ? AND minute = ? AND COALESCE(stoppage, -1) = COALESCE(?, -1)
                """,
                (match_id, player_id, goal.minute, goal.stoppage),
            )
        if cursor.fetchone()[0] > 0:
            return
        cursor.execute(
            """
            INSERT INTO goals
            (match_id, team_id, player_id, assist_player_id, minute, stoppage, score_home, score_away, event_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id, team_id, player_id, assist_id, goal.minute, goal.stoppage, goal.score_home, goal.score_away,
                "own_goal" if goal.is_own_goal else ("penalty" if goal.is_penalty else "goal"),
            ),
        )

    def add_card(
        self,
        match_id: int,
        team_id: int,
        player_id: Optional[int],
        minute: Optional[int],
        stoppage: Optional[int],
        card_type: str,
    ) -> None:
        if player_id is None:
            return
        cursor = self.conn.cursor()
        if minute is None:
            cursor.execute(
                """
                SELECT COUNT(*) FROM cards
                WHERE match_id = ? AND player_id = ? AND minute IS NULL AND card_type = ?
                """,
                (match_id, player_id, card_type),
            )
        else:
            cursor.execute(
                """
                SELECT COUNT(*) FROM cards
                WHERE match_id = ? AND player_id = ? AND minute = ? AND card_type = ?
                """,
                (match_id, player_id, minute, card_type),
            )
        if cursor.fetchone()[0] > 0:
            return
        cursor.execute(
            """
            INSERT INTO cards
            (match_id, team_id, player_id, minute, stoppage, card_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (match_id, team_id, player_id, minute, stoppage, card_type),
        )

    def add_matchday_entry(
        self,
        season_competition_id: int,
        matchday: int,
        date: Optional[str],
        position: Optional[int],
        points: Optional[int],
        goals_for: Optional[int],
        goals_against: Optional[int],
    ) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO season_matchdays
            (season_competition_id, matchday, date, position, points, goals_for, goals_against, goal_difference)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                season_competition_id, matchday, date, position, points, goals_for, goals_against,
                (goals_for - goals_against) if goals_for is not None and goals_against is not None else None,
            ),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _validate_minute(self, minute: Optional[int], stoppage: Optional[int]) -> bool:
        if minute is None:
            return True
        if minute < 0 or minute > 120:
            return False
        if stoppage is not None and (stoppage < 0 or stoppage > 20):
            return False
        return True

    def _validate_player_id(self, player_id: Optional[int]) -> bool:
        if player_id is None:
            return True
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM players WHERE player_id = ?", (player_id,))
        return cursor.fetchone()[0] > 0

    def _validate_match_id(self, match_id: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM matches WHERE match_id = ?", (match_id,))
        return cursor.fetchone()[0] > 0

    def _validate_team_id(self, team_id: int) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM teams WHERE team_id = ?", (team_id,))
        return cursor.fetchone()[0] > 0

    def batch_insert_cards(self, cards_data: List[Tuple[int, int, Optional[int], Optional[int], Optional[int], str]], parser_stats: Optional[Dict] = None) -> int:
        if not cards_data:
            return 0
        cursor = self.conn.cursor()
        seen_cards = set()
        unique_cards = []
        for match_id, team_id, player_id, minute, stoppage, card_type in cards_data:
            if player_id is None:
                continue
            if not self._validate_minute(minute, stoppage):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid minute/stoppage for card: match_id={match_id}, minute={minute}, stoppage={stoppage}")
                continue
            if not self._validate_match_id(match_id):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid match_id for card: {match_id}")
                continue
            card_key = (match_id, player_id, None if minute is None else minute, card_type)
            if card_key not in seen_cards:
                seen_cards.add(card_key)
                unique_cards.append((match_id, team_id, player_id, minute, stoppage, card_type))
            elif parser_stats:
                parser_stats['duplicates_skipped']['cards'] += 1
        if not unique_cards:
            return 0
        cursor.executemany(
            """
            INSERT INTO cards
            (match_id, team_id, player_id, minute, stoppage, card_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            unique_cards,
        )
        return len(unique_cards)

    def batch_insert_goals(self, goals_data: List[Tuple[int, int, Optional[int], Optional[int], int, Optional[int], int, int, str]], parser_stats: Optional[Dict] = None) -> int:
        if not goals_data:
            return 0
        cursor = self.conn.cursor()
        seen_goals = set()
        unique_goals = []
        for match_id, team_id, player_id, assist_id, minute, stoppage, score_home, score_away, event_type in goals_data:
            if not self._validate_minute(minute, stoppage):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid minute/stoppage for goal: match_id={match_id}, minute={minute}, stoppage={stoppage}")
                continue
            if not self._validate_match_id(match_id):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid match_id for goal: {match_id}")
                continue
            if minute is None:
                goal_key = (match_id, player_id, score_home, score_away)
            else:
                goal_key = (match_id, player_id, minute, stoppage if stoppage is not None else -1)
            if goal_key not in seen_goals:
                seen_goals.add(goal_key)
                unique_goals.append((match_id, team_id, player_id, assist_id, minute, stoppage, score_home, score_away, event_type))
            elif parser_stats:
                parser_stats['duplicates_skipped']['goals'] += 1
        if not unique_goals:
            return 0
        cursor.executemany(
            """
            INSERT INTO goals
            (match_id, team_id, player_id, assist_player_id, minute, stoppage, score_home, score_away, event_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            unique_goals,
        )
        return len(unique_goals)

    def batch_insert_lineups(self, lineups_data: List[Tuple[int, int, int, Optional[int], int, Optional[int], Optional[int], Optional[int], Optional[int]]], parser_stats: Optional[Dict] = None) -> int:
        if not lineups_data:
            return 0
        cursor = self.conn.cursor()
        seen_lineups = set()
        unique_lineups = []
        for match_id, team_id, player_id, shirt_number, is_starter, minute_on, stoppage_on, minute_off, stoppage_off in lineups_data:
            if not self._validate_match_id(match_id):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid match_id for lineup: {match_id}")
                continue
            if not self._validate_player_id(player_id):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid player_id for lineup: {player_id}")
                continue
            if not self._validate_team_id(team_id):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid team_id for lineup: {team_id}")
                continue
            if minute_on is not None and not self._validate_minute(minute_on, stoppage_on):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid minute_on/stoppage_on for lineup: match_id={match_id}, minute={minute_on}, stoppage={stoppage_on}")
                continue
            if minute_off is not None and not self._validate_minute(minute_off, stoppage_off):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid minute_off/stoppage_off for lineup: match_id={match_id}, minute={minute_off}, stoppage={stoppage_off}")
                continue
            lineup_key = (match_id, player_id, team_id)
            if lineup_key not in seen_lineups:
                seen_lineups.add(lineup_key)
                unique_lineups.append((match_id, team_id, player_id, shirt_number, is_starter, minute_on, stoppage_on, minute_off, stoppage_off))
            elif parser_stats:
                parser_stats['duplicates_skipped']['lineups'] += 1
        if not unique_lineups:
            return 0
        cursor.executemany(
            """
            INSERT INTO match_lineups
            (match_id, team_id, player_id, shirt_number, is_starter, minute_on, stoppage_on, minute_off, stoppage_off)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            unique_lineups,
        )
        return len(unique_lineups)

    def batch_insert_substitutions(self, subs_data: List[Tuple[int, int, Optional[int], Optional[int], Optional[int], Optional[int]]], parser_stats: Optional[Dict] = None) -> int:
        if not subs_data:
            return 0
        cursor = self.conn.cursor()
        seen_subs = set()
        unique_subs = []
        for match_id, team_id, minute, stoppage, player_on_id, player_off_id in subs_data:
            if minute is None:
                continue
            if not self._validate_minute(minute, stoppage):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid minute/stoppage for substitution: match_id={match_id}, minute={minute}, stoppage={stoppage}")
                continue
            if not self._validate_match_id(match_id):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid match_id for substitution: {match_id}")
                continue
            sub_key = (match_id, player_on_id, player_off_id, minute, stoppage if stoppage is not None else -1)
            if sub_key not in seen_subs:
                seen_subs.add(sub_key)
                unique_subs.append((match_id, team_id, minute, stoppage, player_on_id, player_off_id))
            elif parser_stats:
                parser_stats['duplicates_skipped']['substitutions'] += 1
        if not unique_subs:
            return 0
        cursor.executemany(
            """
            INSERT INTO match_substitutions
            (match_id, team_id, minute, stoppage, player_on_id, player_off_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            unique_subs,
        )
        return len(unique_subs)

    @contextmanager
    def match_transaction(self):
        try:
            yield
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
