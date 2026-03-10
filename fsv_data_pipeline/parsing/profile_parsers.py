import logging
import re
import unicodedata
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Optional

from parsing.html_utils import normalize_whitespace, read_html

logger = logging.getLogger(__name__)


def decode_html_entities(text: str) -> str:
    return unescape(text) if text else text


def strip_accents(text: str) -> str:
    return ''.join(
        char for char in unicodedata.normalize('NFKD', text)
        if not unicodedata.combining(char)
    )


def normalize_name(name: str) -> str:
    normalized = strip_accents(name)
    normalized = re.sub(r'[^a-zA-Z0-9\s]', '', normalized)
    return normalized.lower().strip()


@dataclass
class PlayerProfile:
    filename: str
    name: str
    normalized_name: str
    birth_date: Optional[str] = None
    birth_place: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    position: Optional[str] = None
    nationality: Optional[str] = None
    image_url: Optional[str] = None


@dataclass
class CoachProfile:
    filename: str
    name: str
    normalized_name: str
    birth_date: Optional[str] = None
    birth_place: Optional[str] = None
    predecessor: Optional[str] = None
    successor: Optional[str] = None


@dataclass
class TeamProfile:
    filename: str
    name: str
    normalized_name: str
    aliases: list | None = None

    def __post_init__(self) -> None:
        if self.aliases is None:
            self.aliases = []


class PlayerProfileParser:
    """Parse player profiles from spieler/ directory."""

    BIRTH_PATTERN = re.compile(
        r'\*\s*(?:<a[^>]*>)?(\d{1,2}\.\d{1,2}\.\d{4})(?:</a>)?\s*(?:in\s+([^,.\d]+))?'
        r'(?:[,.\s]*(\d{2,3})\s*cm)?'
        r'(?:[,.\s]*(\d{2,3})\s*kg)?',
        re.IGNORECASE,
    )

    def parse(self, filepath: Path) -> Optional[PlayerProfile]:
        soup = read_html(filepath)
        if not soup:
            return None

        name = None
        for b_tag in soup.find_all('b'):
            text = normalize_whitespace(b_tag.get_text())
            if text and not text.endswith(':') and len(text) > 2 and any(c.isalpha() for c in text):
                name = decode_html_entities(text)
                break

        if not name:
            logger.warning("No name found in %s", filepath)
            return None

        text_content = soup.get_text()
        birth_date = None
        birth_place = None
        height_cm = None
        weight_kg = None

        match = self.BIRTH_PATTERN.search(text_content)
        if match:
            birth_date = match.group(1)
            if match.group(2):
                birth_place = normalize_whitespace(match.group(2).strip(' ,.'))
            if match.group(3):
                try:
                    height_cm = int(match.group(3))
                except ValueError as exc:
                    logger.debug("Ignoring invalid height in %s: %s", filepath, exc)
            if match.group(4):
                try:
                    weight_kg = int(match.group(4))
                except ValueError as exc:
                    logger.debug("Ignoring invalid weight in %s: %s", filepath, exc)

        position = None
        for pattern in [
            r'<b>Position(?:en)?:</b>\s*(?:<br\s*/?>\s*)+([^<]+)',
            r'Position(?:en)?:\s*</b>\s*<br>\s*([^<]+)',
            r'<b>Position(?:en)?:</b>\s*([^<]+)',
        ]:
            pos_match = re.search(pattern, str(soup), re.IGNORECASE | re.DOTALL)
            if pos_match:
                pos_text = normalize_whitespace(pos_match.group(1).strip())
                if pos_text and not pos_text.startswith('<') and len(pos_text) > 1:
                    position = pos_text
                    break

        nationality = None
        nat_match = re.search(r'Nationalität:\s*([^<\n]+)', text_content, re.IGNORECASE)
        if nat_match:
            nationality = normalize_whitespace(nat_match.group(1).strip())

        image_url = None
        img = soup.find('img')
        if img and img.get('src'):
            image_url = img['src']

        return PlayerProfile(
            filename=filepath.name,
            name=name,
            normalized_name=normalize_name(name),
            birth_date=birth_date,
            birth_place=birth_place,
            height_cm=height_cm,
            weight_kg=weight_kg,
            position=position,
            nationality=nationality,
            image_url=image_url,
        )


class CoachProfileParser:
    """Parse coach profiles from trainer/ directory."""

    BIRTH_PATTERN = re.compile(
        r'\*\s*(?:<a[^>]*>)?(\d{1,2}\.\d{1,2}\.\d{4})(?:</a>)?\s*(?:in\s+([^,.<]+))?',
        re.IGNORECASE,
    )

    def parse(self, filepath: Path) -> Optional[CoachProfile]:
        soup = read_html(filepath)
        if not soup:
            return None

        name = None
        for b_tag in soup.find_all('b'):
            text = normalize_whitespace(b_tag.get_text())
            if text and not text.endswith(':') and len(text) > 2 and any(c.isalpha() for c in text):
                name = decode_html_entities(text)
                break

        if not name:
            logger.warning("No name found in %s", filepath)
            return None

        text_content = soup.get_text()
        birth_date = None
        birth_place = None

        match = self.BIRTH_PATTERN.search(text_content)
        if match:
            birth_date = match.group(1)
            if match.group(2):
                birth_place = normalize_whitespace(match.group(2).strip(' ,.'))

        predecessor = None
        successor = None

        pred_match = re.search(r'Vorgänger:\s*<a[^>]*>([^<]+)</a>', str(soup), re.IGNORECASE)
        if pred_match:
            predecessor = decode_html_entities(normalize_whitespace(pred_match.group(1)))

        succ_match = re.search(r'Nachfolger:\s*<a[^>]*>([^<]+)</a>', str(soup), re.IGNORECASE)
        if succ_match:
            successor = decode_html_entities(normalize_whitespace(succ_match.group(1)))

        return CoachProfile(
            filename=filepath.name,
            name=name,
            normalized_name=normalize_name(name),
            birth_date=birth_date,
            birth_place=birth_place,
            predecessor=predecessor,
            successor=successor,
        )


class TeamProfileParser:
    """Parse team profiles from gegner/ directory."""

    def parse(self, filepath: Path) -> Optional[TeamProfile]:
        soup = read_html(filepath)
        if not soup:
            return None

        name = None
        for b_tag in soup.find_all('b'):
            text = normalize_whitespace(b_tag.get_text())
            if text and not text.endswith(':') and len(text) > 2 and any(c.isalpha() for c in text):
                name = decode_html_entities(text)
                break

        if not name:
            logger.warning("No name found in %s", filepath)
            return None

        aliases = []
        for b_tag in soup.find_all('b'):
            text = normalize_whitespace(b_tag.get_text())
            if text and text != name and len(text) > 2:
                text_normalized = normalize_name(text)
                if (
                    text_normalized not in ['heimbilanz', 'auswartsbilanz', 'gesamtbilanz',
                                            'bei beiden vereinen tatig', 'saison', 'alle spiele',
                                            'name', 'fsv', 'fcb', 'u19', 'u17']
                    and any(c.isalpha() for c in text)
                    and not text.endswith(':')
                    and ('II' in text or 'U19' in text or 'U17' in text)
                ):
                    aliases.append(decode_html_entities(text))

        return TeamProfile(
            filename=filepath.name,
            name=name,
            normalized_name=normalize_name(name),
            aliases=aliases,
        )
