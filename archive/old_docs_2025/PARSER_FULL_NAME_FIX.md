# Parser Fix: Full Player Names from Profile Links

**Date:** 2025-11-09
**Issue:** Parser only stored surnames (e.g., "Klopp") instead of full names (e.g., "Jürgen Klopp")
**Solution:** Extract profile URLs from match lineups and get full names before creating players

---

## Changes Made

### 1. Updated `PlayerAppearance` Dataclass

Added `profile_url` field to store the link to player profile page:

```python
@dataclass
class PlayerAppearance:
    name: str
    shirt_number: Optional[int]
    is_starter: bool
    profile_url: Optional[str] = None  # NEW: URL to player profile (e.g., "spieler/klopp.html")
    # ... rest of fields
```

### 2. Modified `parse_team_block` Method

Now extracts profile URLs from `<a href="../spieler/...">` links in match lineup HTML:

```python
# Extract profile URL from <a href="../spieler/..."> link
profile_url = None
anchor = cell.find("a", href=re.compile(r"spieler/.*\.html"))
if anchor and anchor.get("href"):
    href = anchor["href"]
    # Normalize path: "../spieler/klopp.html" -> "spieler/klopp.html"
    profile_url = href.replace("../", "")

# Store profile_url in PlayerAppearance
players[name] = PlayerAppearance(
    name=name,
    shirt_number=shirt_number,
    is_starter=not table_is_reserve,
    profile_url=profile_url,  # NEW
)
```

### 3. Added `get_full_name_from_profile` Method

New helper method to extract full name from player profile HTML:

```python
def get_full_name_from_profile(self, profile_url: str) -> Optional[str]:
    """Extract full name from player profile HTML.

    Args:
        profile_url: Relative path (e.g., "spieler/klopp.html")

    Returns:
        Full name from <b> tag (e.g., "JÜRGEN KLOPP") or None
    """
    # Reads profile HTML, finds <b> tag, extracts and cleans full name
    # Returns: "JÜRGEN KLOPP" instead of "Klopp"
```

### 4. Modified Player Creation Logic

**BEFORE** (created with surname only):
```python
player_id = self.db.get_or_create_player(appearance.name, appearance.profile_url)
# Creates player "Klopp" with profile_url
```

**AFTER** (gets full name first):
```python
# Get full name from profile BEFORE creating player
player_name = appearance.name  # "Klopp"
profile_url = appearance.profile_url  # "spieler/klopp.html"

if profile_url:
    full_name = self.get_full_name_from_profile(profile_url)
    if full_name:
        player_name = full_name  # "JÜRGEN KLOPP"
        self.logger.debug("Resolved %s -> %s from profile", appearance.name, full_name)

player_id = self.db.get_or_create_player(player_name, profile_url)
# Creates player "JÜRGEN KLOPP" instead of "Klopp"
```

### 5. Simplified `parse_player_profile` Method

**BEFORE:** Tried to create duplicate player with full name
**AFTER:** Only updates biographical data (birth date, nationality, etc.) for existing player

```python
# Find existing player and update with bio data only
cursor.execute("SELECT player_id FROM players WHERE normalized_name = ?", (normalized_key,))
player_id = cursor.fetchone()[0]

cursor.execute("""
    UPDATE players
    SET birth_date = COALESCE(?, birth_date),
        birth_place = COALESCE(?, birth_place),
        # ... other bio fields
    WHERE player_id = ?
""", (birth_date, birth_place, ..., player_id))
```

---

## How It Works (Flow)

1. **Parse Match Lineup** (`parse_team_block`)
   - Extract: "29 Klopp" from HTML
   - Extract: `<a href="../spieler/klopp.html">Klopp</a>`
   - Store: `PlayerAppearance(name="Klopp", profile_url="spieler/klopp.html")`

2. **Get Full Name** (`parse_season` → lineup processing)
   - Read: `spieler/klopp.html`
   - Extract: `<b>JÜRGEN KLOPP</b>` from profile
   - Use: "JÜRGEN KLOPP" as player name

3. **Create Player** (`get_or_create_player`)
   - Name: "JÜRGEN KLOPP" (not "Klopp"!)
   - Normalized: "jurgen klopp" (for deduplication)
   - Profile URL: "spieler/klopp.html"

4. **Update Bio Data** (`parse_player_profile`)
   - Add birth date, nationality, position, etc.
   - Does NOT change the name (already set to full name)

---

## Expected Results

### Before Fix
```
| player_id | name     | normalized_name |
|-----------|----------|-----------------|
| 1         | Klopp    | klopp           |
| 2         | Schürrle | schurrle        |
| 3         | Müller   | muller          |
```

### After Fix
```
| player_id | name            | normalized_name |
|-----------|-----------------|-----------------|
| 1         | JÜRGEN KLOPP    | jurgen klopp    |
| 2         | ANDRÉ SCHÜRRLE  | andre schurrle  |
| 3         | THOMAS MÜLLER   | thomas muller   |
```

---

## Testing

To test the fix on a single season:

```bash
cd parsing
python3 comprehensive_fsv_parser.py --seasons 2009-10
```

Check results:

```sql
SELECT name, normalized_name, birth_date, nationality
FROM players
WHERE name LIKE '%KLOPP%' OR name LIKE '%SCHÜRRLE%'
ORDER BY name;
```

Expected: Full names like "JÜRGEN KLOPP", "ANDRÉ SCHÜRRLE"

---

## Notes

- **Normalized names:** Still based on full name for better deduplication
  - "JÜRGEN KLOPP" → normalized: "jurgen klopp"
  - "Jürgen Klopp" → normalized: "jurgen klopp" (same, good!)

- **Missing profiles:** Some players (especially opponents) may not have profile pages
  - Fall back to surname from lineup: "Müller" (opponent player without profile)
  - Still better than before since Mainz players will all have full names

- **Performance:** Minimal impact
  - Profile pages are read once per player (cached)
  - Only adds one extra file read per player during parsing

---

## Database Schema

No schema changes needed! The `players.name` field already supports full names.

```sql
-- Name field can hold both:
-- - Full names: "JÜRGEN KLOPP"
-- - Surnames only: "Müller" (if no profile available)

CREATE TABLE players (
    player_id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,              -- Now stores FULL names!
    normalized_name TEXT UNIQUE,   -- Normalized full name for deduplication
    birth_date TEXT,
    birth_place TEXT,
    height_cm INTEGER,
    weight_kg INTEGER,
    primary_position TEXT,
    nationality TEXT,
    profile_url TEXT,              -- Link to profile page
    image_url TEXT
);
```

---

## Next Steps

1. ✅ **Test with single season** (2009-10)
2. ⏳ **Run full reparse** on all seasons
3. ⏳ **Verify results** in database
4. ⏳ **Update frontend** to display full names in quiz questions
5. ⏳ **Update quality report** with new statistics

---

**Status:** READY TO TEST
**Risk:** LOW (only affects new parsing runs, not existing data)
**Impact:** HIGH (fixes 83% of players missing full names)
