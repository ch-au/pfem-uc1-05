import logging
import os
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from bs4 import BeautifulSoup


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_name(name: str) -> str:
    cleaned = strip_accents(name).replace(".", " ").replace("-", " ")
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", cleaned)
    return normalize_whitespace(cleaned).lower()


def parse_int(value: str) -> Optional[int]:
    value = value.strip()
    if not value:
        return None
    value = value.replace(".", "").replace(",", "")
    if value.isdigit():
        return int(value)
    return None


def parse_minute(text: str) -> Tuple[Optional[int], Optional[int]]:
    match = re.match(r"^\s*(\d+)(?:\+(\d+))?\.", text)
    if not match:
        return None, None
    minute = int(match.group(1))
    stoppage = int(match.group(2)) if match.group(2) else None
    return minute, stoppage


def read_html(path: Path) -> Optional[BeautifulSoup]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="latin-1", errors="ignore") as handle:
            return BeautifulSoup(handle.read(), "lxml")
    except OSError as exc:
        logging.getLogger("HTMLLoader").warning("Failed to read %s: %s", path, exc)
        return None


CARD_ICON_MAP = {
    "../gelbekarte.bmp": "yellow",
    "../gelbrot.bmp": "second_yellow",
    "../rotekarte.bmp": "red",
}

GOAL_ICON = "../tor.bmp"
SUB_ICON = "../raus.bmp"

MAINZ_TEAM_KEY = "1. FSV Mainz 05"


@dataclass
class PlayerAppearance:
    name: str
    shirt_number: Optional[int]
    is_starter: bool
    minute_on: Optional[int] = None
    stoppage_on: Optional[int] = None
    minute_off: Optional[int] = None
    stoppage_off: Optional[int] = None
    card_events: List[Tuple[Optional[int], Optional[int], str]] = field(default_factory=list)


@dataclass
class GoalEvent:
    minute: int
    stoppage: Optional[int]
    score_home: int
    score_away: int
    scorer: str
    assist: Optional[str]
    team_role: str  # "home" or "away"
    is_penalty: bool = False
    is_own_goal: bool = False


