import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from parsing.html_utils import normalize_name, normalize_whitespace, parse_int, parse_minute
from parsing.match_types import GoalEvent, MatchMetadata, PlayerAppearance

CARD_ICON_MAP = {
    "../gelbekarte.bmp": "yellow",
    "../gelbrot.bmp": "second_yellow",
    "../rotekarte.bmp": "red",
}


class MatchParsingMixin:
    def _clean_goal_participant_text(self, text: str) -> Optional[str]:
        cleaned = normalize_whitespace(text)
        cleaned = re.sub(r'^wdh\.\s*', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(
            r'^(FE|ET|HE|E|Elfmeter|ind\.?\s*FS|ind\.?\s*Freisto[ßs])\s*,\s*',
            '',
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        cleaned = re.sub(
            r'^(FE|Elfmeter)\s+im\s+Nachschu(?:ss|ß)\s*,\s*',
            '',
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        if " an " in cleaned.lower():
            cleaned = re.split(r'\s+an\s+', cleaned, flags=re.IGNORECASE)[-1].strip()
        cleaned = re.sub(
            r'\s*,\s*im\s+Nachschu(?:ss|ß).*$',
            '',
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        cleaned = re.sub(
            r'\s*,\s*.*hatte\s+gehalten.*$',
            '',
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        cleaned = re.sub(r'\s*,\s*s\.u\.\s*$', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'^\s*s\.u\.\s*,\s*', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'\s*,\s*im\s+Nachschu(?:ss|ß)\s*$', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = cleaned.strip(" ,")
        if cleaned in {"", "-", "s.u.", "s u"}:
            return None
        return cleaned

    def parse_header_score(self, text: str) -> Tuple[str, str, int, int, Optional[int], Optional[int]]:
        score_pattern = r"(.+?)\s-\s(.+?)\s([-\d]+):([-\d]+)(?:\s\(([-\d]+):([-\d]+)\))?"
        match = re.search(score_pattern, text)
        if not match:
            raise ValueError(f"Cannot parse match header: {text}")

        def parse_score(value: Optional[str]) -> Optional[int]:
            if value is None or value == "-":
                return None
            return int(value)

        return (
            normalize_whitespace(match.group(1)),
            normalize_whitespace(match.group(2)),
            parse_score(match.group(3)),
            parse_score(match.group(4)),
            parse_score(match.group(5) if match.lastindex and match.lastindex >= 5 else None),
            parse_score(match.group(6) if match.lastindex and match.lastindex >= 6 else None),
        )

    def extract_match_details(self, soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        date = None
        kickoff = None
        attendance = None
        referee = None
        referee_link = None
        mainz_coach = None
        mainz_coach_link = None
        opponent_coach = None
        opponent_coach_link = None

        header_line = soup.find(string=re.compile(r"Zuschauer", re.IGNORECASE))
        if header_line:
            container_text = header_line.parent.get_text(" ", strip=True) if header_line.parent else header_line
            parts = [part.strip() for part in normalize_whitespace(container_text).replace(" Uhr", "").split(",")]
            if parts:
                date_parts = parts[0].split()
                if date_parts:
                    date_candidate = date_parts[-1]
                    if re.match(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', date_candidate):
                        try:
                            date = datetime.strptime(date_candidate, "%d.%m.%Y").strftime("%Y-%m-%d")
                        except ValueError as exc:
                            self.logger.debug("Skipping invalid match date %r: %s", date_candidate, exc)
            for index, part in enumerate(parts[1:], 1):
                part_lower = part.lower()
                if "zuschauer" in part_lower or "zuschau" in part_lower:
                    attendance_text = part.replace("Zuschauer.", "").replace("Zuschauer", "").strip()
                    if not attendance_text.startswith("keine") and not attendance_text.startswith("no"):
                        attendance = parse_int(attendance_text.split()[0] if attendance_text else "")
                elif index == 1 and "zuschauer" not in part_lower:
                    kickoff = part

        coach_table = soup.find("b", string=re.compile("Schiedsrichter", re.IGNORECASE))
        if coach_table:
            container = coach_table.find_parent("table")
            if container:
                for cell in container.find_all("td"):
                    text = normalize_whitespace(cell.get_text(" ", strip=True))
                    link = cell.find("a")
                    if "FSV-Trainer" in text:
                        mainz_coach = text.split(":")[-1].strip()
                        mainz_coach_link = link["href"] if link else None
                    elif "Trainer" in text:
                        opponent_coach = text.split(":")[-1].strip()
                        opponent_coach_link = link["href"] if link else None
                    if "Schiedsrichter" in text:
                        referee = text.replace("Schiedsrichter:", "").strip()
                        referee_link = link["href"] if link else None

        return {
            "date": date,
            "kickoff": kickoff,
            "attendance": attendance,
            "referee": referee,
            "referee_link": referee_link,
            "mainz_coach": mainz_coach,
            "mainz_coach_link": mainz_coach_link,
            "opponent_coach": opponent_coach,
            "opponent_coach_link": opponent_coach_link,
        }

    def parse_team_block(self, block: BeautifulSoup) -> Dict[str, Dict]:
        players: Dict[str, PlayerAppearance] = {}
        substitutions: List[Dict[str, Optional[str]]] = []
        for table in block.find_all("table"):
            table_text = normalize_whitespace(table.get_text(" ", strip=True))
            table_text_lower = table_text.lower()
            if any(
                marker in table_text_lower
                for marker in (
                    "trainer:",
                    "fsv-trainer",
                    "schiedsrichter:",
                    "schiedsrichterin:",
                    "referee:",
                    "übersicht",
                    "zurückblättern",
                    "weiterblättern",
                )
            ) or table_text_lower == "tore" or table_text_lower.startswith("tore "):
                break
            table_is_reserve = table_text.lower().startswith("reserve")
            for cell in table.find_all("td"):
                if cell.find("table") is not None:
                    # Old archive pages often wrap a full team block in one outer td.
                    # Its text collapses the entire lineup into one fake player name.
                    continue
                text = normalize_whitespace(cell.get_text(" ", strip=True))
                if not text or text.lower().startswith("reserve"):
                    continue
                text_lower = text.lower()
                if any(pattern in text_lower for pattern in ['trainer:', 'fsv-trainer', 'coach:', '-trainer', 'schiedsrichter:', 'schiedsrichterin:', 'referee:']):
                    continue
                if text_lower.startswith('tore ') or re.match(r'^\d+\.\s*\d+:\d+', text):
                    continue
                icons = [img.get("src") for img in cell.find_all("img")]
                if " für " in text:
                    substitution = self.parse_substitution_entry(cell, text, icons)
                    if substitution:
                        substitutions.append(substitution)
                    continue

                profile_url = None
                anchor = cell.find("a", href=re.compile(r"spieler/.*\.html"))
                if anchor and anchor.get("href"):
                    profile_url = anchor["href"].replace("../", "")

                number_match = re.match(r"^(\d+)\s+(.*)", text)
                shirt_number = int(number_match.group(1)) if number_match else None
                name = number_match.group(2).strip() if number_match else text
                if not name or len(name) < 2:
                    continue
                if name.lower().startswith("die aufstellung "):
                    continue
                if name.startswith('?'):
                    name = name[1:].strip()
                if not name or name == "-":
                    continue
                import unicodedata
                if name and not unicodedata.category(name[0]).startswith('L'):
                    continue

                if name not in players:
                    players[name] = PlayerAppearance(name=name, shirt_number=shirt_number, is_starter=not table_is_reserve, profile_url=profile_url)
                else:
                    existing = players[name]
                    if existing.shirt_number is None and shirt_number is not None:
                        existing.shirt_number = shirt_number
                    if table_is_reserve:
                        existing.is_starter = False
                    if profile_url and not existing.profile_url:
                        existing.profile_url = profile_url

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
        incoming_text = re.sub(r'^(FE|ET|HE),\s*', '', incoming_text, flags=re.IGNORECASE).strip()
        outgoing_text = re.sub(r'^(FE|ET|HE),\s*', '', outgoing_text, flags=re.IGNORECASE).strip()
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
        trailing_scorers: List[Tuple[str, Optional[str], Optional[str], Optional[str]]] = []
        last_score_home: Optional[int] = None
        last_score_away: Optional[int] = None
        for cell in goal_table.find_all("td"):
            text = normalize_whitespace(cell.get_text(" ", strip=True))
            if not text:
                continue
            if text.lower().startswith('tore ') and not re.search(r'\d+\.', text):
                continue
            minute, stoppage = parse_minute(text)
            remainder = re.sub(r"^\s*\d+(?:\+\d+)?\.\s*", "", text) if minute is not None else text
            score_match = re.match(r"(\d+):(\d+)\s+(.*)", remainder)
            if not score_match:
                if last_score_home is None or last_score_away is None:
                    continue
                scorer_name, assist, scorer_profile_url, assist_profile_url = self._parse_goal_scorer_details(cell, remainder)
                if not scorer_name:
                    continue
                trailing_scorers.append((scorer_name, assist, scorer_profile_url, assist_profile_url))
                continue
            score_home = int(score_match.group(1))
            score_away = int(score_match.group(2))
            scorer_name, assist, scorer_profile_url, assist_profile_url = self._parse_goal_scorer_details(
                cell,
                score_match.group(3),
            )
            if not scorer_name:
                continue

            home_scored = score_home > (goals[-1].score_home if goals else 0)
            goals.append(
                GoalEvent(
                    minute=minute,
                    stoppage=stoppage,
                    score_home=score_home,
                    score_away=score_away,
                    scorer=scorer_name,
                    assist=assist,
                    scorer_profile_url=scorer_profile_url,
                    assist_profile_url=assist_profile_url if assist else None,
                    team_role="home" if home_scored else "away",
                )
            )
            last_score_home = score_home
            last_score_away = score_away

        remaining_home = metadata.home_goals - (last_score_home or 0)
        remaining_away = metadata.away_goals - (last_score_away or 0)
        if trailing_scorers and ((remaining_home > 0) ^ (remaining_away > 0)):
            current_home = last_score_home or 0
            current_away = last_score_away or 0
            scoring_role = "home" if remaining_home > 0 else "away"
            expected_remaining = remaining_home if remaining_home > 0 else remaining_away
            if len(trailing_scorers) <= expected_remaining:
                for scorer_name, assist, scorer_profile_url, assist_profile_url in trailing_scorers:
                    if scoring_role == "home":
                        current_home += 1
                    else:
                        current_away += 1
                    goals.append(
                        GoalEvent(
                            minute=None,
                            stoppage=None,
                            score_home=current_home,
                            score_away=current_away,
                            scorer=scorer_name,
                            assist=assist,
                            scorer_profile_url=scorer_profile_url,
                            assist_profile_url=assist_profile_url,
                            team_role=scoring_role,
                        )
                    )
        return goals

    def _parse_goal_scorer_details(
        self,
        cell,
        scorer_info: str,
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        anchors = cell.find_all("a", href=re.compile(r"../spieler/"))
        scorer_profile_url = None
        assist_profile_url = None
        scorer_info = re.sub(r'^(FE|ET|HE),\s*', '', scorer_info, flags=re.IGNORECASE).strip()
        scorer_info = re.sub(r'^wdh\.\s*', '', scorer_info, flags=re.IGNORECASE).strip()

        assist = None
        if "(" in scorer_info and ")" in scorer_info:
            scorer_name, assist_part = scorer_info.split("(", 1)
            assist = self._clean_goal_participant_text(assist_part.strip(" )"))
            if assist and ' an ' in assist.lower():
                parts = re.split(r'\s+an\s+', assist, flags=re.IGNORECASE)
                if len(parts) > 1:
                    assist = parts[-1].strip()
            if assist == "-" or not assist:
                assist = None
        else:
            scorer_name = scorer_info
        scorer_name = scorer_name.strip()
        if ' ' in scorer_name and not re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', scorer_name):
            scorer_link = cell.find("a", href=re.compile(r"../spieler/"))
            if scorer_link:
                scorer_name = normalize_whitespace(scorer_link.get_text(" ", strip=True))
            else:
                parts = scorer_name.split()
                if len(parts) > 2:
                    scorer_name = parts[-1]
        if len(scorer_name) < 2:
            return None, None, None, None
        import unicodedata
        if scorer_name and not unicodedata.category(scorer_name[0]).startswith('L'):
            return None, None, None, None

        normalized_scorer = normalize_name(scorer_name)
        normalized_assist = normalize_name(assist) if assist else None
        for anchor in anchors:
            href = anchor.get("href", "").replace("../", "")
            anchor_text = normalize_whitespace(anchor.get_text(" ", strip=True))
            normalized_anchor = normalize_name(anchor_text)
            if normalized_anchor and normalized_anchor == normalized_scorer and scorer_profile_url is None:
                scorer_profile_url = href
                continue
            if normalized_assist and normalized_anchor == normalized_assist and assist_profile_url is None:
                assist_profile_url = href
        if anchors and scorer_profile_url is None and assist_profile_url is None:
            if assist:
                assist_profile_url = anchors[0].get("href", "").replace("../", "")
            else:
                scorer_profile_url = anchors[0].get("href", "").replace("../", "")
        return scorer_name, assist, scorer_profile_url, assist_profile_url

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
                player_on = PlayerAppearance(name=player_on_name, shirt_number=sub.get("player_on_number"), is_starter=False)
                players[player_on_name] = player_on
            else:
                if player_on.shirt_number is None and sub.get("player_on_number") is not None:
                    player_on.shirt_number = sub["player_on_number"]
                player_on.is_starter = False
            player_on.minute_on = sub["minute"]
            player_on.stoppage_on = sub["stoppage"]

            player_off = players.get(player_off_name)
            if not player_off:
                player_off = PlayerAppearance(name=player_off_name, shirt_number=sub.get("player_off_number"), is_starter=True)
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
