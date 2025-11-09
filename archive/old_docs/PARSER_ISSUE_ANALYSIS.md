# Parser Issue Analysis - Missing Bundesliga Data
**Date:** 2025-11-09
**Issue:** PostgreSQL database has 0 Bundesliga matches with Mainz 05

---

## Problem Summary

Your query to find Mainz 05 win rate by competition shows **0 Bundesliga matches**, even though:
- ✅ Mainz 05 has played in Bundesliga since 2004-05
- ✅ HTML files exist for those seasons (2004-05 through 2024-25)
- ✅ Parser is working correctly
- ❌ **Parser is NOT finding/parsing the Bundesliga match files**

---

## Root Cause Analysis

### 1. Parser Output: SQLite vs PostgreSQL

**The parser writes to SQLite, not PostgreSQL!**

```python
# Line 123 in parsing/comprehensive_fsv_parser.py
self.conn = sqlite3.connect(db_path)
```

**Current state:**
- ✅ SQLite database exists: `fsv_archive_complete.db`
- ✅ Contains 3,354 matches total
- ❌ But **0 Bundesliga matches** with Mainz 05!
- ✅ PostgreSQL was populated from SQLite (same data)

**Verification:**
```bash
sqlite3 fsv_archive_complete.db "SELECT COUNT(*) FROM matches"
# Result: 3354

# Check Bundesliga
sqlite3 fsv_archive_complete.db \
  "SELECT COUNT(*) FROM matches m
   JOIN season_competitions sc ON m.season_competition_id = sc.season_competition_id
   JOIN competitions c ON sc.competition_id = c.competition_id
   WHERE c.name = 'Bundesliga' AND (m.home_team_id = 1 OR m.away_team_id = 1)"
# Result: 0  ← PROBLEM!
```

### 2. Parser File Name Expectations

The parser looks for specific filenames (lines 1435-1467):

```python
# League file (main competition)
for filename in ['profiliga.html', 'profitab.html', 'profitabb.html']:
    candidate = season_path / filename
    if candidate.exists():
        league_name = self._extract_league_from_html(candidate)
        ...

# Cup competitions
("DFB-Pokal", "cup", season_path / "profipokal.html"),

# European competitions
for european_stub in ["profiuefa", "profiuec", "profiueclq", ...]:
    overview = season_path / f"{european_stub}.html"
    ...

# Friendlies
profirest_file = season_path / "profirest.html"
```

**The parser expects files starting with `profi*`:**
- `profiliga.html` - Main league
- `profitab.html` - Alternative league file
- `profitabb.html` - Alternative league file
- `profipokal.html` - DFB-Pokal
- `profiuefa.html` - European competitions
- `profirest.html` - Friendly matches

### 3. Actual File Names in Archive

**Modern seasons (2004-05 onwards) use `aj*` prefix instead of `profi*`:**

```bash
ls fsvarchiv/2004-05/ | grep liga
ajliga.html
ajliga01.html
ajliga02.html
...

ls fsvarchiv/2023-24/ | grep liga
ajliga.html
ajliga01.html
ajliga02.html
...
```

**But these `ajliga` files are U19/youth matches, not first team!**

```html
<!-- fsvarchiv/2004-05/ajliga01.html -->
<b>SpVgg Unterhaching - FSV U19 1:1 (0:1)</b>
```

### 4. Historical Matches Are Being Parsed

The parser IS finding files in older seasons:

```bash
# Competitions with Mainz matches in database
sqlite3 fsv_archive_complete.db \
  "SELECT c.name, COUNT(*) FROM matches m
   JOIN season_competitions sc ON m.season_competition_id = sc.season_competition_id
   JOIN competitions c ON sc.competition_id = c.competition_id
   WHERE m.home_team_id = 1 OR m.away_team_id = 1
   GROUP BY c.name ORDER BY COUNT(*) DESC"

Europapokal|50              # 1911-1934
Bezirksklasse Rheinhessen|38  # 1937-1940
Kreisliga Hessen|36          # 1920-1923
DFB-Pokal|32                # 1936-1985
...
```

**Date ranges confirm only historical data:**
- Earliest match: 1906-10-07
- Latest match: 1985-04-24
- **Missing: Everything from 1985 onwards!**

---

## The Missing Link: What Files Contain Bundesliga Matches?

