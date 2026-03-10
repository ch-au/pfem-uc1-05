import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional, Tuple

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
    logger = logging.getLogger("HTMLLoader")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return None

    for enc in ("utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            return BeautifulSoup(text, "lxml")
        except UnicodeDecodeError as exc:
            logger.debug("Failed to decode %s with %s: %s", path, enc, exc)
            continue

    text = raw.decode("latin-1", errors="ignore")
    logger.debug("Decoded %s with latin-1 (ignore errors) after utf-8 fallback", path)
    return BeautifulSoup(text, "lxml")
