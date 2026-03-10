import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def build_report_payload(reporter) -> Dict[str, Any]:
    logging.getLogger(__name__).info("Generating entity linking report...")
    report = {
        'generated_at': datetime.now().isoformat(),
        'database': str(reporter.db_path),
        'indices_dir': str(reporter.indices_dir),
        'profile_counts': {
            'players': len(reporter.players_index),
            'coaches': len(reporter.coaches_index),
            'teams': len(reporter.teams_index),
        },
        'players': reporter.analyze_players(),
        'coaches': reporter.analyze_coaches(),
        'teams': reporter.analyze_teams(),
        'potential_duplicates': reporter.find_potential_duplicates(),
    }

    total_db = report['players']['total'] + report['coaches']['total'] + report['teams']['total']
    total_linked = (
        report['players']['linked_to_profile']
        + report['coaches']['linked_to_profile']
        + report['teams']['linked_to_profile']
    )
    report['summary'] = {
        'total_entities_in_db': total_db,
        'total_linked_to_profiles': total_linked,
        'overall_link_rate_percent': round(total_linked / total_db * 100, 2) if total_db > 0 else 0,
    }
    return report


def save_report_file(output_dir: Path, report: Optional[Dict[str, Any]] = None) -> str:
    if report is None:
        raise ValueError("report is required")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = output_dir / f"entity_linking_{timestamp}.json"
    with open(filepath, 'w', encoding='utf-8') as file_obj:
        json.dump(report, file_obj, ensure_ascii=False, indent=2)
    logging.getLogger(__name__).info("Report saved to %s", filepath)
    return str(filepath)


def print_report_summary(report: Dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("ENTITY LINKING REPORT")
    print("=" * 60)

    print(f"\nGenerated: {report['generated_at']}")
    print(f"Database: {report['database']}")

    print("\n--- Profile Indices ---")
    print(f"Players: {report['profile_counts']['players']}")
    print(f"Coaches: {report['profile_counts']['coaches']}")
    print(f"Teams:   {report['profile_counts']['teams']}")

    players = report['players']
    print("\n--- Player Linking ---")
    print(f"Total in DB:        {players['total']}")
    print(f"Linked to profile:  {players['linked_to_profile']} ({players['link_rate_percent']}%)")
    print(f"No profile match:   {players['no_profile_match']}")
    print(f"With full name:     {players['has_full_name']} ({players['full_name_rate_percent']}%)")
    print(f"Surname only:       {players['surname_only']}")

    coaches = report['coaches']
    print("\n--- Coach Linking ---")
    print(f"Total in DB:        {coaches['total']}")
    print(f"Linked to profile:  {coaches['linked_to_profile']} ({coaches['link_rate_percent']}%)")
    print(f"No profile match:   {coaches['no_profile_match']}")

    teams = report['teams']
    print("\n--- Team Linking ---")
    print(f"Total in DB:        {teams['total']}")
    print(f"Linked to profile:  {teams['linked_to_profile']} ({teams['link_rate_percent']}%)")
    print(f"No profile match:   {teams['no_profile_match']}")

    summary = report['summary']
    print("\n--- Overall Summary ---")
    print(f"Total entities:     {summary['total_entities_in_db']}")
    print(f"Total linked:       {summary['total_linked_to_profiles']}")
    print(f"Overall link rate:  {summary['overall_link_rate_percent']}%")
    print("\n" + "=" * 60)