Let me investigate a modern season structure:

```bash
ls fsvarchiv/2023-24/ | head -30
ajkader.html       # Youth squad
ajkader2.html
ajkader3.html
ajkarten.html
ajliga.html        # Youth league overview
ajliga01.html      # Youth matches
ajliga02.html
...
ajpokal.html       # Youth cup
profi???           # ← MISSING!
```

**Problem:** Modern seasons don't have `profi*` files, only `aj*` files (youth team).

**Where are the first team Bundesliga matches stored?**

Possibilities:
1. Different directory structure?
2. Different file naming convention?
3. Data not included in archive?
4. Separate database/source?

---

## Investigation Needed

### Check 1: Does `profiliga.html` exist in ANY recent season?

```bash
find fsvarchiv/20* -name "profiliga.html" | head -10
```

If **NO results**: First team data uses different naming

If **HAS results**: Parser should have found them

### Check 2: What about `profitab.html` or `profitabb.html`?

```bash
find fsvarchiv/20* -name "profitab*.html" | head -10
```

### Check 3: Are there ANY `profi*` files in modern seasons?

```bash
ls fsvarchiv/2023-24/ | grep ^profi
```

### Check 4: Check an older season that WAS parsed

```bash
# Find which season has Europapokal data
sqlite3 fsv_archive_complete.db \
  "SELECT s.label, c.name, COUNT(*)
   FROM matches m
   JOIN season_competitions sc ON m.season_competition_id = sc.season_competition_id
   JOIN seasons s ON sc.season_id = s.season_id
   JOIN competitions c ON sc.competition_id = c.competition_id
   WHERE m.home_team_id = 1 OR m.away_team_id = 1
   GROUP BY s.label, c.name
   ORDER BY s.label DESC
   LIMIT 20"

# Then check what files exist in that season directory
ls fsvarchiv/1933-34/ | grep -E "profi|liga"
```

---

## Hypothesis

**Most likely scenario:**

The archive structure has TWO separate sections:
1. **Historical archive** (1905-1985): Uses `profi*` naming → **Parser finds these**
2. **Modern archive** (1985-present): Uses different structure/naming → **Parser misses these**

OR

The `fsvarchiv/` directory only contains:
- Youth team data (`aj*` prefix)
- Historical first team data (up to 1985)
- Modern first team data is stored elsewhere (different directory? different source?)

---

## Next Steps

1. **Investigate file structure** for modern seasons
2. **Find where Bundesliga data is stored** (if it exists)
3. **Update parser** to handle modern file naming conventions
4. **Re-run parser** to populate complete dataset

---

## Immediate Action

Run these commands to diagnose:

```bash
# 1. Check if profi* files exist in modern seasons
echo "=== profiliga files in 2000s ==="
find fsvarchiv/200* -name "profiliga.html" 2>/dev/null | wc -l

# 2. Check what profi* files DO exist
echo "=== All profi* files ==="
find fsvarchiv/ -name "profi*.html" -type f | head -20

# 3. Check a successfully parsed season
echo "=== Files in 1933-34 (has Europapokal data) ==="
ls fsvarchiv/1933-34/ | head -20

# 4. Compare with modern season
echo "=== Files in 2023-24 (should have Bundesliga) ==="
ls fsvarchiv/2023-24/ | head -20

# 5. Check for alternative directory structure
echo "=== Top-level directories ==="
ls -d fsvarchiv/*/ | grep -v "^[0-9]" | head -20
```

---

## Expected Parser Fix

Once we find where Bundesliga data is stored, update the parser:

```python
# Current (lines 1435-1441)
for filename in ['profiliga.html', 'profitab.html', 'profitabb.html']:
    candidate = season_path / filename
    ...

# Updated (add modern naming conventions)
for filename in [
    'profiliga.html', 'profitab.html', 'profitabb.html',  # Historical
    'bundesliga.html', 'ligaXX.html', ...  # Modern (TBD)
]:
    candidate = season_path / filename
    ...
```

---

## Conclusion

**The parser works, but it's looking for files that don't exist in modern seasons.**

We need to:
1. Find where modern Bundesliga data is actually stored
2. Update parser to read those files
3. Re-run the parser
4. Populate both SQLite and PostgreSQL with complete dataset

**Status:** Investigation in progress - need to examine file structure.
