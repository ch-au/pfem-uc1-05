#!/usr/bin/env python3
"""
Debug script to check match detail parsing
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

def test_match_parsing():
    """Test parsing of match details"""
    
    # Test two files: one normal, one COVID
    test_files = [
        ("2004-05/profiliga02.html", "Normal game with attendance"),
        ("2020-21/profiliga33.html", "COVID game - no attendance"),
    ]
    
    for file_path, description in test_files:
        print("\n" + "="*80)
        print(f"TESTING: {description}")
        print(f"File: {file_path}")
        print("="*80)
        
        full_path = Path("fsvarchiv") / file_path
        
        if not full_path.exists():
            print(f"ERROR: File not found: {full_path}")
            continue
        
        with full_path.open("r", encoding="latin-1", errors="ignore") as f:
            soup = BeautifulSoup(f.read(), "lxml")
        
        # Extract match details
        info = {
            "date": None,
            "kickoff": None,
            "attendance": None,
            "referee": None,
        }
        
        # Find the header line with attendance info
        header_line = soup.find(string=re.compile(r"Zuschauer", re.IGNORECASE))
        
        if header_line:
            print("\n✓ Found 'Zuschauer' line")
            container_text = header_line.parent.get_text(" ", strip=True) if header_line.parent else header_line
            text = normalize_whitespace(container_text)
            print(f"  Raw text: '{text}'")
            
            # Remove " Uhr" and split
            text_clean = text.replace(" Uhr", "")
            parts = [p.strip() for p in text_clean.split(",")]
            print(f"  Parts after split: {parts}")
            
            if parts:
                date_parts = parts[0].split()
                if date_parts:
                    try:
                        info["date"] = datetime.strptime(date_parts[-1], "%d.%m.%Y").strftime("%Y-%m-%d")
                        print(f"  ✓ Date: {info['date']}")
                    except ValueError:
                        info["date"] = date_parts[-1]
                        print(f"  ⚠ Date (unparsed): {info['date']}")
            
            if len(parts) > 1:
                info["kickoff"] = parts[1]
                print(f"  ✓ Kickoff: {info['kickoff']}")
            else:
                print(f"  ✗ Kickoff: Missing (only {len(parts)} parts)")
            
            if len(parts) > 2:
                attendance_text = parts[2].replace("Zuschauer.", "").replace("Zuschauer", "").strip()
                print(f"  Attendance text: '{attendance_text}'")
                
                attendance_value = parse_int(attendance_text)
                if attendance_value:
                    info["attendance"] = attendance_value
                    print(f"  ✓ Attendance: {info['attendance']}")
                else:
                    print(f"  ✗ Attendance: Could not parse number from '{attendance_text}'")
            else:
                print(f"  ✗ Attendance: Missing (only {len(parts)} parts)")
        else:
            print("\n✗ 'Zuschauer' line not found")
        
        # Parse halftime score from header
        print("\n--- Halftime Score Parsing ---")
        header = soup.find("b")
        if header:
            header_text = header.get_text(strip=True)
            print(f"Header text: '{header_text}'")
            
            # Look for pattern like "2:1 (0:1)"
            halftime_match = re.search(r"(\d+):(\d+)\s*\((\d+):(\d+)\)", header_text)
            if halftime_match:
                full_home = int(halftime_match.group(1))
                full_away = int(halftime_match.group(2))
                half_home = int(halftime_match.group(3))
                half_away = int(halftime_match.group(4))
                print(f"  ✓ Fulltime: {full_home}:{full_away}")
                print(f"  ✓ Halftime: {half_home}:{half_away}")
            else:
                print(f"  ✗ Halftime score not found in header")
        
        print("\n" + "-"*80)
        print("SUMMARY:")
        print(f"  Date: {info.get('date', 'MISSING')}")
        print(f"  Kickoff: {info.get('kickoff', 'MISSING')}")
        print(f"  Attendance: {info.get('attendance', 'MISSING')}")

if __name__ == "__main__":
    test_match_parsing()

