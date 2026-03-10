import logging
import tempfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from parsing.html_utils import read_html


@dataclass
class PreparedSource:
    local_root: Path
    display_source: str
    temp_dir: Optional[tempfile.TemporaryDirectory] = None

    def cleanup(self) -> None:
        if self.temp_dir is not None:
            self.temp_dir.cleanup()


def _is_remote_source(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _normalize_source_url(source: str) -> tuple[str, str]:
    parsed = urlparse(source)
    path = parsed.path or "/"
    if not path.endswith("/") and not Path(path).suffix:
        path = f"{path}/"
    normalized = parsed._replace(path=path, params="", query="", fragment="")
    scope_path = path if path.endswith("/") else f"{Path(path).parent.as_posix().rstrip('/')}/"
    return urlunparse(normalized), scope_path


def _is_crawlable_link(url: str, root_parts, scope_path: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc != root_parts.netloc:
        return False
    if not parsed.path.startswith(scope_path):
        return False
    if parsed.path.endswith("/"):
        return True
    suffix = Path(parsed.path).suffix.lower()
    return suffix in {"", ".html", ".htm"}


def _local_path_for_url(url: str, scope_path: str, local_root: Path) -> Path:
    parsed = urlparse(url)
    relative = parsed.path[len(scope_path):].lstrip("/") if parsed.path.startswith(scope_path) else parsed.path.lstrip("/")
    path = Path(relative) if relative else Path()
    if parsed.path.endswith("/") or not path.suffix:
        return local_root / path / "index.html"
    return local_root / path


def _extract_crawl_links(base_url: str, soup: BeautifulSoup) -> list[str]:
    links: list[str] = []
    for tag_name, attr_name in (("a", "href"), ("frame", "src"), ("iframe", "src")):
        for tag in soup.find_all(tag_name):
            href = tag.get(attr_name)
            if not href:
                continue
            if href.startswith(("javascript:", "mailto:", "#")):
                continue
            normalized, _ = urldefrag(urljoin(base_url, href))
            links.append(normalized)
    return links


def prepare_input_source(source: str) -> PreparedSource:
    if not _is_remote_source(source):
        local_root = Path(source).expanduser().resolve()
        if not local_root.exists():
            raise FileNotFoundError(f"Source path '{local_root}' does not exist")
        if not local_root.is_dir():
            raise NotADirectoryError(f"Source path '{local_root}' is not a directory")
        return PreparedSource(local_root=local_root, display_source=str(local_root))

    logger = logging.getLogger("SourcePreparer")
    root_url, scope_path = _normalize_source_url(source)
    root_parts = urlparse(root_url)
    temp_dir = tempfile.TemporaryDirectory(prefix="fsv_data_pipeline_source_")
    local_root = Path(temp_dir.name)

    queue: deque[str] = deque([root_url])
    visited: set[str] = set()
    downloaded = 0
    max_pages = 5000

    while queue and len(visited) < max_pages:
        current_url = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)

        request = Request(current_url, headers={"User-Agent": "fsv-data-pipeline/0.1"})
        try:
            with urlopen(request) as response:  # nosec B310 - source URLs are restricted to validated http/https inputs
                payload = response.read()
                content_type = response.headers.get("Content-Type", "")
        except Exception as exc:
            logger.warning("Failed to download %s: %s", current_url, exc)
            continue

        local_path = _local_path_for_url(current_url, scope_path, local_root)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(payload)
        downloaded += 1

        if "text/html" not in content_type and local_path.suffix.lower() not in {".html", ".htm"}:
            continue

        soup = read_html(local_path)
        if soup is None:
            continue

        for linked_url in _extract_crawl_links(current_url, soup):
            if linked_url not in visited and _is_crawlable_link(linked_url, root_parts, scope_path):
                queue.append(linked_url)

    logger.info("Mirrored %d page(s) from %s into %s", downloaded, root_url, local_root)
    return PreparedSource(local_root=local_root, display_source=root_url, temp_dir=temp_dir)
