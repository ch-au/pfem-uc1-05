#!/usr/bin/env python3
"""
Test attendance parsing for old vs new match formats
"""
from pathlib import Path
from bs4 import BeautifulSoup
import re
from datetime import datetime

def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())

def parse_int(value: str) -> int:
    value = value.strip()
    if not value:
        return None
    value = value.replace(".", "").replace(",", "")
    if value.isdigit():
        return int(value)
    return None

def extract_match_details(soup: BeautifulSoup) -> dict:
    """Extract match details using UPDATED logic"""
    info = {
        "date": None,
        "kickoff": None,
        "attendance": None,
    }
    
    header_line = soup.find(string=re.compile(r"Zuschauer", re.IGNORECASE))
    if header_line:
        container_text = header_line.parent.get_text(" ", strip=True) if header_line.parent else header_line
        text = normalize_whitespace(container_text)
        parts = [p.strip() for p in text.replace(" Uhr", "").split(",")]
        
        # Parse date (always first part)
        if parts:
            date_parts = parts[0].split()
            if date_parts:
                try:
                    info["date"] = datetime.strptime(date_parts[-1], "%d.%m.%Y").strftime("%Y-%m-%d")
                except ValueError:
                    info["date"] = date_parts[-1]
        
        # Determine format: old (Datum, Zuschauer) vs new (Datum, Zeit, Zuschauer)
        # Check each part for "Zuschauer" keyword to find attendance
        for i, part in enumerate(parts[1:], 1):
            part_lower = part.lower()
            if "zuschauer" in part_lower or "zuschau" in part_lower:
                # This part contains attendance
                attendance_text = part.replace("Zuschauer.", "").replace("Zuschauer", "").strip()
                # Handle special cases like "keine Zuschauer"
                if not attendance_text.startswith("keine") and not attendance_text.startswith("no"):
                    attendance_value = parse_int(attendance_text.split()[0] if attendance_text else "")
                    info["attendance"] = attendance_value
            elif i == 1 and not ("zuschauer" in part_lower):
                # First part after date, doesn't contain "Zuschauer" -> likely kickoff time
                info["kickoff"] = part
    
    return info

def test_matches():
    """Test various match formats"""
    test_cases = [
        ("1969-70/profiliga19.html", "Old format (no time)", 1970, 2000),
        ("2004-05/profiliga02.html", "Modern format (with time)", 2004, 18700),
        ("2020-21/profiliga33.html", "COVID format", 2021, None),
    ]
    
    print('='*80)
    print('TESTING ATTENDANCE PARSING - OLD VS NEW FORMATS')
    print('='*80)
    
    for file_path, description, expected_year, expected_attendance in test_cases:
        print(f'\n{description}:')
        print(f'  File: {file_path}')
        
        full_path = Path("fsvarchiv") / file_path
        
        if not full_path.exists():
            print(f'  ✗ File not found')
            continue
        
        with full_path.open("r", encoding="latin-1", errors="ignore") as f:
            soup = BeautifulSoup(f.read(), "lxml")
        
        info = extract_match_details(soup)
        
        # Check results
        if info["date"]:
            year = int(info["date"][:4])
            if year == expected_year:
                print(f'  ✓ Date: {info["date"]}')
            else:
                print(f'  ✗ Date: {info["date"]} (expected year {expected_year})')
        else:
            print(f'  ✗ Date: Missing')
        
        if info["kickoff"]:
            print(f'  ✓ Kickoff: {info["kickoff"]}')
        else:
            print(f'  ⚠ Kickoff: Missing (may be normal for old matches)')
        
        if expected_attendance is not None:
            if info["attendance"] == expected_attendance:
                print(f'  ✓ Attendance: {info["attendance"]:,}')
            else:
                print(f'  ✗ Attendance: {info["attendance"]} (expected {expected_attendance:,})')
        else:
            if info["attendance"] is None:
                print(f'  ✓ Attendance: None (COVID - correct)')
            else:
                print(f'  ✗ Attendance: {info["attendance"]} (expected None for COVID)')

if __name__ == "__main__":
    test_matches()

