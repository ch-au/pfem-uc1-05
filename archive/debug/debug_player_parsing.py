#!/usr/bin/env python3
"""
Debug script to check player profile parsing
"""
from pathlib import Path
from bs4 import BeautifulSoup
import re
import unicodedata

def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())

def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))

def normalize_name(name: str) -> str:
    cleaned = strip_accents(name).replace(".", " ").replace("-", " ")
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", cleaned)
    return normalize_whitespace(cleaned).lower()

def test_brosinski_parsing():
    """Test parsing of brosinski.html"""
    
    player_file = Path("fsvarchiv/spieler/brosinski.html")
    
    if not player_file.exists():
        print(f"ERROR: File not found: {player_file}")
        return
    
    print(f"Reading file: {player_file}")
    
    with player_file.open("r", encoding="latin-1", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "lxml")
    
    # Get all text for debugging
    information = soup.get_text("\n", strip=True)
    
    print("\n" + "="*80)
    print("FULL TEXT CONTENT (first 1000 chars):")
    print("="*80)
    print(information[:1000])
    
    # Test height parsing
    print("\n" + "="*80)
    print("HEIGHT PARSING:")
    print("="*80)
    height_match = re.search(r"(\d{2,3})\s*cm", information)
    if height_match:
        print(f"✓ Found height: {height_match.group(1)} cm")
        print(f"  Match: '{height_match.group(0)}'")
    else:
        print("✗ Height not found")
        # Try to find any mention of cm
        cm_matches = re.findall(r".{0,20}\d+\s*cm.{0,20}", information)
        if cm_matches:
            print("  Possible matches:")
            for match in cm_matches[:5]:
                print(f"    - {match}")
    
    # Test weight parsing
    print("\n" + "="*80)
    print("WEIGHT PARSING:")
    print("="*80)
    weight_match = re.search(r"(\d{2,3})\s*kg", information)
    if weight_match:
        print(f"✓ Found weight: {weight_match.group(1)} kg")
        print(f"  Match: '{weight_match.group(0)}'")
    else:
        print("✗ Weight not found")
        # Try to find any mention of kg
        kg_matches = re.findall(r".{0,20}\d+\s*kg.{0,20}", information)
        if kg_matches:
            print("  Possible matches:")
            for match in kg_matches[:5]:
                print(f"    - {match}")
    
    # Test position parsing
    print("\n" + "="*80)
    print("POSITION PARSING:")
    print("="*80)
    position_header = soup.find("b", string=re.compile("Position", re.IGNORECASE))
    primary_position = None
    if position_header:
        print(f"✓ Found position header: '{position_header.string}'")
        parent = position_header.find_parent()
        if parent:
            found_header = False
            for string in parent.stripped_strings:
                if found_header and string and not string.endswith(":"):
                    primary_position = normalize_whitespace(string)
                    break
                if "position" in string.lower():
                    found_header = True
            if primary_position:
                print(f"✓ Position value: '{primary_position}'")
            else:
                print("✗ Position value not found after header")
                print("  Parent strings:")
                for i, s in enumerate(parent.stripped_strings):
                    print(f"    {i}: '{s}'")
        else:
            print("✗ Position parent not found")
    else:
        print("✗ Position header not found")
        # Search for any bold tags
        bold_tags = soup.find_all("b")
        print(f"  Found {len(bold_tags)} <b> tags:")
        for tag in bold_tags[:10]:
            print(f"    - '{tag.string}'")
    
    # Test nationality parsing
    print("\n" + "="*80)
    print("NATIONALITY PARSING:")
    print("="*80)
    nationality_header = soup.find("b", string=re.compile(r"Nationalit[aä]t", re.IGNORECASE))
    nationality = None
    if nationality_header:
        print(f"✓ Found nationality header: '{nationality_header.string}'")
        parent = nationality_header.find_parent()
        if parent:
            found_header = False
            for string in parent.stripped_strings:
                if found_header and string and not string.endswith(":"):
                    nationality = normalize_whitespace(string)
                    break
                if "nationalit" in string.lower():
                    found_header = True
            if nationality:
                print(f"✓ Nationality value: '{nationality}'")
            else:
                print("✗ Nationality value not found after header")
                print("  Parent strings:")
                for i, s in enumerate(parent.stripped_strings):
                    print(f"    {i}: '{s}'")
        else:
            print("✗ Nationality parent not found")
    else:
        print("✗ Nationality header not found")
        # Try to find it in text
        nat_matches = re.findall(r"Nationalit[aä]t:?\s*(\w+)", information, re.IGNORECASE)
        if nat_matches:
            print("  Possible matches in text:")
            for match in nat_matches:
                print(f"    - {match}")

if __name__ == "__main__":
    test_brosinski_parsing()

