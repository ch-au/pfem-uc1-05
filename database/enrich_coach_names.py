#!/usr/bin/env python3
"""
Enrich coach names from profile files.

This script updates coach names in the database by reading their full names
from the trainer/*.html profile files.

Usage:
    python database/enrich_coach_names.py
"""

import sys
import sqlite3
from pathlib import Path
import re
from bs4 import BeautifulSoup


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text."""
    return " ".join(text.split())


def normalize_name(name: str) -> str:
    """Normalize a name for comparison."""
    if not name:
        return ""
    name = name.lower()
    # Remove umlauts and special characters
    replacements = {
        'ä': 'a', 'ö': 'o', 'ü': 'u', 'ß': 'ss',
        'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e',
        'è': 'e', 'ê': 'e', 'í': 'i', 'ì': 'i',
        'ó': 'o', 'ò': 'o', 'ú': 'u', 'ù': 'u',
    }
    for char, replacement in replacements.items():
        name = name.replace(char, replacement)
    return normalize_whitespace(name)


def read_html(file_path: Path):
    """Read and parse an HTML file."""
    try:
        with open(file_path, "r", encoding="latin1") as f:
            content = f.read()
        return BeautifulSoup(content, "html.parser")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None


def enrich_coaches(db_path: str = "fsv_archive_complete.db"):
    """Enrich all coaches with full names from profiles."""

    base_path = Path("fsvarchiv")
    trainer_dir = base_path / "trainer"

    if not trainer_dir.exists():
        print(f"❌ Trainer directory not found: {trainer_dir}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    coach_files = list(trainer_dir.glob("*.html"))
    print(f"Found {len(coach_files)} coach profile files")

    enriched = 0
    updated_coaches = []

    for i, coach_file in enumerate(coach_files, 1):
        if i % 20 == 0:
            print(f"  Processing {i}/{len(coach_files)}...")

        soup = read_html(coach_file)
        if soup is None:
            continue

        # Get coach name from profile
        header = soup.find("b")
        if not header:
            continue

        profile_name = normalize_whitespace(header.get_text(" ", strip=True))
        normalized = normalize_name(profile_name)

        # Find matching coach(es) in database by last name
        last_name = normalized.split()[-1] if normalized else ''
        cursor.execute(
            "SELECT coach_id, name FROM coaches WHERE normalized_name LIKE ?",
            (f"%{last_name}%",)
        )
        matches = cursor.fetchall()

        if matches:
            for coach_id, existing_name in matches:
                # Only update if the profile has a fuller name
                if ' ' in profile_name and ' ' not in existing_name:
                    # Parse birth info
                    information = soup.get_text("\n", strip=True)
                    birth_match = re.search(r"\*.*?(\d{2}\.\d{2}\.\d{4}).*?in\s+([^,\n.]+)", information, re.DOTALL)
                    birth_date = None
                    birth_place = None
                    if birth_match:
                        try:
                            from datetime import datetime
                            birth_date = datetime.strptime(birth_match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
                        except:
                            birth_date = birth_match.group(1)
                        birth_place = birth_match.group(2).strip()

                    # Update coach record - only update name if it won't violate UNIQUE constraint
                    new_normalized = normalize_name(profile_name)

                    # Check if normalized name already exists
                    cursor.execute("SELECT coach_id FROM coaches WHERE normalized_name = ?", (new_normalized,))
                    conflict = cursor.fetchone()

                    if conflict and conflict[0] != coach_id:
                        # Skip if another coach already has this normalized name
                        print(f"  ⚠️  Skipping {existing_name} → {profile_name} (conflict with coach_id {conflict[0]})")
                        continue

                    # Update coach record
                    cursor.execute(
                        """
                        UPDATE coaches
                        SET name = ?,
                            normalized_name = ?,
                            birth_date = COALESCE(?, birth_date),
                            birth_place = COALESCE(?, birth_place),
                            profile_url = COALESCE(?, profile_url)
                        WHERE coach_id = ?
                        """,
                        (profile_name, new_normalized, birth_date, birth_place,
                         str(coach_file.relative_to(base_path)), coach_id)
                    )

                    updated_coaches.append((existing_name, profile_name))
                    enriched += 1

    conn.commit()
    conn.close()

    print(f"\n✅ Enriched {enriched} coach records from {len(coach_files)} profile files")

    if updated_coaches:
        print(f"\n📋 Sample updates (first 10):")
        for old, new in updated_coaches[:10]:
            print(f"  {old:20s} → {new}")

    # Verify Klopp specifically
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name, birth_date, birth_place FROM coaches WHERE normalized_name LIKE '%klopp%'")
    klopp = cursor.fetchone()
    conn.close()

    if klopp:
        print(f"\n🎯 Klopp verification:")
        print(f"  Name: {klopp[0]}")
        print(f"  Born: {klopp[1]} in {klopp[2]}")


if __name__ == "__main__":
    enrich_coaches()
