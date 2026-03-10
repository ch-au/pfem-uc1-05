import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from bs4 import BeautifulSoup
from parsing.database_manager import DatabaseManager, MAINZ_TEAM_KEY
from parsing.html_utils import normalize_name, normalize_whitespace, parse_int, read_html
from parsing.match_types import GoalEvent, MatchMetadata, PlayerAppearance
from parsing.parser_match_helpers import MatchParsingMixin
from parsing.parser_profile_enrichment import ProfileEnrichmentMixin
from parsing.source_preparation import prepare_input_source


class ComprehensiveFSVParser(ProfileEnrichmentMixin, MatchParsingMixin):
    """Parse the FSV Mainz 05 archive into a relational SQLite database."""

    def __init__(
        self,
        base_path: str = "fsvarchiv",
        source: Optional[str] = None,
        db_name: str = "fsv_archive_complete.db",
        seasons: Optional[Sequence[str]] = None,
    ):
        self.prepared_source = prepare_input_source(source or base_path)
        self.base_path = self.prepared_source.local_root
        self.source_label = self.prepared_source.display_source
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
        start_year, end_year = self._season_year_range(season_name)
        season_id = self.db.ensure_season(season_name, start_year, end_year, self.mainz_team_id)

        self.logger.info("Processing season %s", season_name)
        for competition_label, level, overview_path in self._build_overview_files(season_path):
            self._process_competition(season_id, season_path, competition_label, level, overview_path)

    def _season_year_range(self, season_name: str) -> Tuple[int, int]:
        start_year = int(season_name[:4])
        suffix = int(season_name[-2:])
        end_year = int(f"20{suffix:02d}") if suffix <= 30 else int(f"19{suffix:02d}")
        return start_year, end_year

    def _resolve_primary_league_overview(self, season_path: Path) -> Tuple[str, str, Path]:
        league_name = None
        league_file = None
        for filename in ["profiliga.html", "profitab.html", "profitabb.html"]:
            candidate = season_path / filename
            if candidate.exists():
                league_name = self._extract_league_from_html(candidate)
                if league_name:
                    league_file = candidate
                    break

        if not league_name:
            league_name = "Bundesliga"
            league_file = season_path / "profiliga.html"
            self.logger.warning(
                "Could not extract league name for %s, defaulting to Bundesliga",
                season_path.name,
            )

        return league_name, self._determine_league_level(league_name), league_file

    def _build_overview_files(self, season_path: Path) -> List[Tuple[str, str, Path]]:
        league_name, league_level, league_file = self._resolve_primary_league_overview(season_path)
        overview_files = [
            (league_name, league_level, league_file),
            ("DFB-Pokal", "cup", season_path / "profipokal.html"),
        ]

        for european_stub in ["profiuefa", "profiuec", "profiuecl", "profiintertoto", "profiueclq"]:
            overview = season_path / f"{european_stub}.html"
            if overview.exists():
                overview_files.append(("Europapokal", "international", overview))

        profirest_file = season_path / "profirest.html"
        if profirest_file.exists():
            overview_files.append(("Freundschaftsspiele", "friendly", profirest_file))
        return overview_files

    def _process_competition(
        self,
        season_id: int,
        season_path: Path,
        competition_label: str,
        level: str,
        overview_path: Path,
    ) -> None:
        if not overview_path.exists():
            return

        competition_id = self.db.get_or_create_competition(competition_label, level)
        actual_overview_path, matches = self.parse_competition_overview(season_path, overview_path)
        try:
            source_relpath = actual_overview_path.relative_to(self.base_path)
        except ValueError:
            source_relpath = overview_path.relative_to(self.base_path)

        season_competition_id = self.db.ensure_season_competition(
            season_id,
            competition_id,
            competition_label,
            str(source_relpath),
        )

        self.logger.info("  %s: %d fixtures", competition_label, len(matches))
        if matches:
            self._process_detail_matches(
                season_competition_id,
                season_path,
                competition_label,
                matches,
            )
        else:
            self._process_fallback_matches(
                season_competition_id,
                season_path,
                competition_label,
            )

        self.parse_season_table(season_competition_id, season_path, actual_overview_path.name)
        if competition_label == "Bundesliga":
            self.parse_season_squad(season_competition_id, season_path)

    def _process_detail_matches(
        self,
        season_competition_id: int,
        season_path: Path,
        competition_label: str,
        matches: List[Dict[str, Optional[str]]],
    ) -> None:
        seen_details: set[str] = set()
        for match in matches:
            detail_path = season_path / match["detail_file"]
            detail_rel = str(detail_path.relative_to(self.base_path))
            if detail_rel in seen_details:
                self.logger.debug(
                    "    skipping duplicate detail page %s for %s",
                    detail_rel,
                    competition_label,
                )
                continue
            seen_details.add(detail_rel)
            if not detail_path.exists():
                self.logger.warning("    detail page missing: %s", detail_rel)
                continue

            try:
                parsed_entries = self._parse_detail_entries(detail_path, detail_rel, match, season_path)
            except (FileNotFoundError, ValueError) as exc:
                self.logger.warning("    skipping %s (%s)", detail_rel, exc)
                continue

            for entry_rel, parsed_match in parsed_entries:
                try:
                    self._persist_parsed_match(
                        season_competition_id,
                        entry_rel,
                        season_path,
                        *parsed_match,
                    )
                except Exception as exc:
                    self._record_match_failure(entry_rel, exc)
                else:
                    self._record_match_success()

    def _parse_detail_entries(
        self,
        detail_path: Path,
        detail_rel: str,
        overview_info: Dict[str, Optional[str]],
        season_path: Path,
    ) -> List[Tuple[str, Tuple[MatchMetadata, Dict[str, Dict[str, PlayerAppearance]], List[Dict[str, Optional[str]]], List[GoalEvent], List[Dict[str, Optional[str]]]]]]:
        if detail_path.stem.lower().startswith("profirest"):
            profirest_entries = self._parse_profirest_detail_entries(detail_path, detail_rel, overview_info)
            if profirest_entries:
                return profirest_entries
        parsed_match = self.parse_match_detail(detail_path, overview_info, season_path)
        return [(detail_rel, parsed_match)]

    def _parse_profirest_detail_entries(
        self,
        detail_path: Path,
        detail_rel: str,
        overview_info: Dict[str, Optional[str]],
    ) -> List[Tuple[str, Tuple[MatchMetadata, Dict[str, Dict[str, PlayerAppearance]], List[Dict[str, Optional[str]]], List[GoalEvent], List[Dict[str, Optional[str]]]]]]:
        soup = read_html(detail_path)
        if soup is None:
            raise FileNotFoundError(detail_path)

        match_blocks = soup.find_all("table", attrs={"width": "100%", "height": "45%"})
        if not match_blocks:
            match_blocks = self._extract_profirest_side_by_side_blocks(soup)

        entries = []
        for index, block in enumerate(match_blocks, 1):
            match_data = self.parse_profirest_match_block(block, overview_info)
            if not match_data:
                continue
            entries.append(
                (
                    f"{detail_rel}#match{index}",
                    (
                        match_data["metadata"],
                        match_data["lineups"],
                        match_data["substitutions"],
                        match_data["goals"],
                        match_data["cards"],
                    ),
                )
            )
        return entries

    def _process_fallback_matches(
        self,
        season_competition_id: int,
        season_path: Path,
        competition_label: str,
    ) -> None:
        fallback_matches = self.parse_profitab_fallback(season_path, competition_label)
        if not fallback_matches:
            self.logger.info("  %s: no fixtures available", competition_label)
            return

        self.logger.info(
            "  %s: using fallback tab data for %d fixtures",
            competition_label,
            len(fallback_matches),
        )
        for metadata, source_rel in fallback_matches:
            home_team_id = self.db.get_or_create_team(metadata.home_team)
            away_team_id = self.db.get_or_create_team(metadata.away_team)
            referee_id = self.db.get_or_create_referee(metadata.referee, metadata.referee_link)
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

    def _persist_parsed_match(
        self,
        season_competition_id: int,
        detail_rel: str,
        season_path: Path,
        metadata: MatchMetadata,
        lineups: Dict[str, Dict[str, PlayerAppearance]],
        substitutions: List[Dict[str, Optional[str]]],
        goals: List[GoalEvent],
        cards: List[Dict[str, Optional[str]]],
    ) -> None:
        home_team_id = self.db.get_or_create_team(metadata.home_team)
        away_team_id = self.db.get_or_create_team(metadata.away_team)
        referee_id = self.db.get_or_create_referee(metadata.referee, metadata.referee_link)

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

            self.db.batch_insert_lineups(
                self._build_lineup_batch(match_id, home_team_id, away_team_id, lineups, season_path),
                self.stats,
            )
            self.db.batch_insert_substitutions(
                self._build_substitution_batch(match_id, home_team_id, away_team_id, substitutions),
                self.stats,
            )
            self.db.batch_insert_goals(
                self._build_goal_batch(match_id, home_team_id, away_team_id, goals),
                self.stats,
            )
            self.db.batch_insert_cards(
                self._build_card_batch(match_id, home_team_id, away_team_id, cards),
                self.stats,
            )

    def _build_lineup_batch(
        self,
        match_id: int,
        home_team_id: int,
        away_team_id: int,
        lineups: Dict[str, Dict[str, PlayerAppearance]],
        season_path: Path,
    ) -> List[Tuple[int, int, int, Optional[int], int, Optional[int], Optional[int], Optional[int], Optional[int]]]:
        lineups_batch = []
        for team_id, roster in (
            (home_team_id, lineups["home"]),
            (away_team_id, lineups["away"]),
        ):
            for appearance in roster.values():
                player_name, profile_url = self.resolve_player_name(appearance.name, appearance.profile_url)
                try:
                    player_id = self.db.get_or_create_player(player_name, profile_url)
                except ValueError as exc:
                    self.logger.warning("Skipping invalid player name: %s (%s)", player_name, exc)
                    continue
                lineups_batch.append(
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
                    )
                )
                if profile_url and appearance.name not in self.players_processed:
                    self.parse_player_profile(appearance.name, season_path, profile_url)
                    self.players_processed[appearance.name] = True
        return lineups_batch

    def _build_substitution_batch(
        self,
        match_id: int,
        home_team_id: int,
        away_team_id: int,
        substitutions: List[Dict[str, Optional[str]]],
    ) -> List[Tuple[int, int, Optional[int], Optional[int], Optional[int], Optional[int]]]:
        substitutions_batch = []
        for sub in substitutions:
            team_id = home_team_id if sub["team_role"] == "home" else away_team_id
            player_on_name, player_on_url = self.resolve_player_name(sub["player_on"], sub.get("player_on_link"))
            player_off_name, player_off_url = self.resolve_player_name(sub["player_off"], sub.get("player_off_link"))
            try:
                player_on_id = self.db.get_or_create_player(player_on_name, player_on_url)
                player_off_id = self.db.get_or_create_player(player_off_name, player_off_url)
            except ValueError as exc:
                self.logger.warning(
                    "Skipping invalid substitution (%s -> %s): %s",
                    player_off_name,
                    player_on_name,
                    exc,
                )
                continue
            substitutions_batch.append(
                (
                    match_id,
                    team_id,
                    sub["minute"],
                    sub["stoppage"],
                    player_on_id,
                    player_off_id,
                )
            )
        return substitutions_batch

    def _build_goal_batch(
        self,
        match_id: int,
        home_team_id: int,
        away_team_id: int,
        goals: List[GoalEvent],
    ) -> List[Tuple[int, int, Optional[int], Optional[int], int, Optional[int], int, int, str]]:
        goals_batch = []
        for goal in goals:
            team_id = home_team_id if goal.team_role == "home" else away_team_id
            raw_scorer = goal.scorer
            scorer_name, scorer_url = self.resolve_player_name(goal.scorer, goal.scorer_profile_url)
            try:
                player_id = self.db.get_or_create_player(scorer_name, scorer_url)
            except ValueError as exc:
                self.logger.warning("Skipping invalid goal scorer: %s (%s)", scorer_name, exc)
                continue
            if normalize_name(raw_scorer) != normalize_name(scorer_name):
                self.db.add_player_alias(player_id, raw_scorer)

            assist_id = None
            if goal.assist:
                raw_assist = goal.assist
                normalized_raw_assist = normalize_name(raw_assist)
                if normalized_raw_assist in {"", "-", "e"}:
                    raw_assist = None
                else:
                    assist_name, assist_url = self.resolve_player_name(goal.assist, goal.assist_profile_url)
                    try:
                        assist_id = self.db.get_or_create_player(assist_name, assist_url)
                    except ValueError as exc:
                        self.logger.warning("Skipping invalid goal assist: %s (%s)", assist_name, exc)
                    else:
                        if normalize_name(raw_assist) != normalize_name(assist_name):
                            self.db.add_player_alias(assist_id, raw_assist)

            goals_batch.append(
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
                )
            )
        return goals_batch

    def _build_card_batch(
        self,
        match_id: int,
        home_team_id: int,
        away_team_id: int,
        cards: List[Dict[str, Optional[str]]],
    ) -> List[Tuple[int, int, Optional[int], Optional[int], Optional[int], str]]:
        cards_batch = []
        for card in cards:
            team_id = home_team_id if card["team_role"] == "home" else away_team_id
            try:
                player_id = self.db.get_or_create_player(card["player"], None)
            except ValueError as exc:
                self.logger.warning("Skipping invalid card player: %s (%s)", card["player"], exc)
                continue
            cards_batch.append(
                (
                    match_id,
                    team_id,
                    player_id,
                    card["minute"],
                    card["stoppage"],
                    card["card_type"],
                )
            )
        return cards_batch

    def _record_match_success(self) -> None:
        self.stats["matches_processed"] += 1
        self.stats["matches_successful"] += 1

    def _record_match_failure(self, detail_rel: str, exc: Exception) -> None:
        self.stats["matches_processed"] += 1
        self.stats["matches_failed"] += 1
        error_msg = f"Match {detail_rel}: {exc}"
        self.stats["errors"].append(error_msg)
        self.logger.error(error_msg, exc_info=True)

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

    # ---------------------------------------------------------------- profirest (multi-match) file parsing
    def _iter_following_tags_until(self, start_tag, names, stop_when):
        for tag in start_tag.find_all_next(names):
            if stop_when(tag):
                break
            yield tag

    def parse_profirest_match_block(self, match_block, overview_info: Dict[str, Optional[str]]):
        """
        Parse a single match from a profirest file.

        Profirest files have a simplified structure:
        - <table width="100%" height="45%"> contains one complete match
        - Date is in an <a> tag, score is in a <b> tag
        - Lineup is inline (no separate team blocks)
        - May or may not have full lineup data
        """
        # Get full match block text for parsing
        block_text = normalize_whitespace(match_block.get_text(" ", strip=True))

        # Extract score from <b> tag
        header = match_block.find("b")
        if not header:
            return None  # No match data

        header_text = normalize_whitespace(header.get_text(" ", strip=True))

        # Parse date from full block text - format: "SA. 20.07.1963" or "SO. 28.07.1963"
        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', block_text)
        if not date_match:
            # Try alternative format: "ca. Oktober 1945"
            date_match = re.search(r'ca\.\s+(\w+)\s+(\d{4})', block_text)  # Fixed: search in block_text not header_text
            if date_match:
                month_name = date_match.group(1)
                year = date_match.group(2)
                # Map German month names to numbers
                month_map = {
                    'Januar': '01', 'Februar': '02', 'März': '03', 'April': '04',
                    'Mai': '05', 'Juni': '06', 'Juli': '07', 'August': '08',
                    'September': '09', 'Oktober': '10', 'November': '11', 'Dezember': '12'
                }
                month_num = month_map.get(month_name, '01')
                date_iso = f"{year}-{month_num}-01"  # Use first day of month for approximate dates
            else:
                date_iso = None  # Accept missing dates in friendlies
        else:
            # Convert DD.MM.YYYY to YYYY-MM-DD
            date_parts = date_match.group(1).split('.')
            date_iso = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"

        # Parse score - format: "team1 - team2 X:Y (A:B)"
        score_pattern = r"(.+?)\s-\s(.+?)\s(\d+):(\d+)(?:\s\((\d+):(\d+)\))?"
        score_match = re.search(score_pattern, header_text)
        if not score_match:
            return None  # Can't parse score

        home_team = self._clean_team_name(score_match.group(1).strip())
        away_team = self._clean_team_name(score_match.group(2).strip())
        home_goals = int(score_match.group(3))
        away_goals = int(score_match.group(4))
        half_home = int(score_match.group(5)) if score_match.group(5) else None
        half_away = int(score_match.group(6)) if score_match.group(6) else None

        metadata = MatchMetadata(
            home_team=home_team,
            away_team=away_team,
            home_goals=home_goals,
            away_goals=away_goals,
            half_home=half_home,
            half_away=half_away,
            date=date_iso,
            kickoff=None,
            attendance=None,
            referee=None,
            referee_link=None,
            home_coach=None,
            home_coach_link=None,
            away_coach=None,
            away_coach_link=None,
            matchday=None,
            round_name=overview_info.get("stage"),
        )

        # Try to parse lineup - may not exist for all matches
        mainz_is_home = "FSV" in home_team or "Mainz" in home_team

        # Look for player links in the match block
        player_links = match_block.find_all("a", href=re.compile(r"spieler/.*\.html"))

        if not player_links:
            # No lineup data - return minimal match metadata
            return {
                'metadata': metadata,
                'lineups': {'home': {}, 'away': {}},
                'substitutions': [],
                'goals': [],
                'cards': []
            }

        # Parse lineup from inline format
        # In profirest files, all players are shown inline in tables
        # We need to distinguish which team they belong to based on position in the HTML
        roster: Dict[str, PlayerAppearance] = {}

        for link in player_links:
            player_name = normalize_whitespace(link.get_text(" ", strip=True))
            profile_url = link.get("href", "").replace("../", "")

            # Check if this is in a substitution table (contains "für")
            parent_text = link.parent.get_text(" ", strip=True) if link.parent else ""
            is_sub = "für" in parent_text or "f&uuml;r" in str(link.parent)

            # Skip goal scorers in "Tor"/"Tore" sections
            if "Tor" in parent_text or "<b>Tor" in str(link.parent.parent):
                continue

            appearance = PlayerAppearance(
                name=player_name,
                shirt_number=None,  # Not available in profirest files
                is_starter=not is_sub,
                profile_url=profile_url,
                minute_on=None,
                stoppage_on=None,
                minute_off=None,
                stoppage_off=None,
                card_events=[]
            )

            roster[player_name] = appearance

        # Since we can't distinguish home/away in the simplified format,
        # assign all players to Mainz team (this is a limitation)
        if mainz_is_home:
            lineups = {'home': roster, 'away': {}}
        else:
            lineups = {'home': {}, 'away': roster}

        next_match_header_pattern = re.compile(r".+?\s-\s.+?\s\d+:\d+")

        # Try to parse goals from "Tore" section
        goals = []
        tore_section = match_block.find("b", string=re.compile(r"Tor(e)?"))
        if tore_section:
            goal_cells = self._iter_following_tags_until(
                tore_section,
                ["td", "b"],
                lambda tag: tag.name == "b"
                and tag is not tore_section
                and bool(next_match_header_pattern.search(normalize_whitespace(tag.get_text(" ", strip=True)))),
            )
            current_home = 0
            for cell in goal_cells:
                if cell.name != "td":
                    continue
                goal_text = normalize_whitespace(cell.get_text(" ", strip=True))
                # Format: "10. 0:1 Fuchs" or "82. 1:0 Bader (Storck)"
                goal_match = re.match(r'(\d+)\.\s+(\d+):(\d+)\s+(.+)', goal_text)
                if not goal_match:
                    continue

                minute = int(goal_match.group(1))
                score_home = int(goal_match.group(2))
                score_away = int(goal_match.group(3))
                scorer = goal_match.group(4).strip()

                # Determine which team scored by comparing with previous score
                team_role = 'home' if score_home > current_home else 'away'
                current_home = score_home

                # Extract assist if present
                assist_match = re.search(r'\((.+?)\)', scorer)
                assist = self._clean_goal_participant_text(assist_match.group(1)) if assist_match else None
                scorer = re.sub(r'\s*\(.+?\)', '', scorer).strip()

                goals.append(GoalEvent(
                    minute=minute,
                    stoppage=None,
                    score_home=score_home,
                    score_away=score_away,
                    scorer=scorer,
                    assist=assist,
                    team_role=team_role,
                    is_penalty=False,
                    is_own_goal=False
                ))

        # Try to parse substitutions
        substitutions = []
        if tore_section:
            substitution_cells = self._iter_following_tags_until(
                header,
                ["td", "b"],
                lambda tag: tag is tore_section,
            )
        else:
            substitution_cells = match_block.find_all("td")
        for cell in substitution_cells:
            if cell.name != "td":
                continue
            cell_text = normalize_whitespace(cell.get_text(" ", strip=True))
            if " für " not in cell_text and " fÃ¼r " not in cell_text:
                continue

            minute_match = re.match(r'(\d+)\.', cell_text)
            links = cell.find_all("a", href=re.compile(r"spieler/.*\.html"))
            if not minute_match or len(links) < 2:
                continue

            substitutions.append({
                'minute': int(minute_match.group(1)),
                'stoppage': None,  # Not available in profirest format
                'player_on': normalize_whitespace(links[0].get_text(" ", strip=True)),
                'player_off': normalize_whitespace(links[1].get_text(" ", strip=True)),
                'team_role': 'home' if mainz_is_home else 'away',
                'player_on_link': links[0].get("href", "").replace("../", ""),
                'player_off_link': links[1].get("href", "").replace("../", ""),
            })

        return {
            'metadata': metadata,
            'lineups': lineups,
            'substitutions': substitutions,
            'goals': goals,
            'cards': []
        }

    def parse_profirest_file(self, match_blocks, overview_info: Dict[str, Optional[str]], detail_path: Path):
        """
        Parse a profirest*.html file containing multiple matches.
        Returns data for the first parseable match (for compatibility with existing code).

        Note: This is a simplified approach - ideally we would process all matches,
        but that would require changing the caller's logic. For now, we extract
        the first match to at least capture something from these files.
        """
        for idx, block in enumerate(match_blocks):
            match_data = self.parse_profirest_match_block(block, overview_info)
            if match_data:
                self.logger.debug("Parsed match %d/%d from %s", idx + 1, len(match_blocks), detail_path.name)
                # Return in the format expected by parse_match_detail
                return (
                    match_data['metadata'],
                    match_data['lineups'],
                    match_data['substitutions'],
                    match_data['goals'],
                    match_data['cards']
                )

        # No parseable matches found
        raise ValueError(f"No parseable matches in {detail_path}")

    # ---------------------------------------------------------------- detail parsing
    def _extract_profirest_side_by_side_blocks(self, soup: BeautifulSoup) -> List[BeautifulSoup]:
        """
        Some profirest files show multiple matches side-by-side in a single wide table
        (e.g., 1982-83/profirest01.html). We pick each <td> that contains a score line.
        """
        blocks: List[BeautifulSoup] = []
        # Look for wide tables (width ~100% or 50%) that contain multiple td columns
        for table in soup.find_all("table", attrs={"width": re.compile(r"^(100%|50%)")}):
            candidate_blocks = []
            for td in table.find_all("td"):
                header = td.find("b")
                if not header:
                    continue
                header_text = normalize_whitespace(header.get_text(" ", strip=True))
                if re.search(r"\d+:\d+", header_text) and ("FSV" in header_text or "Mainz" in header_text):
                    candidate_blocks.append(td)
            if len(candidate_blocks) >= 2:
                blocks.extend(candidate_blocks)
                break  # first matching table is enough
        return blocks

    def _try_parse_profirest_detail(
        self,
        soup: BeautifulSoup,
        overview_info: Dict[str, Optional[str]],
        detail_path: Path,
    ):
        match_blocks = soup.find_all("table", attrs={"width": "100%", "height": "45%"})
        if len(match_blocks) >= 2:
            self.logger.debug("Detected multi-match file with %d matches: %s", len(match_blocks), detail_path.name)
            return self.parse_profirest_file(match_blocks, overview_info, detail_path)

        alt_blocks = self._extract_profirest_side_by_side_blocks(soup)
        if len(alt_blocks) >= 2:
            self.logger.debug(
                "Detected side-by-side profirest layout with %d matches: %s",
                len(alt_blocks),
                detail_path.name,
            )
            return self.parse_profirest_file(alt_blocks, overview_info, detail_path)

        return None

    def _build_detail_metadata(
        self,
        soup: BeautifulSoup,
        overview_info: Dict[str, Optional[str]],
    ) -> MatchMetadata:
        header = soup.find("b")
        header_text = normalize_whitespace(header.get_text(" ", strip=True)) if header else ""
        home_team, away_team, score_home, score_away, half_home, half_away = self.parse_header_score(header_text)
        detail_info = self.extract_match_details(soup)
        mainz_is_home = "FSV" in home_team or "Mainz" in home_team
        matchday = overview_info.get("matchday")

        return MatchMetadata(
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
            home_coach=detail_info.get("mainz_coach") if mainz_is_home else detail_info.get("opponent_coach"),
            home_coach_link=detail_info.get("mainz_coach_link") if mainz_is_home else detail_info.get("opponent_coach_link"),
            away_coach=detail_info.get("opponent_coach") if mainz_is_home else detail_info.get("mainz_coach"),
            away_coach_link=detail_info.get("opponent_coach_link") if mainz_is_home else detail_info.get("mainz_coach_link"),
            matchday=int(matchday) if isinstance(matchday, int) or (isinstance(matchday, str) and matchday.isdigit()) else None,
            round_name=overview_info.get("stage"),
        )

    def _find_standard_team_blocks(self, soup: BeautifulSoup) -> List[BeautifulSoup]:
        for height in ("30%", "28%", "27%"):
            team_blocks = soup.find_all("table", attrs={"width": "100%", "height": height})
            if len(team_blocks) >= 2:
                return team_blocks[:2]

        all_tables = soup.find_all("table")
        reserve_indices = [idx for idx, table in enumerate(all_tables) if "Reserve" in table.get_text(" ", strip=True)]
        if len(reserve_indices) >= 2:
            return [all_tables[reserve_indices[0]], all_tables[reserve_indices[1]]]
        return []

    def _collect_stacked_layout_players(self, blocks: List[BeautifulSoup]) -> Dict[str, PlayerAppearance]:
        players: Dict[str, PlayerAppearance] = {}
        for block in blocks:
            for cell in block.find_all("td"):
                anchor = cell.find("a", href=re.compile(r"spieler/"))
                if not anchor:
                    continue
                name = normalize_whitespace(anchor.get_text(" ", strip=True))
                if not name:
                    continue
                profile_url = anchor.get("href", "").replace("../", "")
                table = cell.find_parent("table")
                table_text = normalize_whitespace(table.get_text(" ", strip=True)) if table else ""
                is_reserve = "reserve" in table_text.lower()
                if name not in players:
                    players[name] = PlayerAppearance(
                        name=name,
                        shirt_number=None,
                        is_starter=not is_reserve,
                        profile_url=profile_url,
                    )
                    continue
                if profile_url and not players[name].profile_url:
                    players[name].profile_url = profile_url
                if is_reserve:
                    players[name].is_starter = False
        return players

    def _parse_stacked_table_layout(
        self,
        soup: BeautifulSoup,
        metadata: MatchMetadata,
        detail_path: Path,
    ):
        all_tables = soup.find_all("table")
        if len(all_tables) < 2:
            raise ValueError(f"Unexpected match layout in {detail_path}")

        midpoint = len(all_tables) // 2
        home_players = self._collect_stacked_layout_players(all_tables[:midpoint])
        away_players = self._collect_stacked_layout_players(all_tables[midpoint:])
        goals = self.parse_goal_table(soup, metadata)
        cards = self.gather_card_events(home_players, "home") + self.gather_card_events(away_players, "away")
        return metadata, {"home": home_players, "away": away_players}, [], goals, cards

    def _parse_standard_team_layout(
        self,
        soup: BeautifulSoup,
        metadata: MatchMetadata,
        team_blocks: List[BeautifulSoup],
    ):
        home_lineups = self.parse_team_block(team_blocks[0])
        away_lineups = self.parse_team_block(team_blocks[1])
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

        return metadata, {"home": home_players, "away": away_players}, home_subs + away_subs, goals, cards

    def parse_match_detail(self, detail_path: Path, overview_info: Dict[str, Optional[str]], season_path: Path):
        soup = read_html(detail_path)
        if soup is None:
            raise FileNotFoundError(detail_path)

        profirest_result = self._try_parse_profirest_detail(soup, overview_info, detail_path)
        if profirest_result is not None:
            return profirest_result

        metadata = self._build_detail_metadata(soup, overview_info)
        team_blocks = self._find_standard_team_blocks(soup)
        if team_blocks:
            return self._parse_standard_team_layout(soup, metadata, team_blocks)
        return self._parse_stacked_table_layout(soup, metadata, detail_path)

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
            # Update position group headings
            for bold in cell.find_all("b"):
                label = normalize_whitespace(bold.get_text(" ", strip=True)).upper()
                if label in {"TOR", "ABWEHR", "MITTELFELD", "ANGRIFF", "SPIELAUFBAU"}:
                    position_group = label

            for anchor in cell.find_all("a", href=re.compile(r"spieler/")):
                name = normalize_whitespace(anchor.get_text(" ", strip=True))
                profile_url = anchor.get("href", "").replace("../", "") if anchor.get("href") else None

                # Extract shirt number from surrounding line (e.g., "1 Lasse Finn Rieß")
                line_text = normalize_whitespace(anchor.parent.get_text(" ", strip=True))
                shirt_number = None
                m = re.match(r"^(\d+)\s+", line_text)
                if m:
                    shirt_number = int(m.group(1))

                if not name or not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", name):
                    continue
                # If no position_group seen yet (e.g., photo captions), tag as "UNSPECIFIED"
                effective_group = position_group or "UNSPECIFIED"

                try:
                    player_id = self.db.get_or_create_player(name, profile_url)
                except ValueError as e:
                    self.logger.warning("Skipping invalid squad player: %s (%s)", name, e)
                    continue
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO season_squads
                    (season_competition_id, player_id, position_group, shirt_number, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (season_competition_id, player_id, effective_group, shirt_number, "primary"),
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
        self.logger.info("Starting archive parse from %s → %s", self.source_label, self.db.db_path)
        try:
            for season in self.iter_seasons():
                self.db.current_season = season
                self.parse_season(season)

            self.db.current_season = None

            self.logger.info("Enriching player profiles from spieler/ directory...")
            self.enrich_all_player_profiles()

            self.logger.info("Enriching coach profiles from trainer/ directory...")
            self.enrich_all_coach_profiles()

            self.logger.info("All seasons processed. Closing database connection.")
            self.print_statistics()
        finally:
            self.db.close()
            self.prepared_source.cleanup()
    
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
        
        # Per-season player creation stats (URL vs no URL)
        if self.db.player_creation_stats:
            self.logger.info("\nPlayer creations per season (with_url / without_url):")
            for season in sorted(self.db.player_creation_stats.keys()):
                stats = self.db.player_creation_stats[season]
                self.logger.info(f"  {season}: {stats['with_url']} with URL, {stats['without_url']} without URL")
        self.logger.info("=" * 80)
    
def main():
    import argparse

    arg_parser = argparse.ArgumentParser(description="Parse FSV Mainz 05 archive HTML files into database")
    arg_parser.add_argument(
        "--source",
        help="Archive source: local folder with HTML files or website URL to mirror before parsing",
    )
    arg_parser.add_argument("--seasons", nargs="+", help="Specific seasons to parse (e.g., 2009-10 2010-11)")
    arg_parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = arg_parser.parse_args()

    if not logging.getLogger().handlers:
        log_level = logging.DEBUG if args.verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

    seasons = args.seasons if args.seasons else None
    parser = ComprehensiveFSVParser(source=args.source, seasons=seasons)
    parser.run()


if __name__ == "__main__":
    main()
