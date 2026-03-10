import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from bs4 import BeautifulSoup

from parsing.database_manager import DatabaseManager
from parsing.html_utils import normalize_name, normalize_whitespace, read_html


class ProfileEnrichmentMixin:
    base_path: Path
    db: DatabaseManager
    logger: logging.Logger
    player_file_index: Dict[str, Path]

    def parse_player_profile(
        self,
        player_name: str,
        season_path: Path,
        profile_url: Optional[str] = None,
    ) -> None:
        normalized = normalize_name(player_name)
        player_file = None
        if profile_url:
            candidate = self.base_path / profile_url
            if candidate.exists():
                player_file = candidate
                self.player_file_index.setdefault(normalized, player_file)
        if player_file is None:
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
        if name.startswith('?'):
            name = name[1:].strip()
        name = re.sub(r'^wdh\.\s*', '', name, flags=re.IGNORECASE).strip()
        information = soup.get_text("\n", strip=True)

        birth_match = re.search(r"\*.*?(\d{2}\.\d{2}\.\d{4}).*?in\s+([^,\n]+)", information, re.DOTALL)
        birth_date = None
        birth_place = None
        if birth_match:
            try:
                birth_date = datetime.strptime(birth_match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
            except ValueError:
                birth_date = birth_match.group(1)
            birth_place = birth_match.group(2).strip()

        height_match = re.search(r"(\d{2,3})\s*cm", information)
        weight_match = re.search(r"(\d{2,3})\s*kg", information)
        height_cm = int(height_match.group(1)) if height_match else None
        weight_kg = int(weight_match.group(1)) if weight_match else None
        primary_position = self._extract_labeled_value(soup, "Position")
        nationality = self._extract_labeled_value(soup, r"Nationalit[aä]t")
        image = soup.find("img")
        image_url = image["src"] if image else None

        cursor = self.db.conn.cursor()
        relative_profile_url = str(player_file.relative_to(self.base_path))
        normalized_requested_name = normalize_name(player_name)
        normalized_profile_name = normalize_name(name)
        cursor.execute(
            """
            SELECT player_id
            FROM players
            WHERE profile_url = ?
               OR normalized_name = ?
               OR normalized_name = ?
            ORDER BY CASE
                WHEN profile_url = ? THEN 0
                WHEN normalized_name = ? THEN 1
                ELSE 2
            END
            LIMIT 1
            """,
            (
                relative_profile_url,
                normalized_profile_name,
                normalized_requested_name,
                relative_profile_url,
                normalized_profile_name,
            ),
        )
        row = cursor.fetchone()
        if not row:
            self.logger.warning(
                "Player '%s' not found in database for profile update (profile=%s)",
                player_name,
                relative_profile_url,
            )
            return

        player_id = row[0]
        cursor.execute(
            """
            UPDATE players
            SET birth_date = COALESCE(?, birth_date),
                birth_place = COALESCE(?, birth_place),
                height_cm = COALESCE(?, height_cm),
                weight_kg = COALESCE(?, weight_kg),
                primary_position = COALESCE(?, primary_position),
                nationality = COALESCE(?, nationality),
                image_url = COALESCE(?, image_url)
            WHERE player_id = ?
            """,
            (birth_date, birth_place, height_cm, weight_kg, primary_position, nationality, image_url, player_id),
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

    def enrich_all_player_profiles(self) -> None:
        spieler_dir = self.base_path / "spieler"
        if not spieler_dir.exists():
            self.logger.warning("spieler/ directory not found")
            return
        player_files = list(spieler_dir.glob("*.html"))
        self.logger.info("Found %d player profile files", len(player_files))
        enriched = 0
        for index, player_file in enumerate(player_files, 1):
            if index % 500 == 0:
                self.logger.info("  Enriched %d/%d player profiles", index, len(player_files))
            soup = read_html(player_file)
            if soup is None:
                continue
            header = soup.find("b")
            if not header:
                continue
            profile_name = normalize_whitespace(header.get_text(" ", strip=True))
            relative_url = str(player_file.relative_to(self.base_path))
            player_id = self.db.get_or_create_player(profile_name, relative_url)
            self._enrich_player_from_profile(player_id, player_file, soup)
            enriched += 1
        self.logger.info("Enriched %d player records from %d profile files", enriched, len(player_files))

    def _enrich_player_from_profile(self, player_id: int, player_file: Path, soup: BeautifulSoup) -> None:
        information = soup.get_text("\n", strip=True)
        birth_match = re.search(r"\*.*?(\d{2}\.\d{2}\.\d{4}).*?in\s+([^,\n]+)", information, re.DOTALL)
        birth_date = None
        birth_place = None
        if birth_match:
            try:
                birth_date = datetime.strptime(birth_match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
            except ValueError:
                birth_date = birth_match.group(1)
            birth_place = birth_match.group(2).strip()

        height_match = re.search(r"(\d{2,3})\s*cm", information)
        weight_match = re.search(r"(\d{2,3})\s*kg", information)
        height_cm = int(height_match.group(1)) if height_match else None
        weight_kg = int(weight_match.group(1)) if weight_match else None
        primary_position = self._extract_labeled_value(soup, "Position")
        nationality = self._extract_labeled_value(soup, r"Nationalit[aä]t")
        image = soup.find("img")
        image_url = image["src"] if image else None

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
            (
                birth_date,
                birth_place,
                height_cm,
                weight_kg,
                primary_position,
                nationality,
                image_url,
                str(player_file.relative_to(self.base_path)),
                player_id,
            ),
        )
        self.db.conn.commit()

    def enrich_all_coach_profiles(self) -> None:
        trainer_dir = self.base_path / "trainer"
        if not trainer_dir.exists():
            self.logger.warning("trainer/ directory not found")
            return
        coach_files = list(trainer_dir.glob("*.html"))
        self.logger.info("Found %d coach profile files", len(coach_files))
        enriched = 0
        for index, coach_file in enumerate(coach_files, 1):
            if index % 50 == 0:
                self.logger.info("  Enriched %d/%d coach profiles", index, len(coach_files))
            soup = read_html(coach_file)
            if soup is None:
                continue
            header = soup.find("b")
            if not header:
                continue
            profile_name = normalize_whitespace(header.get_text(" ", strip=True))
            relative_url = str(coach_file.relative_to(self.base_path))
            coach_id = self.db.get_or_create_coach(profile_name, relative_url)
            if coach_id:
                self._enrich_coach_from_profile(coach_id, profile_name, coach_file, soup)
                enriched += 1
        self.logger.info("Enriched %d coach records from %d profile files", enriched, len(coach_files))

    def _enrich_coach_from_profile(self, coach_id: int, profile_name: str, coach_file: Path, soup: BeautifulSoup) -> None:
        information = soup.get_text("\n", strip=True)
        birth_match = re.search(r"\*.*?(\d{2}\.\d{2}\.\d{4}).*?in\s+([^,\n.]+)", information, re.DOTALL)
        birth_date = None
        birth_place = None
        if birth_match:
            try:
                birth_date = datetime.strptime(birth_match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
            except ValueError:
                birth_date = birth_match.group(1)
            birth_place = birth_match.group(2).strip()
        nationality = self._extract_labeled_value(soup, r"Nationalit[aä]t")

        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            UPDATE coaches
            SET name = ?,
                normalized_name = ?,
                birth_date = COALESCE(?, birth_date),
                birth_place = COALESCE(?, birth_place),
                nationality = COALESCE(?, nationality),
                profile_url = COALESCE(?, profile_url)
            WHERE coach_id = ?
            """,
            (
                profile_name,
                normalize_name(profile_name),
                birth_date,
                birth_place,
                nationality,
                str(coach_file.relative_to(self.base_path)),
                coach_id,
            ),
        )

        career_header = soup.find("b", string=re.compile("Laufbahn", re.IGNORECASE))
        if career_header:
            career_table = career_header.find_next("table")
            if career_table:
                cursor.execute("DELETE FROM coach_careers WHERE coach_id = ?", (coach_id,))
                for row in career_table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) < 5:
                        continue
                    start_date = normalize_whitespace(cells[0].get_text(" ", strip=True))
                    end_date = normalize_whitespace(cells[2].get_text(" ", strip=True))
                    team_text = normalize_whitespace(cells[4].get_text(" ", strip=True)) if len(cells) > 4 else None
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

    def build_player_index(self) -> Dict[str, Path]:
        index: Dict[str, Path] = {}
        player_dir = self.base_path / "spieler"
        if player_dir.exists():
            for path in player_dir.glob("*.html"):
                index[normalize_name(path.stem)] = path
        return index

    def get_full_name_from_profile(self, profile_url: str) -> Optional[str]:
        if not profile_url:
            return None
        profile_path = self.base_path / profile_url
        if not profile_path.exists():
            return None
        soup = read_html(profile_path)
        if soup is None:
            return None
        header = soup.find("b")
        if not header:
            return None
        full_name = normalize_whitespace(header.get_text(" ", strip=True))
        if full_name.startswith('?'):
            full_name = full_name[1:].strip()
        full_name = re.sub(r'^wdh\.\s*', '', full_name, flags=re.IGNORECASE).strip()
        if not full_name or len(full_name) < 2:
            return None
        return full_name

    def resolve_player_name(self, name: str, profile_url: Optional[str] = None) -> tuple[str, Optional[str]]:
        if not profile_url:
            normalized = normalize_name(name)
            profile_path = self.player_file_index.get(normalized)
            if profile_path:
                fallback_url = str(profile_path.relative_to(self.base_path))
                full_name = self.get_full_name_from_profile(fallback_url)
                return (full_name, fallback_url) if full_name else (name, fallback_url)
            return name, None

        normalized_profile_url = profile_url.replace("../", "")
        full_name = self.get_full_name_from_profile(normalized_profile_url)
        if full_name:
            return full_name, normalized_profile_url
        return name, normalized_profile_url

    def _extract_labeled_value(self, soup: BeautifulSoup, label_pattern: str) -> Optional[str]:
        header = soup.find("b", string=re.compile(label_pattern, re.IGNORECASE))
        if not header:
            return None
        parent = header.find_parent()
        if not parent:
            return None
        found_header = False
        for string in parent.stripped_strings:
            if found_header and string and not string.endswith(":"):
                return normalize_whitespace(string)
            if re.search(label_pattern, string, re.IGNORECASE):
                found_header = True
        return None
