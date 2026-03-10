#!/usr/bin/env python3
"""
Profile Index Builder

Parses canonical entity data from profile folders (spieler, gegner, trainer)
to build master indices for entity linking during match parsing.
"""

import json
import logging
from dataclasses import asdict
from pathlib import Path

from parsing.profile_parsers import (
    CoachProfile,
    CoachProfileParser,
    PlayerProfile,
    PlayerProfileParser,
    TeamProfile,
    TeamProfileParser,
    normalize_name,
    normalize_whitespace,
    strip_accents,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = "generated/indices"

__all__ = [
    "CoachProfile",
    "CoachProfileParser",
    "DEFAULT_OUTPUT_DIR",
    "PlayerProfile",
    "PlayerProfileParser",
    "ProfileIndexBuilder",
    "TeamProfile",
    "TeamProfileParser",
    "normalize_name",
    "normalize_whitespace",
    "strip_accents",
]


class ProfileIndexBuilder:
    """Build canonical entity indices from profile folders."""

    SKIPPED_PROFILE_FILES = {
        "gegner.html",
        "gegnerfr.html",
        "gegnertop.html",
    }

    def __init__(self, archive_dir: str = 'fsvarchiv', output_dir: str = DEFAULT_OUTPUT_DIR):
        self.archive_dir = Path(archive_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.player_parser = PlayerProfileParser()
        self.coach_parser = CoachProfileParser()
        self.team_parser = TeamProfileParser()
        self.stats = {
            'players_parsed': 0,
            'players_failed': 0,
            'coaches_parsed': 0,
            'coaches_failed': 0,
            'teams_parsed': 0,
            'teams_failed': 0,
        }

    def _build_index(self, subdirectory: str, parser, parsed_key: str, failed_key: str) -> dict:
        source_dir = self.archive_dir / subdirectory
        if not source_dir.exists():
            logger.error("%s directory not found: %s", subdirectory.capitalize(), source_dir)
            return {}

        index = {}
        for index_num, filepath in enumerate(sorted(source_dir.glob('*.html')), 1):
            if filepath.name in self.SKIPPED_PROFILE_FILES:
                continue
            profile = parser.parse(filepath)
            if profile:
                index[profile.filename] = asdict(profile)
                self.stats[parsed_key] += 1
            else:
                self.stats[failed_key] += 1
            if index_num % 250 == 0:
                logger.info(
                    "Processed %s files in %s (%s parsed, %s failed)",
                    index_num,
                    subdirectory,
                    self.stats[parsed_key],
                    self.stats[failed_key],
                )

        logger.info(
            "Parsed %s profiles for %s (%s failed)",
            self.stats[parsed_key],
            subdirectory,
            self.stats[failed_key],
        )
        return index

    def build_player_index(self) -> dict:
        return self._build_index('spieler', self.player_parser, 'players_parsed', 'players_failed')

    def build_coach_index(self) -> dict:
        return self._build_index('trainer', self.coach_parser, 'coaches_parsed', 'coaches_failed')

    def build_team_index(self) -> dict:
        return self._build_index('gegner', self.team_parser, 'teams_parsed', 'teams_failed')

    def build_all_indices(self) -> dict:
        logger.info("Building profile indices...")
        indices = {
            'players': self.build_player_index(),
            'coaches': self.build_coach_index(),
            'teams': self.build_team_index(),
        }

        file_paths = {}
        for name, payload in indices.items():
            output_path = self.output_dir / f'{name}.json'
            with open(output_path, 'w', encoding='utf-8') as file_obj:
                json.dump(payload, file_obj, ensure_ascii=False, indent=2)
            file_paths[name] = str(output_path)

        summary = {
            'stats': self.stats,
            'total_entities': self.stats['players_parsed'] + self.stats['coaches_parsed'] + self.stats['teams_parsed'],
            'files': file_paths,
        }
        with open(self.output_dir / 'summary.json', 'w', encoding='utf-8') as file_obj:
            json.dump(summary, file_obj, ensure_ascii=False, indent=2)

        logger.info("Total entities indexed: %s", summary['total_entities'])
        logger.info("Indices saved to %s", self.output_dir)
        return summary


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='Build profile indices for FSV archive')
    parser.add_argument('--archive-dir', default='fsvarchiv', help='Path to fsvarchiv directory')
    parser.add_argument('--output-dir', default=DEFAULT_OUTPUT_DIR, help='Output directory for indices')
    args = parser.parse_args()

    summary = ProfileIndexBuilder(args.archive_dir, args.output_dir).build_all_indices()
    print("\n=== Profile Index Summary ===")
    print(f"Players: {summary['stats']['players_parsed']} parsed, {summary['stats']['players_failed']} failed")
    print(f"Coaches: {summary['stats']['coaches_parsed']} parsed, {summary['stats']['coaches_failed']} failed")
    print(f"Teams:   {summary['stats']['teams_parsed']} parsed, {summary['stats']['teams_failed']} failed")
    print(f"Total:   {summary['total_entities']} entities indexed")


if __name__ == '__main__':
    main()
