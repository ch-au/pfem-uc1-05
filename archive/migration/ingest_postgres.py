#!/usr/bin/env python3
"""
Reparse the FSV Mainz 05 HTML archive and ingest directly into Postgres with cleaned entities.

Optionally mirror the cleaned dataset into a fresh SQLite file for the existing app to use.
"""

import argparse
import logging
import os
import re
import unicodedata
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

import psycopg2
from bs4 import BeautifulSoup

from config import Config
from precompute_embeddings import ensure_vector_extension, upsert_embeddings
from langchain_openai import OpenAIEmbeddings


def normalize_text(value: str) -> str:
    if not value:
        return ""
    txt = value.strip()
    txt = unicodedata.normalize('NFKD', txt)
    txt = ''.join(ch for ch in txt if not unicodedata.combining(ch))
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def normalize_player_name(raw: str) -> str:
    if not raw:
        return ""
    text = raw.strip()
    text = re.sub(r"^\s*\d+[\)\.]?\s+", "", text)  # leading jersey number
    text = re.sub(r"\s+\d+$", "", text)               # trailing number
    text = re.sub(r"[,;]+", " ", text)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z\-\'\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class PGIngestor:
    def __init__(self, base_path: Path, reset: bool = False, mirror_sqlite: Optional[Path] = None):
        self.base_path = Path(base_path)
        self.config = Config()
        # Use Config helper for connection
        self.conn = psycopg2.connect(self.config.build_psycopg2_dsn())
        self.reset = reset
        self.mirror_sqlite = Path(mirror_sqlite) if mirror_sqlite else None
        self.logger = logging.getLogger("ingest")

    # ---------------- Schema ----------------
    def setup_schema(self) -> None:
        with self.conn, self.conn.cursor() as cur:
            if self.reset:
                cur.execute("""
                    DROP TABLE IF EXISTS public.Player_Season_Stats CASCADE;
                    DROP TABLE IF EXISTS public.Player_Careers CASCADE;
                    DROP TABLE IF EXISTS public.Substitutions CASCADE;
                    DROP TABLE IF EXISTS public.Goals CASCADE;
                    DROP TABLE IF EXISTS public.Match_Lineups CASCADE;
                    DROP TABLE IF EXISTS public.Matches CASCADE;
                    DROP TABLE IF EXISTS public.Coaches CASCADE;
                    DROP TABLE IF EXISTS public.Referees CASCADE;
                    DROP TABLE IF EXISTS public.Players CASCADE;
                    DROP TABLE IF EXISTS public.Opponents CASCADE;
                    DROP TABLE IF EXISTS public.Seasons CASCADE;
                """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.Seasons (
                    season_id SERIAL PRIMARY KEY,
                    season_name TEXT UNIQUE,
                    league_name TEXT,
                    total_matches INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.Opponents (
                    opponent_id SERIAL PRIMARY KEY,
                    opponent_name TEXT UNIQUE,
                    opponent_link TEXT,
                    country TEXT,
                    city TEXT,
                    founded_year INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.Players (
                    player_id SERIAL PRIMARY KEY,
                    player_name TEXT UNIQUE,
                    player_link TEXT,
                    full_name TEXT,
                    date_of_birth DATE,
                    birthplace TEXT,
                    nationality TEXT,
                    height_cm INTEGER,
                    weight_kg INTEGER,
                    primary_position TEXT,
                    foot TEXT
                );
                CREATE TABLE IF NOT EXISTS public.Player_Careers (
                    career_id SERIAL PRIMARY KEY,
                    player_id INTEGER REFERENCES public.Players(player_id) ON DELETE CASCADE,
                    club_name TEXT NOT NULL,
                    opponent_id INTEGER REFERENCES public.Opponents(opponent_id) ON DELETE SET NULL,
                    start_year INTEGER,
                    end_year INTEGER,
                    appearances INTEGER,
                    goals INTEGER,
                    is_youth BOOLEAN DEFAULT FALSE,
                    UNIQUE(player_id, club_name, start_year, end_year)
                );
                CREATE TABLE IF NOT EXISTS public.Player_Season_Stats (
                    stat_id SERIAL PRIMARY KEY,
                    player_id INTEGER REFERENCES public.Players(player_id) ON DELETE CASCADE,
                    season_label TEXT,
                    competition TEXT,
                    appearances INTEGER,
                    subs_on INTEGER,
                    subs_off INTEGER,
                    goals INTEGER,
                    assists INTEGER,
                    yellow_cards INTEGER,
                    second_yellow_cards INTEGER,
                    red_cards INTEGER,
                    UNIQUE(player_id, season_label, competition)
                );
                CREATE TABLE IF NOT EXISTS public.Coaches (
                    coach_id SERIAL PRIMARY KEY,
                    coach_name TEXT UNIQUE,
                    coach_link TEXT,
                    date_of_birth DATE,
                    nationality TEXT
                );
                CREATE TABLE IF NOT EXISTS public.Referees (
                    referee_id SERIAL PRIMARY KEY,
                    ref_name TEXT UNIQUE,
                    ref_link TEXT,
                    date_of_birth DATE,
                    association TEXT,
                    country TEXT
                );
                CREATE TABLE IF NOT EXISTS public.Matches (
                    match_id SERIAL PRIMARY KEY,
                    season_id INTEGER REFERENCES public.Seasons(season_id) ON DELETE CASCADE,
                    gameday INTEGER,
                    is_home_game BOOLEAN,
                    opponent_id INTEGER REFERENCES public.Opponents(opponent_id) ON DELETE RESTRICT,
                    mainz_goals INTEGER,
                    opponent_goals INTEGER,
                    match_details_url TEXT,
                    result_string TEXT,
                    attendance INTEGER,
                    referee TEXT,
                    referee_id INTEGER REFERENCES public.Referees(referee_id),
                    UNIQUE(season_id, gameday, opponent_id)
                );
                CREATE TABLE IF NOT EXISTS public.Match_Lineups (
                    lineup_id SERIAL PRIMARY KEY,
                    match_id INTEGER REFERENCES public.Matches(match_id) ON DELETE CASCADE,
                    player_id INTEGER REFERENCES public.Players(player_id) ON DELETE RESTRICT,
                    is_starter BOOLEAN,
                    is_captain BOOLEAN,
                    jersey_number INTEGER,
                    substituted_minute INTEGER,
                    yellow_card BOOLEAN,
                    red_card BOOLEAN,
                    yellow_card_count INTEGER,
                    second_yellow BOOLEAN,
                    position_row INTEGER,
                    position_col INTEGER,
                    UNIQUE(match_id, player_id)
                );
                CREATE TABLE IF NOT EXISTS public.Goals (
                    goal_id SERIAL PRIMARY KEY,
                    match_id INTEGER REFERENCES public.Matches(match_id) ON DELETE CASCADE,
                    player_id INTEGER REFERENCES public.Players(player_id) ON DELETE RESTRICT,
                    goal_minute INTEGER,
                    is_penalty BOOLEAN,
                    is_own_goal BOOLEAN,
                    assisted_by_player_id INTEGER REFERENCES public.Players(player_id) ON DELETE SET NULL,
                    score_at_time TEXT,
                    UNIQUE(match_id, player_id, goal_minute, score_at_time)
                );
                CREATE TABLE IF NOT EXISTS public.Substitutions (
                    substitution_id SERIAL PRIMARY KEY,
                    match_id INTEGER REFERENCES public.Matches(match_id) ON DELETE CASCADE,
                    minute INTEGER,
                    player_in_id INTEGER REFERENCES public.Players(player_id) ON DELETE RESTRICT,
                    player_out_id INTEGER REFERENCES public.Players(player_id) ON DELETE RESTRICT,
                    UNIQUE(match_id, minute, player_in_id, player_out_id)
                );
            """)

    # ---------------- Helpers ----------------
    def get_or_create_season(self, season_name: str, league_name: str) -> int:
        with self.conn, self.conn.cursor() as cur:
            cur.execute("SELECT season_id FROM public.Seasons WHERE season_name = %s", (season_name,))
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute(
                "INSERT INTO public.Seasons (season_name, league_name, total_matches) VALUES (%s, %s, %s) RETURNING season_id",
                (season_name, league_name, None),
            )
            return cur.fetchone()[0]

    def get_or_create_opponent(self, name: str, link: Optional[str]) -> int:
        name = normalize_text(name)
        with self.conn, self.conn.cursor() as cur:
            cur.execute("SELECT opponent_id FROM public.Opponents WHERE opponent_name = %s", (name,))
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute(
                "INSERT INTO public.Opponents (opponent_name, opponent_link) VALUES (%s, %s) RETURNING opponent_id",
                (name, link),
            )
            return cur.fetchone()[0]

    def get_or_create_player(self, name: str, link: Optional[str]) -> Optional[int]:
        name = normalize_player_name(name)
        if not name:
            return None
        with self.conn, self.conn.cursor() as cur:
            cur.execute("SELECT player_id FROM public.Players WHERE player_name = %s", (name,))
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute(
                "INSERT INTO public.Players (player_name, player_link) VALUES (%s, %s) RETURNING player_id",
                (name, link),
            )
            return cur.fetchone()[0]

    def get_or_create_coach(self, name: str, link: Optional[str]) -> Optional[int]:
        name = normalize_text(name)
        if not name:
            return None
        with self.conn, self.conn.cursor() as cur:
            cur.execute("SELECT coach_id FROM public.Coaches WHERE coach_name = %s", (name,))
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute(
                "INSERT INTO public.Coaches (coach_name, coach_link) VALUES (%s, %s) RETURNING coach_id",
                (name, link),
            )
            return cur.fetchone()[0]

    def get_or_create_referee(self, name: str, link: Optional[str]) -> Optional[int]:
        name = normalize_text(name)
        if not name:
            return None
        with self.conn, self.conn.cursor() as cur:
            cur.execute("SELECT referee_id FROM public.Referees WHERE ref_name = %s", (name,))
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute(
                "INSERT INTO public.Referees (ref_name, ref_link) VALUES (%s, %s) RETURNING referee_id",
                (name, link),
            )
            return cur.fetchone()[0]

    # ---------------- Parsing ----------------
    def parse_score(self, score_text: str) -> Tuple[Optional[int], Optional[int]]:
        m = re.search(r"(\d+):(\d+)", score_text or "")
        if not m:
            return None, None
        return int(m.group(1)), int(m.group(2))

    def parse_season_overview(self, season_dir: Path, season_name: str) -> int:
        """Parse season overview file (profiliga.html or profitab.html) and insert matches."""
        # Try different season overview files
        candidate_files = ['profiliga.html', 'profitab.html', 'profitabb.html']
        fp = None
        for filename in candidate_files:
            candidate = season_dir / filename
            if candidate.exists():
                fp = candidate
                break
        
        if not fp:
            self.logger.warning("No season overview file found for %s (tried: %s)", season_name, ", ".join(candidate_files))
            return 0
        with fp.open('r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f, 'lxml')

        league_name = "Unknown"
        title = soup.find('b')
        if title:
            t = title.get_text(strip=True)
            if ':' in t:
                league_name = t.split(':')[1].strip()
            elif 'Bundesliga' in t:
                league_name = 'Bundesliga'
            elif '2. Liga' in t or 'Zweite' in t:
                league_name = '2. Bundesliga'

        season_id = self.get_or_create_season(season_name, league_name)

        matches_found = 0
        gameday = 0
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                row_text = row.get_text()
                if 'FSV' not in row_text:
                    continue
                gameday += 1
                score_a = row.find('a', href=re.compile(r'profiliga\d+\.html'))
                if not score_a:
                    continue
                score_link = score_a.get('href')
                score_text = score_a.get_text(strip=True)
                home_goals, away_goals = self.parse_score(score_text)
                opponent_a = row.find('a', href=re.compile(r'../gegner/'))
                opponent_name = opponent_a.get_text(strip=True) if opponent_a else None
                opponent_link = opponent_a.get('href') if opponent_a else None
                is_home = None
                attendance = None
                referee = None
                fsv_cells = [c for c in cells if 'FSV' in c.get_text()]
                if fsv_cells:
                    fsv_cell = fsv_cells[0]
                    fsv_index = cells.index(fsv_cell)
                    dash_cells = [c for c in cells if '-' in c.get_text()]
                    if dash_cells:
                        dash_index = cells.index(dash_cells[0])
                        is_home = fsv_index < dash_index
                # Try to extract attendance and referee from page header once
                if attendance is None:
                    # Look for a pattern like "Zuschauer" or a number with dots
                    header_text = soup.get_text(" ")
                    m_att = re.search(r"(\d{1,3}(?:\.\d{3})+|\d{3,6})\s*(Zuschauer|ZUSCHAUER)", header_text)
                    if m_att:
                        try:
                            attendance = int(m_att.group(1).replace('.', ''))
                        except Exception:
                            attendance = None
                    m_ref = re.search(r"Schiedsrichter:([^\n]+)", header_text)
                    if m_ref:
                        referee = normalize_text(m_ref.group(1))
                        # Try to resolve referee_id from schiri pages if link present in row
                        ref_link_tag = row.find('a', href=re.compile(r'../schiri/'))
                        ref_href = ref_link_tag.get('href') if ref_link_tag else None
                        ref_id = self.get_or_create_referee(referee, ref_href)

                if opponent_name and home_goals is not None and away_goals is not None and is_home is not None:
                    opponent_id = self.get_or_create_opponent(opponent_name, opponent_link)
                    if is_home:
                        mainz_goals, opp_goals = home_goals, away_goals
                    else:
                        mainz_goals, opp_goals = away_goals, home_goals
                    match_url = str((season_dir / score_link).resolve()) if score_link else None
                    with self.conn, self.conn.cursor() as cur:
                        try:
                            cur.execute(
                                """
                                INSERT INTO public.Matches (season_id, gameday, is_home_game, opponent_id, mainz_goals, opponent_goals, match_details_url, result_string, attendance, referee, referee_id)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (season_id, gameday, opponent_id) DO UPDATE
                                  SET is_home_game = EXCLUDED.is_home_game,
                                      mainz_goals = EXCLUDED.mainz_goals,
                                      opponent_goals = EXCLUDED.opponent_goals,
                                      match_details_url = EXCLUDED.match_details_url,
                                      result_string = EXCLUDED.result_string,
                                      attendance = COALESCE(EXCLUDED.attendance, public.Matches.attendance),
                                      referee = COALESCE(EXCLUDED.referee, public.Matches.referee),
                                      referee_id = COALESCE(EXCLUDED.referee_id, public.Matches.referee_id)
                                RETURNING match_id
                                """,
                                (season_id, gameday, is_home, opponent_id, mainz_goals, opp_goals, match_url, score_text, attendance, referee, ref_id if 'ref_id' in locals() else None),
                            )
                            _ = cur.fetchone()[0]
                            matches_found += 1
                        except Exception as e:
                            self.logger.warning("Match upsert failed for %s GD%s vs %s: %s", season_name, gameday, opponent_name, e)
                else:
                    self.logger.debug("Skip row: season=%s gameday=%s due to incomplete data", season_name, gameday)

        with self.conn, self.conn.cursor() as cur:
            cur.execute("UPDATE public.Seasons SET total_matches = %s WHERE season_id = %s", (matches_found, season_id))
        return matches_found

    def parse_match_details(self, match_id: int, match_url: str) -> None:
        fp = Path(match_url)
        if not match_url or not fp.exists():
            return
        with fp.open('r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f, 'lxml')

        # Lineups, positions and cards
        row_index = 0
        for table in soup.find_all('table'):
            links = table.find_all('a', href=re.compile(r'../spieler/'))
            if not links:
                continue
            row_index += 1
            col_index = 0
            for link in links:
                col_index += 1
                name = normalize_player_name(link.get_text(strip=True))
                href = link.get('href')
                is_captain = link.find_parent('b') is not None
                parent_td = link.find_parent('td')
                yellow_card = red_card = False
                yellow_count = 0
                second_yellow = False
                jersey_number = None
                substituted_minute = None
                if parent_td:
                    parent_html = str(parent_td)
                    parent_text = parent_td.get_text()
                    # Cards detection; handle multiple yellows and second yellow
                    yellow_count = parent_html.count('gelbekarte') + parent_text.count('🟨')
                    red_card = ('rotekarte' in parent_html.lower()) or ('🟥' in parent_text)
                    yellow_card = yellow_count > 0
                    second_yellow = ('gelb-rot' in parent_html.lower()) or ('gelbrot' in parent_html.lower())
                    mnum = re.search(r'^(\s*)(\d+)', parent_text)
                    if mnum:
                        jersey_number = int(mnum.group(2))
                player_id = self.get_or_create_player(name, href)
                if not player_id:
                    continue
                with self.conn, self.conn.cursor() as cur:
                    try:
                        cur.execute(
                            """
                            INSERT INTO public.Match_Lineups (match_id, player_id, is_starter, is_captain, jersey_number, substituted_minute, yellow_card, red_card, yellow_card_count, second_yellow, position_row, position_col)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (match_id, player_id) DO UPDATE
                              SET is_starter = EXCLUDED.is_starter,
                                  is_captain = EXCLUDED.is_captain,
                                  jersey_number = COALESCE(EXCLUDED.jersey_number, public.Match_Lineups.jersey_number),
                                  substituted_minute = COALESCE(EXCLUDED.substituted_minute, public.Match_Lineups.substituted_minute),
                                  yellow_card = EXCLUDED.yellow_card,
                                  red_card = EXCLUDED.red_card,
                                  yellow_card_count = GREATEST(public.Match_Lineups.yellow_card_count, EXCLUDED.yellow_card_count),
                                  second_yellow = public.Match_Lineups.second_yellow OR EXCLUDED.second_yellow,
                                  position_row = COALESCE(EXCLUDED.position_row, public.Match_Lineups.position_row),
                                  position_col = COALESCE(EXCLUDED.position_col, public.Match_Lineups.position_col)
                            """,
                            (match_id, player_id, True, is_captain, jersey_number, substituted_minute, yellow_card, red_card, yellow_count, second_yellow, row_index, col_index),
                        )
                    except Exception as e:
                        self.logger.debug("Lineup upsert failed (match %s, player %s): %s", match_id, player_id, e)

        # Goals
        goals_header = soup.find('b', string=re.compile(r'Tore', re.IGNORECASE))
        goal_text = ""
        goal_table = None
        if goals_header:
            goal_table = goals_header.find_next('table')
            if goal_table:
                goal_text = goal_table.get_text()
            else:
                next_element = goals_header.find_next_sibling()
                goal_text = next_element.get_text() if next_element else ""
        if goal_text and ("nicht überliefert" not in goal_text and "keine" not in goal_text.lower()):
            if goal_table:
                for cell in goal_table.find_all('td'):
                    entry = cell.get_text(strip=True)
                    if not entry or not re.search(r'\d+\.', entry):
                        continue
                    m = re.match(r"(\d+)\.\s*(\d+:\d+)\s*([^\(]+)(?:\s*\(([^\)]+)\))?", entry)
                    if not m:
                        continue
                    minute = int(m.group(1))
                    score = m.group(2)
                    scorer_text = normalize_player_name(m.group(3))
                    assister_text = normalize_player_name(m.group(4)) if m.group(4) else None
                    is_penalty = any(tok in entry for tok in ['Elfmeter', 'FE', '11m'])
                    scorer_link = cell.find('a', href=re.compile(r'../spieler/'))
                    if scorer_link:
                        scorer_name = normalize_player_name(scorer_link.get_text(strip=True))
                        scorer_href = scorer_link.get('href')
                    else:
                        scorer_name = scorer_text
                        scorer_href = None
                    scorer_id = self.get_or_create_player(scorer_name, scorer_href)
                    assister_id = self.get_or_create_player(assister_text, None) if assister_text else None
                    if scorer_id:
                        with self.conn, self.conn.cursor() as cur:
                            try:
                                cur.execute(
                                    """
                                    INSERT INTO public.Goals (match_id, player_id, goal_minute, is_penalty, is_own_goal, assisted_by_player_id, score_at_time)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    ON CONFLICT (match_id, player_id, goal_minute, score_at_time) DO NOTHING
                                    """,
                                    (match_id, scorer_id, minute, is_penalty, False, assister_id, score),
                                )
                            except Exception as e:
                                self.logger.debug("Goal upsert failed (match %s): %s", match_id, e)

        # Substitutions (best-effort)
        all_text = soup.get_text(" ")
        for sm in re.finditer(r"(\d+)\.\s+([^f]+)\s+für\s+([^\n]+)", all_text):
            minute = int(sm.group(1))
            player_in = normalize_player_name(sm.group(2))
            player_out = normalize_player_name(sm.group(3))
            pid_in = self.get_or_create_player(player_in, None)
            pid_out = self.get_or_create_player(player_out, None)
            if pid_in and pid_out:
                with self.conn, self.conn.cursor() as cur:
                    try:
                        cur.execute(
                            "INSERT INTO public.Substitutions (match_id, minute, player_in_id, player_out_id) VALUES (%s, %s, %s, %s) ON CONFLICT (match_id, minute, player_in_id, player_out_id) DO NOTHING",
                            (match_id, minute, pid_in, pid_out),
                        )
                    except Exception as e:
                        self.logger.debug("Substitution upsert failed (match %s): %s", match_id, e)

    # ---------------- Enrichment from reference pages ----------------
    def _parse_key_value_table(self, soup: BeautifulSoup) -> dict:
        """Extract simple key:value facts often structured in two-column tables."""
        facts = {}
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) == 2:
                    key = normalize_text(cells[0].get_text())
                    val = normalize_text(cells[1].get_text())
                    if key and val:
                        facts[key.lower()] = val
        return facts

    def enrich_players_from_spieler(self) -> None:
        base = self.base_path / 'spieler'
        if not base.exists():
            return
        files = [p for p in base.glob('*.html') if p.is_file()]
        for i, fp in enumerate(files, 1):
            if i % 200 == 0:
                self.logger.info("Enrich players: %s/%s", i, len(files))
            try:
                with fp.open('r', encoding='latin-1', errors='ignore') as f:
                    soup = BeautifulSoup(f, 'lxml')
                
                # Infer name from title or first bold header
                name_tag = soup.find('h1') or soup.find('b') or soup.find('title')
                name = normalize_player_name(name_tag.get_text()) if name_tag else None
                
                # Get full text for regex parsing
                information = soup.get_text("\n", strip=True)
                
                # Parse birth date - use DOTALL to match across newlines
                dob = None
                birth_match = re.search(r"\*.*?(\d{2}\.\d{2}\.\d{4})", information, re.DOTALL)
                if birth_match:
                    dob = birth_match.group(1)
                
                # Parse height and weight from text (more reliable than table)
                height_match = re.search(r"(\d{2,3})\s*cm", information)
                height = height_match.group(1) if height_match else None
                
                weight_match = re.search(r"(\d{2,3})\s*kg", information)
                weight = weight_match.group(1) if weight_match else None
                
                # Parse position - look for bold "Position:" header
                pos = None
                position_header = soup.find("b", string=re.compile("Position", re.IGNORECASE))
                if position_header:
                    parent = position_header.find_parent()
                    if parent:
                        found_header = False
                        for string in parent.stripped_strings:
                            if found_header and string and not string.endswith(":"):
                                pos = normalize_text(string)
                                break
                            if "position" in string.lower():
                                found_header = True
                
                # Parse nationality - look for bold "Nationalität:" header
                nat = None
                nationality_header = soup.find("b", string=re.compile(r"Nationalit[aä]t", re.IGNORECASE))
                if nationality_header:
                    parent = nationality_header.find_parent()
                    if parent:
                        found_header = False
                        for string in parent.stripped_strings:
                            if found_header and string and not string.endswith(":"):
                                nat = normalize_text(string)
                                break
                            if "nationalit" in string.lower():
                                found_header = True
                
                # Foot preference (optional, keep existing table-based parsing as fallback)
                facts = self._parse_key_value_table(soup)
                foot = facts.get('fuss') or facts.get('fuß') or None
                
                pid = self.get_or_create_player(name or fp.stem, f"../spieler/{fp.name}")
                if not pid:
                    continue
                
                with self.conn, self.conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE public.Players
                        SET name = COALESCE(%s, name),
                            birth_date = COALESCE(%s::date, birth_date),
                            nationality = COALESCE(%s, nationality),
                            height_cm = COALESCE(NULLIF(REGEXP_REPLACE(%s, '\\D', '', 'g'), '')::int, height_cm),
                            weight_kg = COALESCE(NULLIF(REGEXP_REPLACE(%s, '\\D', '', 'g'), '')::int, weight_kg),
                            primary_position = COALESCE(%s, primary_position),
                            foot = COALESCE(%s, foot)
                        WHERE player_id = %s
                        """,
                        (name, dob, nat, height, weight, pos, foot, pid),
                    )

                # Try to parse career table blocks listing clubs and seasons
                try:
                    for table in soup.find_all('table'):
                        # Parse per-season line tables like in kohr.html (headers include Gelb/Gelb-Rot/Rot)
                        header_cells = table.find_all('td')
                        header_text = ' '.join(c.get_text(strip=True) for c in header_cells[:9]).lower()
                        if ('spiele' in header_text and 'gelb' in header_text and 'rot' in header_text) or ('einw.' in header_text):
                            # determine current competition by preceding bold row or link
                            comp = None
                            prev = table.find_previous('tr')
                            if prev:
                                comp = normalize_text(prev.get_text())
                            # iterate rows
                            for row in table.find_all('tr'):
                                cells = [c.get_text(strip=True) for c in row.find_all('td')]
                                if len(cells) >= 9 and any(ch.isdigit() for ch in ''.join(cells)):
                                    season_label = cells[0]
                                    # cells indexes: [season, spiele, einw., ausw., tore, vorl., gelb, gelb-rot, rot]
                                    def num(x):
                                        s = re.sub(r'[^0-9]', '', x)
                                        return int(s) if s else 0
                                    apps = num(cells[1]); subs_on = num(cells[2]); subs_off = num(cells[3])
                                    goals = num(cells[4]); assists = num(cells[5])
                                    yellow = num(cells[6]); second_yellow = num(cells[7]); red = num(cells[8])
                                    with self.conn, self.conn.cursor() as cur:
                                        cur.execute(
                                            """
                                            INSERT INTO public.Player_Season_Stats (player_id, season_label, competition, appearances, subs_on, subs_off, goals, assists, yellow_cards, second_yellow_cards, red_cards)
                                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                            ON CONFLICT (player_id, season_label, competition) DO UPDATE
                                              SET appearances = GREATEST(public.Player_Season_Stats.appearances, EXCLUDED.appearances),
                                                  subs_on = GREATEST(public.Player_Season_Stats.subs_on, EXCLUDED.subs_on),
                                                  subs_off = GREATEST(public.Player_Season_Stats.subs_off, EXCLUDED.subs_off),
                                                  goals = GREATEST(public.Player_Season_Stats.goals, EXCLUDED.goals),
                                                  assists = GREATEST(public.Player_Season_Stats.assists, EXCLUDED.assists),
                                                  yellow_cards = GREATEST(public.Player_Season_Stats.yellow_cards, EXCLUDED.yellow_cards),
                                                  second_yellow_cards = GREATEST(public.Player_Season_Stats.second_yellow_cards, EXCLUDED.second_yellow_cards),
                                                  red_cards = GREATEST(public.Player_Season_Stats.red_cards, EXCLUDED.red_cards)
                                            """,
                                            (pid, season_label, comp, apps, subs_on, subs_off, goals, assists, yellow, second_yellow, red),
                                        )
                            continue
                        header = table.find_previous_sibling(['h2', 'h3'])
                        if header and ('vereine' in header.get_text().lower() or 'karriere' in header.get_text().lower()):
                            for row in table.find_all('tr'):
                                cells = [c.get_text(strip=True) for c in row.find_all('td')]
                                if len(cells) < 2:
                                    continue
                                season = cells[0]
                                club = cells[1]
                                apps = None; goals = None
                                if len(cells) >= 4:
                                    apps = cells[2]; goals = cells[3]
                                # Parse season like 2007/08 or 1999-2001
                                start_year = end_year = None
                                m1 = re.match(r"(\d{4})\s*[/-]\s*(\d{2,4})", season)
                                if m1:
                                    start_year = int(m1.group(1))
                                    y2 = m1.group(2)
                                    end_year = int(y2) if len(y2) == 4 else start_year + int(y2)
                                else:
                                    m2 = re.match(r"(\d{4})", season)
                                    if m2:
                                        start_year = int(m2.group(1))
                                club_name = normalize_text(club)
                                if not club_name:
                                    continue
                                # best-effort link to Opponents
                                opp_id = None
                                link = row.find('a')
                                if link and link.get('href') and '../gegner/' in link.get('href'):
                                    opp_name = normalize_text(link.get_text())
                                    opp_id = self.get_or_create_opponent(opp_name, link.get('href'))
                                with self.conn, self.conn.cursor() as cur:
                                    cur.execute(
                                        """
                                        INSERT INTO public.Player_Careers (player_id, club_name, opponent_id, start_year, end_year, appearances, goals)
                                        VALUES (%s, %s, %s, %s, %s, NULLIF(REGEXP_REPLACE(%s, '\\D', '', 'g'), '')::int, NULLIF(REGEXP_REPLACE(%s, '\\D', '', 'g'), '')::int)
                                        ON CONFLICT (player_id, club_name, start_year, end_year) DO NOTHING
                                        """,
                                        (pid, club_name, opp_id, start_year, end_year, apps, goals),
                                    )
                except Exception:
                    pass
            except Exception as e:
                self.logger.debug("Player enrich failed for %s: %s", fp.name, e)

    def enrich_opponents_from_gegner(self) -> None:
        base = self.base_path / 'gegner'
        if not base.exists():
            return
        files = [p for p in base.glob('*.html') if p.is_file()]
        for fp in files:
            try:
                with fp.open('r', encoding='utf-8', errors='ignore') as f:
                    soup = BeautifulSoup(f, 'lxml')
                name_tag = soup.find('h1') or soup.find('b') or soup.find('title')
                name = normalize_text(name_tag.get_text()) if name_tag else fp.stem
                oid = self.get_or_create_opponent(name, f"../gegner/{fp.name}")
                facts = self._parse_key_value_table(soup)
                city = facts.get('stadt') or facts.get('ort') or None
                country = facts.get('land') or None
                founded = facts.get('gegruendet') or facts.get('gegründet') or None
                with self.conn, self.conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE public.Opponents
                        SET city = COALESCE(%s, city),
                            country = COALESCE(%s, country),
                            founded_year = COALESCE(NULLIF(REGEXP_REPLACE(%s, '\\D', '', 'g'), '')::int, founded_year)
                        WHERE opponent_id = %s
                        """,
                        (city, country, founded, oid),
                    )
            except Exception as e:
                self.logger.debug("Opponent enrich failed for %s: %s", fp.name, e)

    def enrich_coaches_from_trainer(self) -> None:
        base = self.base_path / 'trainer'
        if not base.exists():
            return
        for fp in base.glob('*.html'):
            try:
                with fp.open('r', encoding='utf-8', errors='ignore') as f:
                    soup = BeautifulSoup(f, 'lxml')
                name_tag = soup.find('h1') or soup.find('b') or soup.find('title')
                name = normalize_text(name_tag.get_text()) if name_tag else fp.stem
                cid = self.get_or_create_coach(name, f"../trainer/{fp.name}")
                facts = self._parse_key_value_table(soup)
                dob = facts.get('geburtsdatum') or None
                nat = facts.get('nationalitaet') or facts.get('nationalität') or None
                with self.conn, self.conn.cursor() as cur:
                    cur.execute(
                        "UPDATE public.Coaches SET date_of_birth = COALESCE(%s::date, date_of_birth), nationality = COALESCE(%s, nationality) WHERE coach_id = %s",
                        (dob, nat, cid),
                    )
            except Exception as e:
                self.logger.debug("Coach enrich failed for %s: %s", fp.name, e)

    def enrich_referees_from_schiri(self) -> None:
        base = self.base_path / 'schiri'
        if not base.exists():
            return
        for fp in base.glob('*.html'):
            try:
                with fp.open('r', encoding='utf-8', errors='ignore') as f:
                    soup = BeautifulSoup(f, 'lxml')
                name_tag = soup.find('h1') or soup.find('b') or soup.find('title')
                name = normalize_text(name_tag.get_text()) if name_tag else fp.stem
                rid = self.get_or_create_referee(name, f"../schiri/{fp.name}")
                facts = self._parse_key_value_table(soup)
                dob = facts.get('geburtsdatum') or None
                assoc = facts.get('verband') or None
                country = facts.get('land') or None
                with self.conn, self.conn.cursor() as cur:
                    cur.execute(
                        "UPDATE public.Referees SET date_of_birth = COALESCE(%s::date, date_of_birth), association = COALESCE(%s, association), country = COALESCE(%s, country) WHERE referee_id = %s",
                        (dob, assoc, country, rid),
                    )
            except Exception as e:
                self.logger.debug("Referee enrich failed for %s: %s", fp.name, e)

    def run(self, limit_matches: Optional[int] = None) -> None:
        self.setup_schema()

        # Pass 1: seasons + matches
        seasons = []
        for item in os.listdir(self.base_path):
            if re.match(r"\d{4}-\d{2}", item) and (self.base_path / item).is_dir():
                seasons.append(item)
        seasons.sort()

        total_matches = 0
        for season in seasons:
            season_dir = self.base_path / season
            found = self.parse_season_overview(season_dir, season)
            self.logger.info("%s: %s matches", season, found)
            total_matches += found

        # Fetch match ids + urls for Pass 2
        with self.conn, self.conn.cursor() as cur:
            cur.execute("SELECT match_id, match_details_url FROM public.Matches WHERE match_details_url IS NOT NULL ORDER BY match_id")
            matches = cur.fetchall()

        if limit_matches is not None:
            matches = matches[:limit_matches]

        for i, (match_id, url) in enumerate(matches, 1):
            if i % 200 == 0:
                self.logger.info("Parsed %s/%s match details", i, len(matches))
            self.parse_match_details(match_id, url)
        self.logger.info("Parsed all match details: %s", len(matches))

        # Enrich entities from reference pages (players, opponents, coaches, referees)
        try:
            self.enrich_players_from_spieler()
            self.enrich_opponents_from_gegner()
            self.enrich_coaches_from_trainer()
            self.enrich_referees_from_schiri()
        except Exception as e:
            self.logger.warning("Entity enrichment failed/partial: %s", e)

        # Compute and upsert embeddings into Postgres
        try:
            ensure_vector_extension(self.config)
            embedder = OpenAIEmbeddings(api_key=self.config.OPENAI_API_KEY, model=self.config.OPENAI_EMBEDDING_MODEL)
            with self.conn.cursor() as cur:
                cur.execute("SELECT player_id, player_name FROM public.Players ORDER BY player_id")
                players = [("player", int(pid), name) for pid, name in cur.fetchall()]
            with self.conn.cursor() as cur:
                cur.execute("SELECT opponent_id, opponent_name FROM public.Opponents ORDER BY opponent_id")
                opponents = [("opponent", int(oid), name) for oid, name in cur.fetchall()]
            all_rows = players + opponents
            self.logger.info("Embedding %s names (players+opponents)", len(all_rows))
            batch_size = 128
            for i in range(0, len(all_rows), batch_size):
                chunk = all_rows[i:i+batch_size]
                names = [name for _, _, name in chunk]
                vecs = embedder.embed_documents(names)
                payload = [(kind, ent_id, name, vec) for (kind, ent_id, name), vec in zip(chunk, vecs)]
                upsert_embeddings(self.config, payload)
            self.logger.info("Embeddings upsert complete")
        except Exception as e:
            self.logger.warning("Embedding step skipped/failed: %s", e)

        # Mirror to SQLite if requested
        if self.mirror_sqlite:
            self.mirror_to_sqlite(self.mirror_sqlite)

    def mirror_to_sqlite(self, sqlite_path: Path) -> None:
        if sqlite_path.exists():
            sqlite_path.unlink()
        conn_sqlite = sqlite3.connect(str(sqlite_path))
        cur_s = conn_sqlite.cursor()
        # Create schema
        cur_s.executescript(
            """
            CREATE TABLE Seasons (season_id INTEGER PRIMARY KEY, season_name TEXT UNIQUE, league_name TEXT, total_matches INTEGER);
            CREATE TABLE Opponents (opponent_id INTEGER PRIMARY KEY, opponent_name TEXT UNIQUE, opponent_link TEXT);
            CREATE TABLE Players (player_id INTEGER PRIMARY KEY, player_name TEXT UNIQUE, player_link TEXT);
            CREATE TABLE Matches (
                match_id INTEGER PRIMARY KEY,
                season_id INTEGER, gameday INTEGER, is_home_game BOOLEAN,
                opponent_id INTEGER, mainz_goals INTEGER, opponent_goals INTEGER,
                match_details_url TEXT, result_string TEXT
            );
            CREATE TABLE Match_Lineups (
                lineup_id INTEGER PRIMARY KEY, match_id INTEGER, player_id INTEGER,
                is_starter BOOLEAN, is_captain BOOLEAN, jersey_number INTEGER,
                substituted_minute INTEGER, yellow_card BOOLEAN, red_card BOOLEAN
            );
            CREATE TABLE Goals (
                goal_id INTEGER PRIMARY KEY, match_id INTEGER, player_id INTEGER,
                goal_minute INTEGER, is_penalty BOOLEAN, is_own_goal BOOLEAN,
                assisted_by_player_id INTEGER, score_at_time TEXT
            );
            CREATE TABLE Substitutions (
                substitution_id INTEGER PRIMARY KEY, match_id INTEGER, minute INTEGER,
                player_in_id INTEGER, player_out_id INTEGER
            );
            """
        )
        # Copy data from PG
        with self.conn.cursor() as cur:
            # Map of SQLite table -> explicit columns to pull from Postgres in the same order
            columns_map = {
                "Seasons": ["season_id", "season_name", "league_name", "total_matches"],
                "Opponents": ["opponent_id", "opponent_name", "opponent_link"],
                "Players": ["player_id", "player_name", "player_link"],
                "Matches": [
                    "match_id",
                    "season_id",
                    "gameday",
                    "is_home_game",
                    "opponent_id",
                    "mainz_goals",
                    "opponent_goals",
                    "match_details_url",
                    "result_string",
                ],
                "Match_Lineups": [
                    "lineup_id",
                    "match_id",
                    "player_id",
                    "is_starter",
                    "is_captain",
                    "jersey_number",
                    "substituted_minute",
                    "yellow_card",
                    "red_card",
                ],
                "Goals": [
                    "goal_id",
                    "match_id",
                    "player_id",
                    "goal_minute",
                    "is_penalty",
                    "is_own_goal",
                    "assisted_by_player_id",
                    "score_at_time",
                ],
                "Substitutions": [
                    "substitution_id",
                    "match_id",
                    "minute",
                    "player_in_id",
                    "player_out_id",
                ],
            }

            for table, columns in columns_map.items():
                select_cols = ", ".join(columns)
                cur.execute(f"SELECT {select_cols} FROM public.{table}")
                rows = cur.fetchall()
                if not rows:
                    continue
                placeholders = ",".join(["?"] * len(columns))
                insert_cols = ", ".join(columns)
                cur_s.executemany(f"INSERT INTO {table} ({insert_cols}) VALUES ({placeholders})", rows)
        conn_sqlite.commit()
        conn_sqlite.close()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    parser = argparse.ArgumentParser(description="Reparse HTML and ingest into Postgres (optionally mirror to SQLite)")
    parser.add_argument("--base-path", default=str(Path(__file__).parent / "fsvarchiv"))
    parser.add_argument("--reset", action="store_true", help="Drop and recreate tables")
    parser.add_argument("--limit-matches", type=int, default=None, help="Limit number of match detail pages to parse")
    parser.add_argument("--mirror-sqlite", type=str, default=str(Path(__file__).parent / "fsv_archive_clean.db"))
    parser.add_argument("--mirror-only", action="store_true", help="Only mirror existing Postgres data to SQLite and exit")
    args = parser.parse_args()

    ing = PGIngestor(Path(args.base_path), reset=args.reset, mirror_sqlite=Path(args.mirror_sqlite) if args.mirror_sqlite else None)
    if args.mirror_only:
        if not args.mirror_sqlite:
            raise SystemExit("--mirror-only requires --mirror-sqlite to be set")
        ing.mirror_to_sqlite(Path(args.mirror_sqlite))
    else:
        ing.run(limit_matches=args.limit_matches)
    print("Ingestion complete.")


if __name__ == "__main__":
    main()