@dataclass
class MatchMetadata:
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    half_home: Optional[int] = None
    half_away: Optional[int] = None
    date: Optional[str] = None
    kickoff: Optional[str] = None
    attendance: Optional[int] = None
    referee: Optional[str] = None
    referee_link: Optional[str] = None
    home_coach: Optional[str] = None
    home_coach_link: Optional[str] = None
    away_coach: Optional[str] = None
    away_coach_link: Optional[str] = None
    stage_label: Optional[str] = None
    matchday: Optional[int] = None
    round_name: Optional[str] = None
    leg: Optional[int] = None


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

    def create_schema(self) -> None:
        cursor = self.conn.cursor()
        self.conn.execute("PRAGMA foreign_keys = OFF;")
        drop_order = [
            "season_matchdays",
            "match_notes",
            "cards",
            "goals",
            "match_substitutions",
            "match_lineups",
            "match_referees",
            "match_coaches",
            "matches",
            "season_squads",
            "coach_careers",
            "player_careers",
            "player_aliases",
            "players",
            "coaches",
            "referees",
            "season_competitions",
            "seasons",
            "competitions",
            "teams",
            # legacy tables from earlier schema versions (capitalized)
            "Season_matchdays",
            "Match_notes",
            "Cards",
            "Goals",
            "Substitutions",
            "Match_Lineups",
            "Match_Referees",
            "Match_Coaches",
            "Matches",
            "Season_Squads",
            "Player_Careers",
            "Player_Aliases",
            "Players",
            "Coaches",
            "Referees",
            "Season_Competitions",
            "Seasons",
            "Competitions",
            "Teams",
            "Opponents",
            "Player_Season_Stats",
        ]
        for table in drop_order:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        self.conn.commit()
        self.conn.execute("PRAGMA foreign_keys = ON;")

        cursor.execute(
            """
            CREATE TABLE teams (
                team_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                normalized_name TEXT UNIQUE,
                team_type TEXT,
                profile_url TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE competitions (
                competition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                normalized_name TEXT UNIQUE,
                level TEXT,
                gender TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE seasons (
                season_id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT UNIQUE,
                start_year INTEGER,
                end_year INTEGER,
                team_id INTEGER,
                FOREIGN KEY (team_id) REFERENCES teams(team_id)
            )
            """
        )
        cursor.execute(
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
            """
        )
        cursor.execute(
            """
            CREATE TABLE referees (
                referee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                normalized_name TEXT UNIQUE,
                profile_url TEXT
            )
            """
        )
        cursor.execute(
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
            """
        )
        cursor.execute(
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
            """
        )
        cursor.execute(
            """
            CREATE TABLE player_aliases (
                alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                alias TEXT,
                normalized_alias TEXT,
                UNIQUE (player_id, normalized_alias),
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
            """
        )
        cursor.execute(
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
            """
        )
        cursor.execute(
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
            """
        )
        cursor.execute(
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
            """
        )
        cursor.execute(
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
            """
        )
        cursor.execute(
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
            """
        )
        cursor.execute(
            """
            CREATE TABLE match_referees (
                match_referee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                referee_id INTEGER,
                role TEXT,
                FOREIGN KEY (match_id) REFERENCES matches(match_id),
                FOREIGN KEY (referee_id) REFERENCES referees(referee_id)
            )
            """
        )
        cursor.execute(
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
            """
        )
        cursor.execute(
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
            """
        )
        cursor.execute(
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
            """
        )
        cursor.execute(
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
            """
        )
        cursor.execute(
            """
            CREATE TABLE match_notes (
                note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER,
                note TEXT,
                note_type TEXT,
                FOREIGN KEY (match_id) REFERENCES matches(match_id)
            )
            """
        )
        cursor.execute(
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
            """
        )
        self.conn.commit()

    # ----- caching helpers -------------------------------------------------

    def get_or_create_team(self, name: str, team_type: str = "club", profile_url: Optional[str] = None) -> int:
        # Normalisiere Mainz-Team-Varianten zu "1. FSV Mainz 05"
        name_clean = name.strip()
        name_lower = name_clean.lower()
        
        # Erkenne alle Mainz-Team-Varianten und normalisiere sie
        mainz_patterns = [
            'mainzer fc hassia',
            'mainzer fsv',
            'mainzer fv',
            'viktoria 05 mainz',
            'reichsbahn',  # Erfasst "Reichsbahn TSV Mainz 05" und "Reichsbahn-TSV Mainz 05"
            'luftwaffe-sv mainz',
            'mainzer tv',
            'spvgg weisenau mainz',
        ]
        
        # Prüfe ob es ein Mainz-Team ist
        is_mainz_team = any(pattern in name_lower for pattern in mainz_patterns) or \
                       (name_lower.startswith('1.') and 'mainz' in name_lower and '05' in name_lower) or \
                       ('mainz' in name_lower and '05' in name_lower and ('tsv' in name_lower or 'fsv' in name_lower))
        
        if is_mainz_team:
            name_clean = MAINZ_TEAM_KEY
        
        normalized = normalize_name(name_clean)
        if normalized in self.team_cache:
            return self.team_cache[normalized]
        cursor = self.conn.cursor()
        cursor.execute("SELECT team_id FROM teams WHERE normalized_name = ?", (normalized,))
        row = cursor.fetchone()
        if row:
            team_id = row[0]
        else:
            cursor.execute(
                """
                INSERT INTO teams (name, normalized_name, team_type, profile_url)
                VALUES (?, ?, ?, ?)
                """,
                (name_clean, normalized, team_type, profile_url),
            )
            team_id = cursor.lastrowid
            self.conn.commit()
        self.team_cache[normalized] = team_id
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
        if normalized in self.coach_cache:
            return self.coach_cache[normalized]
        cursor = self.conn.cursor()
        cursor.execute("SELECT coach_id FROM coaches WHERE normalized_name = ?", (normalized,))
        row = cursor.fetchone()
        if row:
            coach_id = row[0]
        else:
            cursor.execute(
                """
                INSERT INTO coaches (name, normalized_name, profile_url)
                VALUES (?, ?, ?)
                """,
                (name, normalized, profile_url),
            )
            coach_id = cursor.lastrowid
            self.conn.commit()
        self.coach_cache[normalized] = coach_id
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
        # Validierung: Filtere ungültige Namen
        if not name or not name.strip():
            raise ValueError("Player name cannot be empty")
        
        name_clean = name.strip()
        
        # Bereinige Namen mit "?" am Anfang (Platzhalter für unbekannten Vornamen)
        # z.B. "? SANDER" -> "SANDER"
        if name_clean.startswith('?'):
            name_clean = name_clean[1:].strip()
            if not name_clean:
                raise ValueError("Player name cannot be empty after removing '?'")
        
        # Filtere "-" als Platzhalter für "kein Name"
        if name_clean == "-" or name_clean == "":
            raise ValueError("Player name cannot be '-' (placeholder)")
        
        # Bereinige "wdh." Präfixe und ähnliche Wiederholungsmarkierungen
        name_clean = re.sub(r'^wdh\.\s*', '', name_clean, flags=re.IGNORECASE)
        
        # Filtere Trainer-Namen
        name_lower = name_clean.lower()
        if any(pattern in name_lower for pattern in ['trainer:', 'fsv-trainer', 'coach:', '-trainer']):
            raise ValueError(f"Invalid player name (trainer): {name_clean}")
        
        # Filtere Schiedsrichter-Namen
        if any(pattern in name_lower for pattern in ['schiedsrichter:', 'schiedsrichterin:', 'referee:']):
            raise ValueError(f"Invalid player name (referee): {name_clean}")
        
        # Filtere Tor-Text (beginnt mit "Tore" oder "tore")
        if name_lower.startswith('tore ') or re.match(r'^\d+\.\s*\d+:\d+', name_clean):
            raise ValueError(f"Invalid player name (goal text): {name_clean}")
        
        # Filtere Fehlertext-Präfixe ("FE,", "ET,", "HE,") - entferne sie aber behalte den Rest
        # z.B. "FE, Lipponer" -> "Lipponer"
        name_clean = re.sub(r'^(FE|ET|HE),\s*', '', name_clean, flags=re.IGNORECASE)
        name_clean = name_clean.strip()
        
        # WICHTIG: Filtere Assist-Texte mit " an " - das sind keine Spielernamen!
        # z.B. "Liebers an Klopp" -> sollte nicht als Spieler erstellt werden
        if ' an ' in name_clean.lower():
            raise ValueError(f"Invalid player name (assist text): {name_clean}")
        
        if not name_clean or name_clean == "-":
            raise ValueError("Player name cannot be empty after cleaning")
        
        # Validierung: Namen sollten mit Buchstaben beginnen (Unicode-Buchstaben erlaubt)
        import unicodedata
        if name_clean and not unicodedata.category(name_clean[0]).startswith('L'):
            raise ValueError(f"Invalid player name (doesn't start with letter): {name_clean}")
        
        # Validierung: Namen sollten nicht zu kurz sein
        if len(name_clean) < 2:
            raise ValueError(f"Invalid player name (too short): {name_clean}")
        
        # Validierung: Namen sollten nicht zu lang sein
        if len(name_clean) > 100:
            raise ValueError(f"Invalid player name (too long): {name_clean}")
        
        # Warnung bei Kommas (oft Parsing-Fehler, aber nicht immer)
        if ',' in name_clean and not re.search(r'\s+an\s+', name_clean, re.IGNORECASE):
            # Komma ohne "an" ist verdächtig
            logging.getLogger("PlayerValidation").warning(
                "Player name contains comma (might be parsing error): %s", name_clean
            )
        
        normalized = normalize_name(name_clean)
        if normalized in self.player_cache:
            return self.player_cache[normalized]
        cursor = self.conn.cursor()
        cursor.execute("SELECT player_id FROM players WHERE normalized_name = ?", (normalized,))
        row = cursor.fetchone()
        if row:
            player_id = row[0]
        else:
            cursor.execute(
                """
                INSERT INTO players (name, normalized_name, profile_url)
                VALUES (?, ?, ?)
                """,
                (name_clean, normalized, profile_url),
            )
            player_id = cursor.lastrowid
            self.conn.commit()
        self.player_cache[normalized] = player_id
        return player_id

    # ----- insert helpers --------------------------------------------------

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
                    season_competition_id,
                    metadata.round_name,
                    metadata.matchday,
                    metadata.leg,
                    metadata.date,
                    metadata.kickoff,
                    None,
                    metadata.attendance,
                    referee_id,
                    home_team_id,
                    away_team_id,
                    metadata.home_goals,
                    metadata.away_goals,
                    metadata.half_home,
                    metadata.half_away,
                    detail_path,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise sqlite3.IntegrityError(
                f"Failed inserting match {detail_path}: "
                f"season_competition_id={season_competition_id}, "
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
        # Note: commit() removed - handled by transaction manager
        return match_id

    def add_match_coach(self, match_id: int, team_id: int, coach_id: Optional[int], role: str, parser_stats: Optional[Dict] = None) -> bool:
        """
        Add a coach assignment to the database, avoiding duplicates.
        Checks if a coach assignment with the same (match_id, team_id, coach_id, role) already exists.
        Returns True if inserted, False if duplicate skipped.
        """
        if coach_id is None:
            return False
        cursor = self.conn.cursor()
        # Check for existing coach assignment to prevent duplicates
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
            # Note: commit() removed - handled by transaction manager
            return True
        else:
            # Track duplicate skipped
            if parser_stats:
                parser_stats['duplicates_skipped']['coaches'] += 1
            return False

    def add_match_referee(self, match_id: int, referee_id: Optional[int], role: str = "referee") -> None:
        """
        Add a referee assignment to the database, avoiding duplicates.
        Checks if a referee assignment with the same (match_id, referee_id, role) already exists.
        """
        if referee_id is None:
            return
        cursor = self.conn.cursor()
        # Check for existing referee assignment to prevent duplicates
        cursor.execute(
            """
            SELECT COUNT(*) FROM match_referees
            WHERE match_id = ? AND referee_id = ? AND role = ?
            """,
            (match_id, referee_id, role),
        )
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            cursor.execute(
                """
                INSERT INTO match_referees (match_id, referee_id, role)
                VALUES (?, ?, ?)
                """,
                (match_id, referee_id, role),
            )
            # Note: commit() removed - handled by transaction manager
        # If duplicate exists, silently skip (referee assignment already recorded)

    def add_lineup_entry(self, match_id: int, team_id: int, player_id: int, appearance: PlayerAppearance) -> None:
        """
        Add a lineup entry to the database, avoiding duplicates.
        Checks if a lineup entry with the same (match_id, player_id, team_id) already exists.
        """
        cursor = self.conn.cursor()
        # Check for existing lineup entry to prevent duplicates
        cursor.execute(
            """
            SELECT COUNT(*) FROM match_lineups
            WHERE match_id = ? AND player_id = ? AND team_id = ?
            """,
            (match_id, player_id, team_id),
        )
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            cursor.execute(
                """
                INSERT INTO match_lineups
                (match_id, team_id, player_id, shirt_number, is_starter, minute_on, stoppage_on, minute_off, stoppage_off)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    team_id,
                    player_id,
                    appearance.shirt_number,
                    1 if appearance.is_starter else 0,
                    appearance.minute_on,
                    appearance.stoppage_on,
                    appearance.minute_off,
                    appearance.stoppage_off,
                ),
            )
            # Note: commit() removed - handled by transaction manager
        # If duplicate exists, silently skip (lineup entry already recorded)

    def add_substitution(
        self,
        match_id: int,
        team_id: int,
        minute: Optional[int],
        stoppage: Optional[int],
        player_on_id: Optional[int],
        player_off_id: Optional[int],
    ) -> None:
        """
        Add a substitution event to the database, avoiding duplicates.
        Checks if a substitution with the same (match_id, player_on_id, player_off_id, minute) already exists.
        """
        if minute is None:
            return
        cursor = self.conn.cursor()
        # Check for existing substitution to prevent duplicates
        cursor.execute(
            """
            SELECT COUNT(*) FROM match_substitutions
            WHERE match_id = ? AND player_on_id = ? AND player_off_id = ? AND minute = ? AND COALESCE(stoppage, -1) = COALESCE(?, -1)
            """,
            (match_id, player_on_id, player_off_id, minute, stoppage),
        )
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            cursor.execute(
                """
                INSERT INTO match_substitutions
                (match_id, team_id, minute, stoppage, player_on_id, player_off_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (match_id, team_id, minute, stoppage, player_on_id, player_off_id),
            )
            # Note: commit() removed - handled by transaction manager
        # If duplicate exists, silently skip (substitution already recorded)

    def add_goal(self, match_id: int, team_id: int, goal: GoalEvent, player_id: Optional[int], assist_id: Optional[int]) -> None:
        """
        Add a goal event to the database, avoiding duplicates.
        Checks if a goal with the same (match_id, player_id, minute, stoppage) already exists.
        """
        if player_id is None:
            # Own goals can have NULL player_id, but we still want to prevent duplicates
            # In this case, we check by match_id, minute, stoppage, and score
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM goals
                WHERE match_id = ? AND player_id IS NULL AND minute = ? AND COALESCE(stoppage, -1) = COALESCE(?, -1)
                """,
                (match_id, goal.minute, goal.stoppage),
            )
            exists = cursor.fetchone()[0] > 0
        else:
            cursor = self.conn.cursor()
            # Check for existing goal to prevent duplicates
            cursor.execute(
                """
                SELECT COUNT(*) FROM goals
                WHERE match_id = ? AND player_id = ? AND minute = ? AND COALESCE(stoppage, -1) = COALESCE(?, -1)
                """,
                (match_id, player_id, goal.minute, goal.stoppage),
            )
            exists = cursor.fetchone()[0] > 0
        
        if not exists:
            cursor.execute(
                """
                INSERT INTO goals
                (match_id, team_id, player_id, assist_player_id, minute, stoppage, score_home, score_away, event_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    team_id,
                    player_id,
                    assist_id,
                    goal.minute,
                    goal.stoppage,
                    goal.score_home,
                    goal.score_away,
                    "own_goal" if goal.is_own_goal else ("penalty" if goal.is_penalty else "goal"),
                ),
            )
            # Note: commit() removed - handled by transaction manager
        # If duplicate exists, silently skip (goal already recorded)

    def add_card(
        self,
        match_id: int,
        team_id: int,
        player_id: Optional[int],
        minute: Optional[int],
        stoppage: Optional[int],
        card_type: str,
    ) -> None:
        """
        Add a card event to the database, avoiding duplicates.
        Checks if a card with the same (match_id, player_id, minute, card_type) already exists.
        Handles NULL minute values correctly (94.5% of cards have NULL minute).
        """
        if player_id is None:
            return
        
        cursor = self.conn.cursor()
        # Check for existing card to prevent duplicates
        # Use separate queries for NULL vs non-NULL minute (94.5% have NULL minute)
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
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            cursor.execute(
                """
                INSERT INTO cards
                (match_id, team_id, player_id, minute, stoppage, card_type)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (match_id, team_id, player_id, minute, stoppage, card_type),
            )
            # Note: commit() removed - handled by transaction manager
        # If duplicate exists, silently skip (card already recorded)

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
                season_competition_id,
                matchday,
                date,
                position,
                points,
                goals_for,
                goals_against,
                (goals_for - goals_against) if goals_for is not None and goals_against is not None else None,
            ),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def _validate_minute(self, minute: Optional[int], stoppage: Optional[int]) -> bool:
        """Validate minute and stoppage values. Returns True if valid."""
        if minute is None:
            return True  # NULL minute is valid (e.g., cards from lineups)
        if minute < 0 or minute > 120:
            return False
        if stoppage is not None and (stoppage < 0 or stoppage > 20):
            return False
        return True
    
    def _validate_player_id(self, player_id: Optional[int]) -> bool:
        """Validate player_id exists. Returns True if valid."""
        if player_id is None:
            return True  # NULL is valid for own goals
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM players WHERE player_id = ?", (player_id,))
        return cursor.fetchone()[0] > 0
    
    def _validate_match_id(self, match_id: int) -> bool:
        """Validate match_id exists. Returns True if valid."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM matches WHERE match_id = ?", (match_id,))
        return cursor.fetchone()[0] > 0
    
    def _validate_team_id(self, team_id: int) -> bool:
        """Validate team_id exists. Returns True if valid."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM teams WHERE team_id = ?", (team_id,))
        return cursor.fetchone()[0] > 0

    def batch_insert_cards(self, cards_data: List[Tuple[int, int, Optional[int], Optional[int], Optional[int], str]], parser_stats: Optional[Dict] = None) -> int:
        """
        Batch insert cards with deduplication and validation.
        cards_data: List of tuples (match_id, team_id, player_id, minute, stoppage, card_type)
        Returns number of cards inserted.
        """
        if not cards_data:
            return 0
        
        cursor = self.conn.cursor()
        
        # Deduplicate in-memory first
        seen_cards = set()
        unique_cards = []
        
        for match_id, team_id, player_id, minute, stoppage, card_type in cards_data:
            if player_id is None:
                continue
            
            # Validate data
            if not self._validate_minute(minute, stoppage):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid minute/stoppage for card: match_id={match_id}, minute={minute}, stoppage={stoppage}")
                continue
            
            if not self._validate_match_id(match_id):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid match_id for card: {match_id}")
                continue
            
            # Create unique key for deduplication
            if minute is None:
                card_key = (match_id, player_id, None, card_type)
            else:
                card_key = (match_id, player_id, minute, card_type)
            
            if card_key not in seen_cards:
                seen_cards.add(card_key)
                unique_cards.append((match_id, team_id, player_id, minute, stoppage, card_type))
            elif parser_stats:
                parser_stats['duplicates_skipped']['cards'] += 1
        
        if not unique_cards:
            return 0
        
        # Batch insert
        cursor.executemany(
            """
            INSERT INTO cards
            (match_id, team_id, player_id, minute, stoppage, card_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            unique_cards,
        )
        # Note: commit() removed - handled by transaction manager
        return len(unique_cards)
    
    def batch_insert_goals(self, goals_data: List[Tuple[int, int, Optional[int], Optional[int], int, Optional[int], int, int, str]], parser_stats: Optional[Dict] = None) -> int:
        """
        Batch insert goals with deduplication and validation.
        goals_data: List of tuples (match_id, team_id, player_id, assist_id, minute, stoppage, score_home, score_away, event_type)
        Returns number of goals inserted.
        """
        if not goals_data:
            return 0
        
        cursor = self.conn.cursor()
        
        # Deduplicate in-memory first
        seen_goals = set()
        unique_goals = []
        
        for match_id, team_id, player_id, assist_id, minute, stoppage, score_home, score_away, event_type in goals_data:
            # Validate data
            if not self._validate_minute(minute, stoppage):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid minute/stoppage for goal: match_id={match_id}, minute={minute}, stoppage={stoppage}")
                continue
            
            if not self._validate_match_id(match_id):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid match_id for goal: {match_id}")
                continue
            
            # Create unique key for deduplication (using COALESCE for stoppage)
            stoppage_key = stoppage if stoppage is not None else -1
            goal_key = (match_id, player_id, minute, stoppage_key)
            
            if goal_key not in seen_goals:
                seen_goals.add(goal_key)
                unique_goals.append((match_id, team_id, player_id, assist_id, minute, stoppage, score_home, score_away, event_type))
            elif parser_stats:
                parser_stats['duplicates_skipped']['goals'] += 1
        
        if not unique_goals:
            return 0
        
        # Batch insert
        cursor.executemany(
            """
            INSERT INTO goals
            (match_id, team_id, player_id, assist_player_id, minute, stoppage, score_home, score_away, event_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            unique_goals,
        )
        # Note: commit() removed - handled by transaction manager
        return len(unique_goals)
    
    def batch_insert_lineups(self, lineups_data: List[Tuple[int, int, int, Optional[int], int, Optional[int], Optional[int], Optional[int], Optional[int]]], parser_stats: Optional[Dict] = None) -> int:
        """
        Batch insert lineup entries with deduplication and validation.
        lineups_data: List of tuples (match_id, team_id, player_id, shirt_number, is_starter, minute_on, stoppage_on, minute_off, stoppage_off)
        Returns number of lineups inserted.
        """
        if not lineups_data:
            return 0
        
        cursor = self.conn.cursor()
        
        # Deduplicate in-memory first
        seen_lineups = set()
        unique_lineups = []
        
        for match_id, team_id, player_id, shirt_number, is_starter, minute_on, stoppage_on, minute_off, stoppage_off in lineups_data:
            # Validate data
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
            
            # Validate minutes if present
            if minute_on is not None and not self._validate_minute(minute_on, stoppage_on):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid minute_on/stoppage_on for lineup: match_id={match_id}, minute={minute_on}, stoppage={stoppage_on}")
                continue
            
            if minute_off is not None and not self._validate_minute(minute_off, stoppage_off):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid minute_off/stoppage_off for lineup: match_id={match_id}, minute={minute_off}, stoppage={stoppage_off}")
                continue
            
            # Create unique key for deduplication
            lineup_key = (match_id, player_id, team_id)
            
            if lineup_key not in seen_lineups:
                seen_lineups.add(lineup_key)
                unique_lineups.append((match_id, team_id, player_id, shirt_number, is_starter, minute_on, stoppage_on, minute_off, stoppage_off))
            elif parser_stats:
                parser_stats['duplicates_skipped']['lineups'] += 1
        
        if not unique_lineups:
            return 0
        
        # Batch insert
        cursor.executemany(
            """
            INSERT INTO match_lineups
            (match_id, team_id, player_id, shirt_number, is_starter, minute_on, stoppage_on, minute_off, stoppage_off)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            unique_lineups,
        )
        # Note: commit() removed - handled by transaction manager
        return len(unique_lineups)
    
    def batch_insert_substitutions(self, subs_data: List[Tuple[int, int, Optional[int], Optional[int], Optional[int], Optional[int]]], parser_stats: Optional[Dict] = None) -> int:
        """
        Batch insert substitutions with deduplication and validation.
        subs_data: List of tuples (match_id, team_id, minute, stoppage, player_on_id, player_off_id)
        Returns number of substitutions inserted.
        """
        if not subs_data:
            return 0
        
        cursor = self.conn.cursor()
        
        # Deduplicate in-memory first
        seen_subs = set()
        unique_subs = []
        
        for match_id, team_id, minute, stoppage, player_on_id, player_off_id in subs_data:
            if minute is None:
                continue
            
            # Validate data
            if not self._validate_minute(minute, stoppage):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid minute/stoppage for substitution: match_id={match_id}, minute={minute}, stoppage={stoppage}")
                continue
            
            if not self._validate_match_id(match_id):
                if parser_stats:
                    parser_stats['warnings'].append(f"Invalid match_id for substitution: {match_id}")
                continue
            
            # Create unique key for deduplication (using COALESCE for stoppage)
            stoppage_key = stoppage if stoppage is not None else -1
            sub_key = (match_id, player_on_id, player_off_id, minute, stoppage_key)
            
            if sub_key not in seen_subs:
                seen_subs.add(sub_key)
                unique_subs.append((match_id, team_id, minute, stoppage, player_on_id, player_off_id))
            elif parser_stats:
                parser_stats['duplicates_skipped']['substitutions'] += 1
        
        if not unique_subs:
            return 0
        
        # Batch insert
        cursor.executemany(
            """
            INSERT INTO match_substitutions
            (match_id, team_id, minute, stoppage, player_on_id, player_off_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            unique_subs,
        )
        # Note: commit() removed - handled by transaction manager
        return len(unique_subs)

    @contextmanager
    def match_transaction(self):
        """
        Context manager for match-level transactions.
        Automatically commits on success, rolls back on exception.
        """
        try:
            yield
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise


class ComprehensiveFSVParser:
    """Parse the FSV Mainz 05 archive into a relational SQLite database."""

    def __init__(
        self,
        base_path: str = "fsvarchiv",
        db_name: str = "fsv_archive_complete.db",
        seasons: Optional[Sequence[str]] = None,
    ):
        self.base_path = Path(base_path)
        self.db = DatabaseManager(db_name)
        self.seasons_filter = set(seasons) if seasons else None
        self.mainz_team_id = self.db.get_or_create_team(MAINZ_TEAM_KEY, team_type="club")
        self.match_cache: Dict[Tuple[str, str], int] = {}
        self.players_processed: Dict[str, bool] = {}
        self.player_file_index = self.build_player_index()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Error statistics tracking
        self.stats = {
            'matches_processed': 0,
            'matches_successful': 0,
            'matches_failed': 0,
            'errors': [],
            'warnings': [],
            'duplicates_skipped': {
                'cards': 0,
                'goals': 0,
                'substitutions': 0,
                'lineups': 0,
                'coaches': 0,
                'referees': 0,
            }
        }

    # ------------------------------------------------------------------ utils
    def iter_seasons(self) -> Iterable[str]:
        if not self.base_path.exists():
            raise FileNotFoundError(f"Base path '{self.base_path}' does not exist")
        for entry in sorted(self.base_path.iterdir()):
            if not entry.is_dir():
                continue
            if not re.match(r"\d{4}-\d{2}", entry.name):
                continue
            if self.seasons_filter and entry.name not in self.seasons_filter:
                continue
            yield entry.name

    # ---------------------------------------------------------------- matches
    def _is_mainz_team(self, text: str) -> bool:
        cleaned = text.lower()
        if "mainz" not in cleaned and "fsv" not in cleaned:
            return False
        return "mainz" in cleaned or "fsv" in cleaned or "05" in cleaned

    def _clean_team_name(self, text: str) -> str:
        return normalize_whitespace(text)

    def parse_season(self, season_name: str) -> None:
        season_path = self.base_path / season_name
        start_year = int(season_name[:4])
        end_year = int("20" + season_name[-2:]) if int(season_name[-2:]) <= 30 else int("19" + season_name[-2:])
        season_id = self.db.ensure_season(season_name, start_year, end_year, self.mainz_team_id)

        self.logger.info("Processing season %s", season_name)

        # Find league file and extract league name
        league_name = None
        league_file = None
        for filename in ['profiliga.html', 'profitab.html', 'profitabb.html']:
            candidate = season_path / filename
            if candidate.exists():
                league_name = self._extract_league_from_html(candidate)
                if league_name:
                    league_file = candidate
                    break
        
        # Fallback to "Bundesliga" if no league found (shouldn't happen for valid seasons)
        if not league_name:
            league_name = "Bundesliga"
            league_file = season_path / "profiliga.html"
            self.logger.warning("Could not extract league name for %s, defaulting to Bundesliga", season_name)

        # Determine competition level based on league name
        league_level = self._determine_league_level(league_name)

        overview_files = [
            (league_name, league_level, league_file),
            ("DFB-Pokal", "cup", season_path / "profipokal.html"),
        ]

        # Add European competitions if present
        for european_stub in ["profiuefa", "profiuec", "profiuecl", "profiintertoto", "profiueclq"]:
            overview = season_path / f"{european_stub}.html"
            if overview.exists():
                overview_files.append(("Europapokal", "international", overview))
        
        # Add friendly matches (Freundschaftsspiele)
        # "profirest" = "Profi Rest" = Freundschaftsspiele
        profirest_file = season_path / "profirest.html"
        if profirest_file.exists():
            overview_files.append(("Freundschaftsspiele", "friendly", profirest_file))

        for competition_label, level, overview_path in overview_files:
            if not overview_path.exists():
                continue

            competition_id = self.db.get_or_create_competition(competition_label, level)
            actual_overview_path, matches = self.parse_competition_overview(season_path, overview_path)
            try:
                source_relpath = actual_overview_path.relative_to(self.base_path)
            except ValueError:
                source_relpath = overview_path.relative_to(self.base_path)
            season_competition_id = self.db.ensure_season_competition(
                season_id, competition_id, competition_label, str(source_relpath)
            )

            self.logger.info("  %s: %d fixtures", competition_label, len(matches))
            if matches:
                seen_details: set[str] = set()
                for match in matches:
                    detail_path = season_path / match["detail_file"]
                    detail_rel = str(detail_path.relative_to(self.base_path))
                    if detail_rel in seen_details:
                        self.logger.debug(
                            "    skipping duplicate detail page %s for %s", detail_rel, competition_label
                        )
                        continue
                    seen_details.add(detail_rel)
                    if not detail_path.exists():
                        self.logger.warning("    detail page missing: %s", detail_rel)
                        continue
                    try:
                        metadata, lineups, substitutions, goals, cards = self.parse_match_detail(
                            detail_path, match, season_path
                        )
                    except (FileNotFoundError, ValueError) as exc:
                        self.logger.warning("    skipping %s (%s)", detail_rel, exc)
                        continue

                    home_team_id = self.db.get_or_create_team(metadata.home_team)
                    away_team_id = self.db.get_or_create_team(metadata.away_team)
                    referee_id = self.db.get_or_create_referee(metadata.referee, metadata.referee_link)

                    # Use transaction context manager for atomic match processing
                    try:
                        with self.db.match_transaction():
                            match_id = self.db.insert_match(
                                season_competition_id,
                                metadata,
                                detail_rel,
                                referee_id,
                                home_team_id,
                                away_team_id,
                            )
                            self.db.add_match_referee(match_id, referee_id)

                            home_coach_id = self.db.get_or_create_coach(metadata.home_coach, metadata.home_coach_link)
                            away_coach_id = self.db.get_or_create_coach(metadata.away_coach, metadata.away_coach_link)

                            self.db.add_match_coach(match_id, home_team_id, home_coach_id, "head_coach", self.stats)
                            self.db.add_match_coach(match_id, away_team_id, away_coach_id, "head_coach", self.stats)

                            # Collect data for batch inserts
                            lineups_batch = []
                            subs_batch = []
                            goals_batch = []
                            cards_batch = []

                            for role, team_id, roster in (
                                ("home", home_team_id, lineups["home"]),
                                ("away", away_team_id, lineups["away"]),
                            ):
                                for appearance in roster.values():
                                    try:
                                        player_id = self.db.get_or_create_player(appearance.name, appearance.__dict__.get("profile_url"))
                                    except ValueError as e:
                                        self.logger.warning("Skipping invalid player name: %s (%s)", appearance.name, e)
                                        continue
                                    # Collect lineup data for batch insert
                                    lineups_batch.append((
                                        match_id, team_id, player_id, appearance.shirt_number,
                                        1 if appearance.is_starter else 0,
                                        appearance.minute_on, appearance.stoppage_on,
                                        appearance.minute_off, appearance.stoppage_off
                                    ))
                                    # NOTE: Cards are NOT inserted here to avoid duplicates
                                    # Cards are inserted later from the unified 'cards' list which includes
                                    # cards from appearance.card_events, substitutions, etc.
                                    # This prevents double insertion of the same card event.
                                    if appearance.name not in self.players_processed:
                                        self.parse_player_profile(appearance.name, season_path)
                                        self.players_processed[appearance.name] = True

                            for sub in substitutions:
                                team_id = home_team_id if sub["team_role"] == "home" else away_team_id
                                try:
                                    player_on_id = self.db.get_or_create_player(sub["player_on"], sub.get("player_on_link"))
                                except ValueError as e:
                                    self.logger.warning("Skipping invalid substitution player_on: %s (%s)", sub["player_on"], e)
                                    continue
                                try:
                                    player_off_id = self.db.get_or_create_player(sub["player_off"], sub.get("player_off_link"))
                                except ValueError as e:
                                    self.logger.warning("Skipping invalid substitution player_off: %s (%s)", sub["player_off"], e)
                                    continue
                                # Collect substitution data for batch insert
                                subs_batch.append((
                                    match_id, team_id, sub["minute"], sub["stoppage"],
                                    player_on_id, player_off_id
                                ))

                            for goal in goals:
                                team_id = home_team_id if goal.team_role == "home" else away_team_id
                                try:
                                    player_id = self.db.get_or_create_player(goal.scorer, None)
                                except ValueError as e:
                                    self.logger.warning("Skipping invalid goal scorer: %s (%s)", goal.scorer, e)
                                    continue
                                assist_id = None
                                if goal.assist:
                                    try:
                                        assist_id = self.db.get_or_create_player(goal.assist, None)
                                    except ValueError as e:
                                        self.logger.warning("Skipping invalid goal assist: %s (%s)", goal.assist, e)
                                # Collect goal data for batch insert
                                goals_batch.append((
                                    match_id, team_id, player_id, assist_id,
                                    goal.minute, goal.stoppage, goal.score_home, goal.score_away,
                                    "own_goal" if goal.is_own_goal else ("penalty" if goal.is_penalty else "goal")
                                ))

                            for card in cards:
                                team_id = home_team_id if card["team_role"] == "home" else away_team_id
                                try:
                                    player_id = self.db.get_or_create_player(card["player"], None)
                                except ValueError as e:
                                    self.logger.warning("Skipping invalid card player: %s (%s)", card["player"], e)
                                    continue
                                # Collect card data for batch insert
                                cards_batch.append((
                                    match_id, team_id, player_id,
                                    card["minute"], card["stoppage"], card["card_type"]
                                ))

                            # Execute batch inserts
                            self.db.batch_insert_lineups(lineups_batch, self.stats)
                            self.db.batch_insert_substitutions(subs_batch, self.stats)
                            self.db.batch_insert_goals(goals_batch, self.stats)
                            self.db.batch_insert_cards(cards_batch, self.stats)
                        
                        self.stats['matches_processed'] += 1
                        self.stats['matches_successful'] += 1
                    except Exception as exc:
                        self.stats['matches_processed'] += 1
                        self.stats['matches_failed'] += 1
                        error_msg = f"Match {detail_rel}: {str(exc)}"
                        self.stats['errors'].append(error_msg)
                        self.logger.error(error_msg, exc_info=True)
                        # Continue with next match (transaction rollback already handled)
                        continue
            else:
                fallback_matches = self.parse_profitab_fallback(season_path, competition_label)
                if fallback_matches:
                    self.logger.info(
                        "  %s: using fallback tab data for %d fixtures", competition_label, len(fallback_matches)
                    )
                    for metadata, source_rel in fallback_matches:
                        home_team_id = self.db.get_or_create_team(metadata.home_team)
                        away_team_id = self.db.get_or_create_team(metadata.away_team)
                        referee_id = self.db.get_or_create_referee(metadata.referee, metadata.referee_link)
                        
                        # Use transaction context manager for atomic match processing
                        with self.db.match_transaction():
                            match_id = self.db.insert_match(
                                season_competition_id,
                                metadata,
                                source_rel,
                                referee_id,
                                home_team_id,
                                away_team_id,
                            )
                            self.db.add_match_referee(match_id, referee_id)
                else:
                    self.logger.info("  %s: no fixtures available", competition_label)

            self.parse_season_table(season_competition_id, season_path, actual_overview_path.name)
            if competition_label == "Bundesliga":
                self.parse_season_squad(season_competition_id, season_path)

    # ---------------------------------------------------------------- parse overview
    def _load_overview_document(self, overview_path: Path) -> Tuple[Path, Optional[BeautifulSoup]]:
        current_path = overview_path
        visited: set[str] = set()
        while True:
            soup = read_html(current_path)
            if soup is None:
                return current_path, None

            frameset = soup.find("frameset")
            if not frameset:
                return current_path, soup

            resolved = str(current_path.resolve())
            if resolved in visited:
                self.logger.warning("Recursive frameset detected while resolving %s", current_path)
                return current_path, soup
            visited.add(resolved)

            frames = frameset.find_all("frame")
            if not frames:
                return current_path, soup

            preferred_src = None
            for frame in frames:
                src = frame.get("src")
                if not src:
                    continue
                name = (frame.get("name") or "").lower()
                if name in {"tabelle", "table", "main", "inhalt", "content"}:
                    preferred_src = src
                    break
            if not preferred_src:
                for frame in frames:
                    src = frame.get("src")
                    if src and re.search(r"\d", src):
                        preferred_src = src
                        break
            if not preferred_src:
                for frame in frames:
                    src = frame.get("src")
                    if src:
                        preferred_src = src
                        break

            if not preferred_src:
                return current_path, soup

            next_path = current_path.parent / preferred_src
            if not next_path.exists():
                self.logger.warning(
                    "Frame source %s referenced from %s does not exist", preferred_src, current_path
                )
                return current_path, soup

            self.logger.debug("Resolved framed overview %s → %s", current_path, next_path)
            current_path = next_path

    def _determine_league_level(self, league_name: str) -> str:
        """Determine competition level based on league name.
        
        Args:
            league_name: Name of the league/competition
            
        Returns:
            Level string: 'first_division', 'second_division', 'third_division', 
                         'amateur', 'historical', 'cup', 'international', or 'other'
        """
        lower = league_name.lower()
        
        # 1. Bundesliga (without "2.")
        if 'bundesliga' in lower and '2.' not in lower and 'süd' not in lower:
            return 'first_division'
        
        # 2. Bundesliga
        if '2. bundesliga' in lower or '2.bundesliga' in lower:
            return 'second_division'
        
        # 3. Liga / Regionalliga  
        if 'regionalliga' in lower:
            return 'third_division'
        
        # Amateur/Oberliga
        if any(x in lower for x in ['amateur', 'oberliga', 'amateurliga']):
            return 'amateur'
        
        # Historical leagues
        if any(x in lower for x in ['gauliga', 'bezirks', 'kreis', 'klasse']):
            return 'historical'
        
        # Cup competitions
        if 'pokal' in lower:
            return 'cup'
        
        # International competitions
        if any(x in lower for x in ['europapokal', 'champions league', 'europa league', 'uefa']):
            return 'international'
        
        # Default
        return 'other'

    def _extract_league_from_html(self, overview_path: Path) -> Optional[str]:
        """Extract league name from HTML title tag.
        
        Looks for format "Title: League Name" in <b> tag.
        Falls back to filename-based detection if title parsing fails.
        
        Args:
            overview_path: Path to HTML file (profiliga.html, profitab.html, etc.)
            
        Returns:
            League name if found, None otherwise
        """
        actual_path, soup = self._load_overview_document(overview_path)
        if soup is None:
            return None
        
        # Try to extract from <b> tag title
        title_tag = soup.find('b')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Extract league name after colon
            if ':' in title_text:
                league = title_text.split(':')[1].strip()
                if league:
                    self.logger.debug("Extracted league '%s' from %s", league, overview_path.name)
                    return league
        
        # Fallback: try to detect from filename or content
        stem = actual_path.stem.lower()
        if 'pokal' in stem:
            return None  # Cup competitions handled separately
        if 'liga' in stem:
            # Default to Bundesliga if no specific league found
            return "Bundesliga"
        
        return None

    def parse_competition_overview(
        self, season_path: Path, overview_path: Path
    ) -> Tuple[Path, List[Dict[str, Optional[str]]]]:
        actual_path, soup = self._load_overview_document(overview_path)
        if soup is None:
            return actual_path, []

        matches: List[Dict[str, Optional[str]]] = []
        tables = soup.find_all("table")

        current_matchday = 0
        is_league = "liga" in actual_path.stem.lower()
        for table in tables:
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue
                score_link = None
                for cell in cells:
                    anchor = cell.find("a", href=True)
                    if not anchor:
                        continue
                    href = anchor["href"]
                    if re.search(r"profi[a-z]*\d+\.html", href, re.IGNORECASE):
                        score_link = anchor
                        break
                if not score_link or not score_link.get("href"):
                    continue
                detail_href = score_link["href"]

                opponent_anchor = None
                for anchor in row.find_all("a", href=True):
                    if "gegner" in anchor["href"].lower():
                        opponent_anchor = anchor
                        break
                if not opponent_anchor:
                    continue
                opponent_name = normalize_whitespace(opponent_anchor.get_text(" ", strip=True))

                stage_text = None
                stage_candidates = [normalize_whitespace(c.get_text(" ", strip=True)) for c in cells]
                for candidate in stage_candidates:
                    if candidate.startswith("(") and candidate.endswith(")"):
                        stage_text = candidate.strip("()")
                        break

                score_text = normalize_whitespace(score_link.get_text(" ", strip=True))
                if is_league:
                    current_matchday += 1

                matches.append(
                    {
                        "detail_file": detail_href,
                        "opponent": opponent_name,
                        "score": score_text,
                        "matchday": current_matchday if is_league else None,
                        "stage": stage_text,
                    }
                )
        return actual_path, matches

    def parse_profitab_fallback(self, season_path: Path, competition_label: str) -> List[Tuple[MatchMetadata, str]]:
        tab_dir = season_path / "tab"
        if not tab_dir.exists():
            return []

        fallback_matches: List[Tuple[MatchMetadata, str]] = []

        for tab_file in sorted(tab_dir.glob("profitab*.html")):
            soup = read_html(tab_file)
            if soup is None:
                continue

            matchday = None
            date_iso = None

            filename_match = re.search(r"profitab(\d+)", tab_file.stem, re.IGNORECASE)
            if filename_match:
                matchday = int(filename_match.group(1))

            header_node = soup.find(string=re.compile(r"Spieltag", re.IGNORECASE))
            if header_node:
                header_text = normalize_whitespace(header_node)
                header_match = re.search(r"(\d+)\.\s*Spieltag(?:,\s*(\d{2}\.\d{2}\.\d{4}))?", header_text)
                if header_match:
                    if matchday is None:
                        matchday = int(header_match.group(1))
                    date_str = header_match.group(2)
                    if date_str:
                        try:
                            date_iso = datetime.strptime(date_str, "%d.%m.%Y").strftime("%Y-%m-%d")
                        except ValueError:
                            date_iso = None

            main_table = soup.find("table", width="550")
            if not main_table:
                main_table = soup.find("table")
            if not main_table:
                continue

            for row in main_table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue

                left_text = normalize_whitespace(cells[1].get_text(" ", strip=True))
                right_text = normalize_whitespace(cells[3].get_text(" ", strip=True))
                result_text = normalize_whitespace(cells[4].get_text(" ", strip=True))

                left_is_mainz = self._is_mainz_team(left_text)
                right_is_mainz = self._is_mainz_team(right_text)
                if not (left_is_mainz or right_is_mainz):
                    continue

                score_match = re.search(r"(\d+)\s*[:\-]\s*(\d+)", result_text)
                if not score_match:
                    continue

                home_goals = int(score_match.group(1))
                away_goals = int(score_match.group(2))

                if left_is_mainz and right_is_mainz:
                    # Should not happen, skip ambiguous rows.
                    continue

                home_team = self._clean_team_name(left_text)
                away_team = self._clean_team_name(right_text)
                is_mainz_home = left_is_mainz

                metadata = MatchMetadata(
                    home_team=home_team,
                    away_team=away_team,
                    home_goals=home_goals,
                    away_goals=away_goals,
                    half_home=None,
                    half_away=None,
                    date=date_iso,
                    kickoff=None,
                    attendance=None,
                    referee=None,
                    referee_link=None,
                    home_coach=None,
                    home_coach_link=None,
                    away_coach=None,
                    away_coach_link=None,
                    matchday=matchday,
                    round_name=f"{matchday}. Spieltag" if matchday is not None else None,
                    leg=None,
                )

                source_rel = f"tab/{tab_file.name}#fallback"
                fallback_matches.append((metadata, source_rel))

        return fallback_matches

    # ---------------------------------------------------------------- detail parsing
    def parse_match_detail(self, detail_path: Path, overview_info: Dict[str, Optional[str]], season_path: Path):
        soup = read_html(detail_path)
        if soup is None:
            raise FileNotFoundError(detail_path)

        header = soup.find("b")
        header_text = normalize_whitespace(header.get_text(" ", strip=True)) if header else ""
        home_team, away_team, score_home, score_away, half_home, half_away = self.parse_header_score(header_text)
        stage_label = overview_info.get("stage")
        matchday = overview_info.get("matchday")

        detail_info = self.extract_match_details(soup)
        mainz_is_home = "FSV" in home_team or "Mainz" in home_team
        home_coach = detail_info.get("mainz_coach") if mainz_is_home else detail_info.get("opponent_coach")
        home_coach_link = detail_info.get("mainz_coach_link") if mainz_is_home else detail_info.get("opponent_coach_link")
        away_coach = detail_info.get("opponent_coach") if mainz_is_home else detail_info.get("mainz_coach")
        away_coach_link = detail_info.get("opponent_coach_link") if mainz_is_home else detail_info.get("mainz_coach_link")

        metadata = MatchMetadata(
            home_team=home_team,
            away_team=away_team,
            home_goals=score_home,
            away_goals=score_away,
            half_home=half_home,
            half_away=half_away,
            date=detail_info.get("date"),
            kickoff=detail_info.get("kickoff"),
            attendance=detail_info.get("attendance"),
            referee=detail_info.get("referee"),
            referee_link=detail_info.get("referee_link"),
            home_coach=home_coach,
            home_coach_link=home_coach_link,
            away_coach=away_coach,
            away_coach_link=away_coach_link,
            matchday=int(matchday) if isinstance(matchday, int) or (isinstance(matchday, str) and matchday.isdigit()) else None,
            round_name=stage_label,
        )

        team_blocks = soup.find_all("table", attrs={"width": "100%", "height": "30%"})
        if len(team_blocks) < 2:
            team_blocks = soup.find_all("table", attrs={"width": "100%", "height": "28%"})
        if len(team_blocks) < 2:
            team_blocks = soup.find_all("table", attrs={"width": "100%", "height": "27%"})
        if len(team_blocks) < 2:
            # fallback: heuristically pair tables around lineup sections
            all_tables = soup.find_all("table")
            reserve_indices = [
                idx for idx, tbl in enumerate(all_tables) if "Reserve" in tbl.get_text(" ", strip=True)
            ]
            if len(reserve_indices) >= 2:
                first_block = all_tables[reserve_indices[0]]
                second_block = all_tables[reserve_indices[1]]
                team_blocks = [first_block, second_block]
            else:
                raise ValueError(f"Unexpected match layout in {detail_path}")

        first_block, second_block = team_blocks[:2]
        lineup_home_block = first_block
        lineup_away_block = second_block

        home_lineups = self.parse_team_block(lineup_home_block)
        away_lineups = self.parse_team_block(lineup_away_block)

        goals = self.parse_goal_table(soup, metadata)

        home_players = home_lineups["players"]
        away_players = away_lineups["players"]

        home_subs, home_sub_cards = self.apply_substitutions(home_lineups["substitutions"], home_players, "home")
        away_subs, away_sub_cards = self.apply_substitutions(away_lineups["substitutions"], away_players, "away")

        cards = []
        cards.extend(self.gather_card_events(home_players, "home"))
        cards.extend(self.gather_card_events(away_players, "away"))
        cards.extend(home_sub_cards)
        cards.extend(away_sub_cards)

        substitutions = home_subs + away_subs

        lineups = {
            "home": home_players,
            "away": away_players,
        }

        return metadata, lineups, substitutions, goals, cards

    def parse_header_score(self, text: str) -> Tuple[str, str, int, int, Optional[int], Optional[int]]:
        score_pattern = r"(.+?)\s-\s(.+?)\s([-\d]+):([-\d]+)(?:\s\(([-\d]+):([-\d]+)\))?"
        match = re.search(score_pattern, text)
        if not match:
            raise ValueError(f"Cannot parse match header: {text}")

        home_team = normalize_whitespace(match.group(1))
        away_team = normalize_whitespace(match.group(2))
        home_score_raw = match.group(3)
        away_score_raw = match.group(4)
        half_home_raw = match.group(5) if match.lastindex and match.lastindex >= 5 else None
        half_away_raw = match.group(6) if match.lastindex and match.lastindex >= 6 else None

        def parse_score(value: Optional[str]) -> Optional[int]:
            if value is None or value == "-":
                return None
            return int(value)

        home_goals = parse_score(home_score_raw)
        away_goals = parse_score(away_score_raw)
        half_home = parse_score(half_home_raw)
        half_away = parse_score(half_away_raw)
        return home_team, away_team, home_goals, away_goals, half_home, half_away

    def extract_match_details(self, soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        info = {
            "date": None,
            "kickoff": None,
            "attendance": None,
            "referee": None,
            "referee_link": None,
            "mainz_coach": None,
            "mainz_coach_link": None,
            "opponent_coach": None,
            "opponent_coach_link": None,
        }

        header_line = soup.find(string=re.compile(r"Zuschauer", re.IGNORECASE))
        if header_line:
            container_text = header_line.parent.get_text(" ", strip=True) if header_line.parent else header_line
            text = normalize_whitespace(container_text)
            parts = [p.strip() for p in text.replace(" Uhr", "").split(",")]
            
            # Parse date (always first part)
            if parts:
                date_parts = parts[0].split()
                if date_parts:
                    date_candidate = date_parts[-1]
                    # Only try to parse if it looks like a date (has digits and dots/dashes)
                    if re.match(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', date_candidate):
                        try:
                            info["date"] = datetime.strptime(date_candidate, "%d.%m.%Y").strftime("%Y-%m-%d")
                        except ValueError:
                            # Invalid date, leave as None
                            pass
            
            # Determine format: old (Datum, Zuschauer) vs new (Datum, Zeit, Zuschauer)
            # Check each part for "Zuschauer" keyword to find attendance
            for i, part in enumerate(parts[1:], 1):
                part_lower = part.lower()
                if "zuschauer" in part_lower or "zuschau" in part_lower:
                    # This part contains attendance
                    attendance_text = part.replace("Zuschauer.", "").replace("Zuschauer", "").strip()
                    # Handle special cases like "keine Zuschauer"
                    if not attendance_text.startswith("keine") and not attendance_text.startswith("no"):
                        attendance_value = parse_int(attendance_text.split()[0] if attendance_text else "")
                        info["attendance"] = attendance_value
                elif i == 1 and not ("zuschauer" in part_lower):
                    # First part after date, doesn't contain "Zuschauer" -> likely kickoff time
                    info["kickoff"] = part

        coach_table = soup.find("b", string=re.compile("Schiedsrichter", re.IGNORECASE))
        if coach_table:
            container = coach_table.find_parent("table")
            if container:
                for cell in container.find_all("td"):
                    text = normalize_whitespace(cell.get_text(" ", strip=True))
                    link = cell.find("a")
                    if "FSV-Trainer" in text:
                        info["mainz_coach"] = text.split(":")[-1].strip()
                        info["mainz_coach_link"] = link["href"] if link else None
                    elif "Trainer" in text:
                        info["opponent_coach"] = text.split(":")[-1].strip()
                        info["opponent_coach_link"] = link["href"] if link else None
                    if "Schiedsrichter" in text:
                        info["referee"] = text.replace("Schiedsrichter:", "").strip()
                        info["referee_link"] = link["href"] if link else None
        return info

    def parse_team_block(self, block: BeautifulSoup) -> Dict[str, Dict]:
        players: Dict[str, PlayerAppearance] = {}
        substitutions: List[Dict[str, Optional[str]]] = []
        for table in block.find_all("table"):
            table_text = normalize_whitespace(table.get_text(" ", strip=True))
            table_is_reserve = table_text.lower().startswith("reserve")
            for cell in table.find_all("td"):
                text = normalize_whitespace(cell.get_text(" ", strip=True))
                if not text or text.lower().startswith("reserve"):
                    continue

                # Filtere Trainer-Namen und Schiedsrichter-Namen aus Team-Block
                text_lower = text.lower()
                if any(pattern in text_lower for pattern in [
                    'trainer:', 'fsv-trainer', 'coach:', '-trainer',
                    'schiedsrichter:', 'schiedsrichterin:', 'referee:'
                ]):
                    continue

                # Filtere Tor-Text (beginnt mit "Tore" oder enthält "Tore" am Anfang)
                if text_lower.startswith('tore ') or re.match(r'^\d+\.\s*\d+:\d+', text):
                    continue

                icons = [img.get("src") for img in cell.find_all("img")]
                if " für " in text:
                    substitution = self.parse_substitution_entry(cell, text, icons)
                    if substitution:
                        substitutions.append(substitution)
                    continue

                number_match = re.match(r"^(\d+)\s+(.*)", text)
                if number_match:
                    shirt_number = int(number_match.group(1))
                    name = number_match.group(2).strip()
                else:
                    shirt_number = None
                    name = text

                # Zusätzliche Validierung: Überspringe ungültige Namen
                if not name or len(name) < 2:
                    continue
                # Bereinige "?" am Anfang
                if name.startswith('?'):
                    name = name[1:].strip()
                # Prüfe ob Name mit Buchstabe beginnt (Unicode-Buchstaben erlaubt)
                if not name or name == "-":
                    continue
                import unicodedata
                if name and not unicodedata.category(name[0]).startswith('L'):
                    continue

                if name not in players:
                    players[name] = PlayerAppearance(
                        name=name,
                        shirt_number=shirt_number,
                        is_starter=not table_is_reserve,
                    )
                else:
                    existing = players[name]
                    if existing.shirt_number is None and shirt_number is not None:
                        existing.shirt_number = shirt_number
                    if table_is_reserve:
                        existing.is_starter = False

                for icon in icons:
                    if icon in CARD_ICON_MAP:
                        players[name].card_events.append((None, None, CARD_ICON_MAP[icon]))

        return {"players": players, "substitutions": substitutions}

    def parse_substitution_entry(self, cell, text: str, icons: List[str]) -> Optional[Dict[str, Optional[str]]]:
        minute, stoppage = parse_minute(text)
        if minute is None:
            return None
        remainder = re.sub(r"^\s*\d+(?:\+\d+)?\.\s*", "", text)
        if " für " not in remainder:
            return None

        incoming_text, outgoing_text = [part.strip() for part in remainder.split(" für ", 1)]
        incoming_number = None
        outgoing_number = None

        # Filtere Fehlertext-Präfixe ("FE,", "ET,", "HE,") - entferne sie aber behalte den Rest
        # z.B. "FE, Lipponer" -> "Lipponer"
        incoming_text = re.sub(r'^(FE|ET|HE),\s*', '', incoming_text, flags=re.IGNORECASE).strip()
        outgoing_text = re.sub(r'^(FE|ET|HE),\s*', '', outgoing_text, flags=re.IGNORECASE).strip()
        
        # Bereinige "wdh." Präfixe
        incoming_text = re.sub(r'^wdh\.\s*', '', incoming_text, flags=re.IGNORECASE).strip()
        outgoing_text = re.sub(r'^wdh\.\s*', '', outgoing_text, flags=re.IGNORECASE).strip()

        number_match = re.match(r"^(\d+)\s+(.*)", incoming_text)
        if number_match:
            incoming_number = int(number_match.group(1))
            incoming_text = number_match.group(2).strip()

        number_match = re.match(r"^(\d+)\s+(.*)", outgoing_text)
        if number_match:
            outgoing_number = int(number_match.group(1))
            outgoing_text = number_match.group(2).strip()

        # Extrahiere Spielernamen aus "an"-Konstruktionen (z.B. "FE, Liebers an Klopp" -> "Klopp")
        if ' an ' in incoming_text.lower():
            parts = re.split(r'\s+an\s+', incoming_text, flags=re.IGNORECASE)
            if len(parts) > 1:
                incoming_text = parts[-1].strip()
        if ' an ' in outgoing_text.lower():
            parts = re.split(r'\s+an\s+', outgoing_text, flags=re.IGNORECASE)
            if len(parts) > 1:
                outgoing_text = parts[-1].strip()

        card_type = next((CARD_ICON_MAP[icon] for icon in icons if icon in CARD_ICON_MAP), None)
        anchors = cell.find_all("a")
        player_on_link = None
        player_off_link = None
        for anchor in anchors:
            href = anchor.get("href")
            if not href:
                continue
            anchor_text = normalize_whitespace(anchor.get_text(" ", strip=True))
            if anchor_text and anchor_text in incoming_text and player_on_link is None:
                player_on_link = href
                continue
            if anchor_text and anchor_text in outgoing_text and player_off_link is None:
                player_off_link = href
                continue
            if player_on_link is None:
                player_on_link = href
            elif player_off_link is None:
                player_off_link = href

        return {
            "minute": minute,
            "stoppage": stoppage,
            "player_on": incoming_text,
            "player_on_number": incoming_number,
            "player_on_link": player_on_link,
            "player_off": outgoing_text,
            "player_off_number": outgoing_number,
            "player_off_link": player_off_link,
            "card_type": card_type,
            "team_role": None,
        }

    def parse_goal_table(self, soup: BeautifulSoup, metadata: MatchMetadata) -> List[GoalEvent]:
        goal_header = soup.find("b", string=re.compile("Tore", re.IGNORECASE))
        if not goal_header:
            return []
        goal_table = goal_header.find_parent("table").find_next("table")
        if not goal_table:
            return []

        goals: List[GoalEvent] = []
        for cell in goal_table.find_all("td"):
            text = normalize_whitespace(cell.get_text(" ", strip=True))
            if not text:
                continue
            
            # Überspringe Zellen die nur "Tore" enthalten oder mit "Tore" beginnen
            if text.lower().startswith('tore ') and not re.search(r'\d+\.', text):
                continue
            
            minute, stoppage = parse_minute(text)
            if minute is None:
                continue
            remainder = re.sub(r"^\s*\d+(?:\+\d+)?\.\s*", "", text)
            score_match = re.match(r"(\d+):(\d+)\s+(.*)", remainder)
            if not score_match:
                continue
            score_home = int(score_match.group(1))
            score_away = int(score_match.group(2))
            scorer_info = score_match.group(3)
            
            # Filtere Fehlertext-Präfixe - entferne sie aber behalte den Rest
            scorer_info = re.sub(r'^(FE|ET|HE),\s*', '', scorer_info, flags=re.IGNORECASE).strip()
            
            # Bereinige "wdh." Präfixe
            scorer_info = re.sub(r'^wdh\.\s*', '', scorer_info, flags=re.IGNORECASE).strip()
            
            assist = None
            if "(" in scorer_info and ")" in scorer_info:
                scorer_name, assist_part = scorer_info.split("(", 1)
                assist = assist_part.strip(" )")
                # Filtere auch aus Assist - entferne Präfixe aber behalte den Rest
                assist = re.sub(r'^(FE|ET|HE),\s*', '', assist, flags=re.IGNORECASE).strip()
                # Bereinige "wdh." Präfixe
                assist = re.sub(r'^wdh\.\s*', '', assist, flags=re.IGNORECASE).strip()
                
                # WICHTIG: Extrahiere Spielernamen aus "an"-Konstruktionen
                # z.B. "FE an Becker" -> "Becker", "Liebers an Klopp" -> "Klopp"
                if ' an ' in assist.lower():
                    parts = re.split(r'\s+an\s+', assist, flags=re.IGNORECASE)
                    if len(parts) > 1:
                        assist = parts[-1].strip()  # Nimm den Teil NACH "an"
                
                # Filtere "-" als Platzhalter
                if assist == "-" or not assist:
                    assist = None
            else:
                scorer_name = scorer_info
            
            scorer_name = scorer_name.strip()
            
            # Extrahiere nur Spielernamen, nicht vollständigen Tor-Text
            # Wenn mehrere Namen durch Leerzeichen getrennt sind, nimm den letzten (oft der Torschütze)
            if ' ' in scorer_name and not re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', scorer_name):
                # Versuche Link zu finden für korrekten Namen
                scorer_link = cell.find("a", href=re.compile(r"../spieler/"))
                if scorer_link:
                    scorer_name = normalize_whitespace(scorer_link.get_text(" ", strip=True))
                else:
                    # Fallback: Nimm letzten Teil wenn mehrere Wörter
                    parts = scorer_name.split()
                    if len(parts) > 2:
                        scorer_name = parts[-1]  # Oft der Nachname
            
            # Validierung: Überspringe wenn Name zu kurz oder ungültig
            if len(scorer_name) < 2:
                continue
            # Prüfe ob Name mit Buchstabe beginnt (Unicode-Buchstaben erlaubt)
            import unicodedata
            if scorer_name and not unicodedata.category(scorer_name[0]).startswith('L'):
                continue

            home_scored = score_home > (goals[-1].score_home if goals else 0)
            team_role = "home" if home_scored else "away"

            goals.append(
                GoalEvent(
                    minute=minute,
                    stoppage=stoppage,
                    score_home=score_home,
                    score_away=score_away,
                    scorer=scorer_name,
                    assist=assist,
                    team_role=team_role,
                )
            )
        return goals

    def apply_substitutions(
        self,
        substitutions: List[Dict[str, Optional[str]]],
        players: Dict[str, PlayerAppearance],
        team_role: str,
    ) -> Tuple[List[Dict[str, Optional[str]]], List[Dict[str, Optional[str]]]]:
        resolved_subs: List[Dict[str, Optional[str]]] = []
        cards: List[Dict[str, Optional[str]]] = []

        for sub in substitutions:
            sub["team_role"] = team_role
            player_on_name = sub["player_on"]
            player_off_name = sub["player_off"]

            player_on = players.get(player_on_name)
            if not player_on:
                player_on = PlayerAppearance(
                    name=player_on_name,
                    shirt_number=sub.get("player_on_number"),
                    is_starter=False,
                )
                players[player_on_name] = player_on
            else:
                if player_on.shirt_number is None and sub.get("player_on_number") is not None:
                    player_on.shirt_number = sub["player_on_number"]
                player_on.is_starter = False
            player_on.minute_on = sub["minute"]
            player_on.stoppage_on = sub["stoppage"]

            player_off = players.get(player_off_name)
            if not player_off:
                player_off = PlayerAppearance(
                    name=player_off_name,
                    shirt_number=sub.get("player_off_number"),
                    is_starter=True,
                )
                players[player_off_name] = player_off
            else:
                if player_off.shirt_number is None and sub.get("player_off_number") is not None:
                    player_off.shirt_number = sub["player_off_number"]
            player_off.minute_off = sub["minute"]
            player_off.stoppage_off = sub["stoppage"]

            if sub.get("card_type"):
                cards.append(
                    {
                        "team_role": team_role,
                        "player": player_on_name,
                        "minute": sub["minute"],
                        "stoppage": sub["stoppage"],
                        "card_type": sub["card_type"],
                    }
                )
            resolved_subs.append(sub)

        return resolved_subs, cards

    def gather_card_events(self, players: Dict[str, PlayerAppearance], team_role: str) -> List[Dict[str, Optional[str]]]:
        events: List[Dict[str, Optional[str]]] = []
        for appearance in players.values():
            for minute, stoppage, card_type in appearance.card_events:
                events.append(
                    {
                        "team_role": team_role,
                        "player": appearance.name,
                        "minute": minute,
                        "stoppage": stoppage,
                        "card_type": card_type,
                    }
                )
        return events

    # ---------------------------------------------------------------- player profiles
    def parse_player_profile(self, player_name: str, season_path: Path) -> None:
        normalized = normalize_name(player_name)
        player_file = self.player_file_index.get(normalized)

        if player_file is None:
            for path in season_path.glob("spieler/*.html"):
                if normalize_name(path.stem) == normalized:
                    player_file = path
                    self.player_file_index[normalized] = player_file
                    break

        if player_file is None or not player_file.exists():
            return

        soup = read_html(player_file)
        if soup is None:
            return

        header = soup.find("b")
        name = normalize_whitespace(header.get_text(" ", strip=True)) if header else player_name
        
        # Bereinige "?" am Anfang (wenn aus HTML extrahiert)
        if name.startswith('?'):
            name = name[1:].strip()
        
        # Bereinige "wdh." Präfixe
        name = re.sub(r'^wdh\.\s*', '', name, flags=re.IGNORECASE).strip()
        
        information = soup.get_text("\n", strip=True)

        # Parse birth date and place - use DOTALL flag to match across newlines
        birth_match = re.search(r"\*.*?(\d{2}\.\d{2}\.\d{4}).*?in\s+([^,\n]+)", information, re.DOTALL)
        birth_date = None
        birth_place = None
        if birth_match:
            try:
                birth_date = datetime.strptime(birth_match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
            except ValueError:
                birth_date = birth_match.group(1)
            birth_place = birth_match.group(2).strip()

        # Parse height (2-3 digits)
        height_match = re.search(r"(\d{2,3})\s*cm", information)
        height_cm = int(height_match.group(1)) if height_match else None
        
        # Parse weight (2-3 digits)
        weight_match = re.search(r"(\d{2,3})\s*kg", information)
        weight_kg = int(weight_match.group(1)) if weight_match else None

        # Parse position
        primary_position = None
        position_header = soup.find("b", string=re.compile("Position", re.IGNORECASE))
        if position_header:
            # Get the parent element and extract all text after the header
            parent = position_header.find_parent()
            if parent:
                # Get all strings after the position header
                found_header = False
                for string in parent.stripped_strings:
                    if found_header and string and not string.endswith(":"):
                        primary_position = normalize_whitespace(string)
                        break
                    if "position" in string.lower():
                        found_header = True
        
        # Parse nationality
        nationality = None
        nationality_header = soup.find("b", string=re.compile(r"Nationalit[aä]t", re.IGNORECASE))
        if nationality_header:
            # Get the parent element and extract text after the header
            parent = nationality_header.find_parent()
            if parent:
                # Get all strings after the nationality header
                found_header = False
                for string in parent.stripped_strings:
                    if found_header and string and not string.endswith(":"):
                        nationality = normalize_whitespace(string)
                        break
                    if "nationalit" in string.lower():
                        found_header = True

        image = soup.find("img")
        image_url = image["src"] if image else None

        try:
            player_id = self.db.get_or_create_player(name, str(player_file.relative_to(self.base_path)))
        except ValueError as e:
            self.logger.warning("Skipping invalid player profile: %s (%s)", name, e)
            return
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            UPDATE players
            SET name = ?, birth_date = ?, birth_place = ?, height_cm = ?, weight_kg = ?, primary_position = ?, nationality = ?, image_url = ?
            WHERE player_id = ?
            """,
            (name, birth_date, birth_place, height_cm, weight_kg, primary_position, nationality, image_url, player_id),
        )
        self.db.conn.commit()

        career_header = soup.find("b", string=re.compile("Laufbahn", re.IGNORECASE))
        if career_header:
            career_table = career_header.find_next("table")
            if career_table:
                cursor.execute("DELETE FROM player_careers WHERE player_id = ?", (player_id,))
                for row in career_table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) < 2:
                        continue
                    years_text = normalize_whitespace(cells[0].get_text(" ", strip=True))
                    team_text = normalize_whitespace(cells[1].get_text(" ", strip=True))
                    years_match = re.match(r"(\d{4})(?:-(\d{4}))?", years_text)
                    start_year = int(years_match.group(1)) if years_match else None
                    end_year = int(years_match.group(2)) if years_match and years_match.group(2) else None
                    cursor.execute(
                        """
                        INSERT INTO player_careers (player_id, team_name, start_year, end_year)
                        VALUES (?, ?, ?, ?)
                        """,
                        (player_id, team_text, start_year, end_year),
                    )
        self.db.conn.commit()

    # ---------------------------------------------------------------- season squad
    def parse_season_squad(self, season_competition_id: int, season_path: Path) -> None:
        squad_path = season_path / "profikader.html"
        soup = read_html(squad_path)
        if soup is None:
            return

        cursor = self.db.conn.cursor()

        parent_table = soup.find("table", width="90%")
        if not parent_table:
            parent_table = soup.find("table")

        position_group = None
        for cell in parent_table.find_all("td"):
            for raw_entry in cell.stripped_strings:
                entry = normalize_whitespace(raw_entry)
                if not entry:
                    continue
                upper_entry = entry.upper()
                if "WEITERE EINGESETZTE SPIELER" in upper_entry or "TRAINER" in upper_entry:
                    return
                if upper_entry in {"TOR", "ABWEHR", "MITTELFELD", "ANGRIFF"}:
                    position_group = upper_entry
                    continue
                if entry.endswith(":") or position_group is None:
                    continue
                cleaned_entry = re.sub(r"\(.*?\)", "", entry).strip()
                if not cleaned_entry:
                    continue
                number_match = re.match(r"^(\d+)\s+(.*)", cleaned_entry)
                shirt_number = int(number_match.group(1)) if number_match else None
                name = number_match.group(2).strip() if number_match else cleaned_entry
                if not name:
                    continue
                try:
                    player_id = self.db.get_or_create_player(name, None)
                except ValueError as e:
                    self.logger.warning("Skipping invalid squad player: %s (%s)", name, e)
                    continue
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO season_squads
                    (season_competition_id, player_id, position_group, shirt_number, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (season_competition_id, player_id, position_group, shirt_number, "primary"),
                )
        self.db.conn.commit()

    # ---------------------------------------------------------------- standings
    def parse_season_table(self, season_competition_id: int, season_path: Path, overview_filename: str) -> None:
        if "liga" not in overview_filename:
            return
        frameset = season_path / "profitab.html"
        if not frameset.exists():
            return

        for matchday in range(1, 35):
            tab_file = season_path / "tab" / f"profitab{matchday:02}.html"
            if not tab_file.exists():
                continue
            soup = read_html(tab_file)
            if soup is None:
                continue

            matchday_date = None
            header_text = soup.get_text("\n", strip=True)
            date_match = re.search(rf"{matchday}\.\s*Spieltag,\s*(\d{{2}}\.\d{{2}}\.\d{{4}})", header_text)
            if date_match:
                try:
                    matchday_date = datetime.strptime(date_match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
                except ValueError:
                    matchday_date = date_match.group(1)

            position = None
            points = None
            goals_for = None
            goals_against = None

            for row in soup.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue
                team_text = normalize_whitespace(cells[1].get_text(" ", strip=True))
                if "Mainz" not in team_text:
                    continue
                position = parse_int(cells[0].get_text(" ", strip=True))
                stats_text = cells[2].get_text(" ", strip=True)
                score_match = re.search(r"(\d+)\s*-\s*(\d+)", stats_text)
                if score_match:
                    goals_for = int(score_match.group(1))
                    goals_against = int(score_match.group(2))
                points_match = re.search(r"(\d+)\s*$", stats_text)
                if points_match:
                    points = int(points_match.group(1))
                break

            if position is not None:
                self.db.add_matchday_entry(
                    season_competition_id,
                    matchday,
                    matchday_date,
                    position,
                    points,
                    goals_for,
                    goals_against,
                )

    # ---------------------------------------------------------------- runner
    def run(self) -> None:
        self.logger.info("Starting archive parse from %s → %s", self.base_path, self.db.db_path)
        for season in self.iter_seasons():
            self.parse_season(season)
        
        # Parse all player profiles to enrich player data
        self.logger.info("Enriching player profiles from spieler/ directory...")
        self.enrich_all_player_profiles()
        
        # Parse all coach profiles to enrich coach data
        self.logger.info("Enriching coach profiles from trainer/ directory...")
        self.enrich_all_coach_profiles()
        
        self.logger.info("All seasons processed. Closing database connection.")
        self.print_statistics()
        self.db.close()
    
    def print_statistics(self) -> None:
        """Print parsing statistics and error summary."""
        self.logger.info("=" * 80)
        self.logger.info("PARSING STATISTICS")
        self.logger.info("=" * 80)
        self.logger.info(f"Matches processed: {self.stats['matches_processed']}")
        self.logger.info(f"Matches successful: {self.stats['matches_successful']}")
        self.logger.info(f"Matches failed: {self.stats['matches_failed']}")
        
        if self.stats['duplicates_skipped']:
            total_dups = sum(self.stats['duplicates_skipped'].values())
            if total_dups > 0:
                self.logger.info(f"\nDuplicates skipped: {total_dups:,}")
                for entity_type, count in self.stats['duplicates_skipped'].items():
                    if count > 0:
                        self.logger.info(f"  {entity_type}: {count:,}")
        
        if self.stats['errors']:
            self.logger.warning(f"\nErrors encountered: {len(self.stats['errors'])}")
            # Show first 10 errors
            for error in self.stats['errors'][:10]:
                self.logger.warning(f"  - {error}")
            if len(self.stats['errors']) > 10:
                self.logger.warning(f"  ... and {len(self.stats['errors']) - 10} more errors")
        
        if self.stats['warnings']:
            self.logger.warning(f"\nWarnings: {len(self.stats['warnings'])}")
        
        self.logger.info("=" * 80)
    
    def enrich_all_player_profiles(self) -> None:
        """Parse all player profile HTML files to enrich player data."""
        spieler_dir = self.base_path / "spieler"
        if not spieler_dir.exists():
            self.logger.warning("spieler/ directory not found")
            return
        
        player_files = list(spieler_dir.glob("*.html"))
        self.logger.info("Found %d player profile files", len(player_files))
        
        enriched = 0
        for i, player_file in enumerate(player_files, 1):
            if i % 500 == 0:
                self.logger.info("  Enriched %d/%d player profiles", i, len(player_files))
            
            soup = read_html(player_file)
            if soup is None:
                continue
            
            # Get player name from profile
            header = soup.find("b")
            if not header:
                continue
            
            profile_name = normalize_whitespace(header.get_text(" ", strip=True))
            normalized = normalize_name(profile_name)
            
            # Find matching player(s) in database by normalized name
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT player_id, name FROM players WHERE normalized_name = ?",
                (normalized,)
            )
            matches = cursor.fetchall()
            
            if not matches:
                # Try partial match (e.g., "Brosinski" for "DANIEL BROSINSKI")
                cursor.execute(
                    "SELECT player_id, name FROM players WHERE normalized_name LIKE ?",
                    (f"%{normalized}%",)
                )
                matches = cursor.fetchall()
            
            if matches:
                # Enrich all matching players with profile data
                for player_id, existing_name in matches:
                    self._enrich_player_from_profile(player_id, profile_name, player_file, soup)
                    enriched += 1
        
        self.logger.info("Enriched %d player records from %d profile files", enriched, len(player_files))
    
    def _enrich_player_from_profile(self, player_id: int, profile_name: str, player_file: Path, soup: BeautifulSoup) -> None:
        """Enrich a single player record with profile data."""
        information = soup.get_text("\n", strip=True)
        
        # Parse birth date and place
        birth_match = re.search(r"\*.*?(\d{2}\.\d{2}\.\d{4}).*?in\s+([^,\n]+)", information, re.DOTALL)
        birth_date = None
        birth_place = None
        if birth_match:
            try:
                birth_date = datetime.strptime(birth_match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
            except ValueError:
                birth_date = birth_match.group(1)
            birth_place = birth_match.group(2).strip()
        
        # Parse height and weight
        height_match = re.search(r"(\d{2,3})\s*cm", information)
        height_cm = int(height_match.group(1)) if height_match else None
        
        weight_match = re.search(r"(\d{2,3})\s*kg", information)
        weight_kg = int(weight_match.group(1)) if weight_match else None
        
        # Parse position
        primary_position = None
        position_header = soup.find("b", string=re.compile("Position", re.IGNORECASE))
        if position_header:
            parent = position_header.find_parent()
            if parent:
                found_header = False
                for string in parent.stripped_strings:
                    if found_header and string and not string.endswith(":"):
                        primary_position = normalize_whitespace(string)
                        break
                    if "position" in string.lower():
                        found_header = True
        
        # Parse nationality
        nationality = None
        nationality_header = soup.find("b", string=re.compile(r"Nationalit[aä]t", re.IGNORECASE))
        if nationality_header:
            parent = nationality_header.find_parent()
            if parent:
                found_header = False
                for string in parent.stripped_strings:
                    if found_header and string and not string.endswith(":"):
                        nationality = normalize_whitespace(string)
                        break
                    if "nationalit" in string.lower():
                        found_header = True
        
        image = soup.find("img")
        image_url = image["src"] if image else None
        
        # Update player record (don't update name to avoid UNIQUE conflicts)
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            UPDATE players
            SET birth_date = COALESCE(?, birth_date),
                birth_place = COALESCE(?, birth_place),
                height_cm = COALESCE(?, height_cm),
                weight_kg = COALESCE(?, weight_kg),
                primary_position = COALESCE(?, primary_position),
                nationality = COALESCE(?, nationality),
                image_url = COALESCE(?, image_url),
                profile_url = COALESCE(?, profile_url)
            WHERE player_id = ?
            """,
            (birth_date, birth_place, height_cm, weight_kg, 
             primary_position, nationality, image_url, str(player_file.relative_to(self.base_path)), player_id),
        )
        self.db.conn.commit()
    
    def enrich_all_coach_profiles(self) -> None:
        """Parse all coach profile HTML files to enrich coach data."""
        trainer_dir = self.base_path / "trainer"
        if not trainer_dir.exists():
            self.logger.warning("trainer/ directory not found")
            return
        
        coach_files = list(trainer_dir.glob("*.html"))
        self.logger.info("Found %d coach profile files", len(coach_files))
        
        enriched = 0
        for i, coach_file in enumerate(coach_files, 1):
            if i % 50 == 0:
                self.logger.info("  Enriched %d/%d coach profiles", i, len(coach_files))
            
            soup = read_html(coach_file)
            if soup is None:
                continue
            
            # Get coach name from profile
            header = soup.find("b")
            if not header:
                continue
            
            profile_name = normalize_whitespace(header.get_text(" ", strip=True))
            normalized = normalize_name(profile_name)
            
            # Find matching coach(es) in database
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT coach_id, name FROM coaches WHERE normalized_name LIKE ?",
                (f"%{normalized.split()[-1] if normalized else ''}%",)  # Match by last name
            )
            matches = cursor.fetchall()
            
            if matches:
                # Enrich all matching coaches
                for coach_id, existing_name in matches:
                    self._enrich_coach_from_profile(coach_id, profile_name, coach_file, soup)
                    enriched += 1
        
        self.logger.info("Enriched %d coach records from %d profile files", enriched, len(coach_files))
    
    def _enrich_coach_from_profile(self, coach_id: int, profile_name: str, coach_file: Path, soup: BeautifulSoup) -> None:
        """Enrich a single coach record with profile data."""
        information = soup.get_text("\n", strip=True)
        
        # Parse birth date and place
        birth_match = re.search(r"\*.*?(\d{2}\.\d{2}\.\d{4}).*?in\s+([^,\n.]+)", information, re.DOTALL)
        birth_date = None
        birth_place = None
        if birth_match:
            try:
                birth_date = datetime.strptime(birth_match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
            except ValueError:
                birth_date = birth_match.group(1)
            birth_place = birth_match.group(2).strip()
        
        # Parse nationality (coaches may have this field)
        nationality = None
        nationality_header = soup.find("b", string=re.compile(r"Nationalit[aä]t", re.IGNORECASE))
        if nationality_header:
            parent = nationality_header.find_parent()
            if parent:
                found_header = False
                for string in parent.stripped_strings:
                    if found_header and string and not string.endswith(":"):
                        nationality = normalize_whitespace(string)
                        break
                    if "nationalit" in string.lower():
                        found_header = True
        
        # Update coach record
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            UPDATE coaches
            SET birth_date = COALESCE(?, birth_date),
                birth_place = COALESCE(?, birth_place),
                nationality = COALESCE(?, nationality),
                profile_url = COALESCE(?, profile_url)
            WHERE coach_id = ?
            """,
            (birth_date, birth_place, nationality, str(coach_file.relative_to(self.base_path)), coach_id),
        )
        
        # Parse career table
        career_header = soup.find("b", string=re.compile("Laufbahn", re.IGNORECASE))
        if career_header:
            career_table = career_header.find_next("table")
            if career_table:
                cursor.execute("DELETE FROM coach_careers WHERE coach_id = ?", (coach_id,))
                for row in career_table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) < 5:
                        continue
                    
                    # Parse dates (columns 0-2: start, -, end)
                    start_date = normalize_whitespace(cells[0].get_text(" ", strip=True))
                    end_date = normalize_whitespace(cells[2].get_text(" ", strip=True))
                    
                    # Team (column 4)
                    team_text = normalize_whitespace(cells[4].get_text(" ", strip=True)) if len(cells) > 4 else None
                    
                    # Role (column 6 or last)
                    role_text = normalize_whitespace(cells[6].get_text(" ", strip=True)) if len(cells) > 6 else None
                    
                    if team_text:
                        cursor.execute(
                            """
                            INSERT INTO coach_careers (coach_id, team_name, start_date, end_date, role)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (coach_id, team_text, start_date, end_date, role_text),
                        )
        
        self.db.conn.commit()

    # ---------------------------------------------------------------- indexing
    def build_player_index(self) -> Dict[str, Path]:
        index: Dict[str, Path] = {}
        player_dir = self.base_path / "spieler"
        if player_dir.exists():
            for path in player_dir.glob("*.html"):
                index[normalize_name(path.stem)] = path
        return index


def main():
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
    parser = ComprehensiveFSVParser()
    parser.run()


if __name__ == "__main__":
    main()
