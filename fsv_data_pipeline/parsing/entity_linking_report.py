#!/usr/bin/env python3
"""Generate quality reports on entity linking between parsed match data and canonical profile indices."""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from parsing.entity_linking_report_renderer import (
    build_report_payload,
    print_report_summary,
    save_report_file,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_INDICES_DIR = "generated/indices"
DEFAULT_REPORTS_DIR = "generated/reports"


class EntityLinkingReporter:
    """Generate entity linking quality reports."""

    def __init__(
        self,
        db_path: str = "fsv_archive_complete.db",
        indices_dir: str = DEFAULT_INDICES_DIR,
        output_dir: str = DEFAULT_REPORTS_DIR,
    ):
        self.db_path = Path(db_path)
        self.indices_dir = Path(indices_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.players_index: Dict[str, Dict[str, Any]] = {}
        self.coaches_index: Dict[str, Dict[str, Any]] = {}
        self.teams_index: Dict[str, Dict[str, Any]] = {}
        self.player_names: Set[str] = set()
        self.coach_names: Set[str] = set()
        self.team_names: Set[str] = set()

        self._load_indices()

    def _load_index(self, filename: str) -> Dict[str, Dict[str, Any]]:
        index_path = self.indices_dir / filename
        if not index_path.exists():
            return {}
        with open(index_path, 'r', encoding='utf-8') as file_obj:
            return json.load(file_obj)

    def _load_indices(self) -> None:
        self.players_index = self._load_index("players.json")
        self.coaches_index = self._load_index("coaches.json")
        self.teams_index = self._load_index("teams.json")
        self.player_names = {data.get('normalized_name', '') for data in self.players_index.values()}
        self.coach_names = {data.get('normalized_name', '') for data in self.coaches_index.values()}
        self.team_names = {data.get('normalized_name', '') for data in self.teams_index.values()}
        logger.info("Loaded %d player profiles", len(self.players_index))
        logger.info("Loaded %d coach profiles", len(self.coaches_index))
        logger.info("Loaded %d team profiles", len(self.teams_index))

    def _get_db_connection(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        return sqlite3.connect(self.db_path)

    def _fetch_rows(self, query: str) -> list[tuple]:
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()
        finally:
            conn.close()

    def analyze_players(self) -> Dict[str, Any]:
        rows = self._fetch_rows(
            """
            SELECT player_id, name, normalized_name, profile_url
            FROM players
            """
        )

        linked_to_profile = []
        no_profile_match = []
        has_full_name = []
        surname_only = []

        for player_id, name, normalized_name, profile_url in rows:
            player_info = {
                'player_id': player_id,
                'name': name,
                'normalized_name': normalized_name,
                'profile_url': profile_url,
            }
            if (profile_url and profile_url.strip()) or normalized_name in self.player_names:
                linked_to_profile.append(player_info)
            else:
                no_profile_match.append(player_info)

            if ' ' in (name or ''):
                has_full_name.append(player_info)
            else:
                surname_only.append(player_info)

        total = len(rows)
        return {
            'total': total,
            'linked_to_profile': len(linked_to_profile),
            'no_profile_match': len(no_profile_match),
            'has_full_name': len(has_full_name),
            'surname_only': len(surname_only),
            'link_rate_percent': round(len(linked_to_profile) / total * 100, 2) if total > 0 else 0,
            'full_name_rate_percent': round(len(has_full_name) / total * 100, 2) if total > 0 else 0,
            'unlinked_sample': no_profile_match[:50],
        }

    def analyze_coaches(self) -> Dict[str, Any]:
        rows = self._fetch_rows(
            """
            SELECT coach_id, name, normalized_name, profile_url
            FROM coaches
            """
        )

        linked_to_profile = []
        no_profile_match = []
        has_full_name = []

        for coach_id, name, normalized_name, profile_url in rows:
            coach_info = {
                'coach_id': coach_id,
                'name': name,
                'normalized_name': normalized_name,
                'profile_url': profile_url,
            }
            if (profile_url and profile_url.strip()) or normalized_name in self.coach_names:
                linked_to_profile.append(coach_info)
            else:
                no_profile_match.append(coach_info)
            if ' ' in (name or ''):
                has_full_name.append(coach_info)

        total = len(rows)
        return {
            'total': total,
            'linked_to_profile': len(linked_to_profile),
            'no_profile_match': len(no_profile_match),
            'has_full_name': len(has_full_name),
            'link_rate_percent': round(len(linked_to_profile) / total * 100, 2) if total > 0 else 0,
            'full_name_rate_percent': round(len(has_full_name) / total * 100, 2) if total > 0 else 0,
            'unlinked_sample': no_profile_match[:50],
        }

    def analyze_teams(self) -> Dict[str, Any]:
        rows = self._fetch_rows(
            """
            SELECT team_id, name, normalized_name, profile_url
            FROM teams
            """
        )

        linked_to_profile = []
        no_profile_match = []

        for team_id, name, normalized_name, profile_url in rows:
            team_info = {
                'team_id': team_id,
                'name': name,
                'normalized_name': normalized_name,
                'profile_url': profile_url,
            }
            if 'mainz' in (normalized_name or '').lower() or ((profile_url and profile_url.strip()) or normalized_name in self.team_names):
                linked_to_profile.append(team_info)
            else:
                no_profile_match.append(team_info)

        total = len(rows)
        return {
            'total': total,
            'linked_to_profile': len(linked_to_profile),
            'no_profile_match': len(no_profile_match),
            'link_rate_percent': round(len(linked_to_profile) / total * 100, 2) if total > 0 else 0,
            'unlinked_sample': no_profile_match[:50],
        }

    def find_potential_duplicates(self) -> Dict[str, List[Dict[str, Any]]]:
        rows = self._fetch_rows(
            """
            SELECT p1.player_id, p1.name, p1.normalized_name,
                   p2.player_id, p2.name, p2.normalized_name
            FROM players p1
            JOIN players p2 ON p1.player_id < p2.player_id
            WHERE (
                p1.normalized_name LIKE '%' || p2.normalized_name || '%'
                OR p2.normalized_name LIKE '%' || p1.normalized_name || '%'
            )
            AND LENGTH(p1.normalized_name) > 5
            AND LENGTH(p2.normalized_name) > 5
            LIMIT 100
            """
        )
        return {
            'player_potential_duplicates': [
                {
                    'player1': {'id': row[0], 'name': row[1], 'normalized': row[2]},
                    'player2': {'id': row[3], 'name': row[4], 'normalized': row[5]},
                }
                for row in rows
            ],
        }

    def generate_report(self) -> Dict[str, Any]:
        return build_report_payload(self)

    def save_report(self, report: Optional[Dict[str, Any]] = None) -> str:
        if report is None:
            report = self.generate_report()
        return save_report_file(self.output_dir, report)

    def print_summary(self, report: Optional[Dict[str, Any]] = None) -> None:
        if report is None:
            report = self.generate_report()
        print_report_summary(report)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='Generate entity linking report')
    parser.add_argument('--db-path', default='fsv_archive_complete.db', help='Path to SQLite database')
    parser.add_argument('--indices-dir', default=DEFAULT_INDICES_DIR, help='Path to profile indices')
    parser.add_argument('--output-dir', default=DEFAULT_REPORTS_DIR, help='Output directory for reports')
    args = parser.parse_args()

    reporter = EntityLinkingReporter(args.db_path, args.indices_dir, args.output_dir)
    report = reporter.generate_report()
    reporter.print_summary(report)
    filepath = reporter.save_report(report)
    print(f"\nFull report saved to: {filepath}")


if __name__ == '__main__':
    main()
