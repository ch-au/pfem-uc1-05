# Automatische Verbesserungen beim Parsing

## Was automatisch beim Parsing passiert

### ✅ Spielernamen-Bereinigung (automatisch)

Die folgenden Verbesserungen werden **automatisch beim Parsing** angewendet:

1. **"?" am Anfang entfernen**: `"? SANDER"` → `"SANDER"`
   - In `get_or_create_player()` (Zeile 610-615)
   - In `parse_team_block()` (Zeile 2132-2133)
   - In `parse_player_profile()` (Zeile 2417-2418)

2. **"wdh." Präfixe entfernen**: `"wdh. FE, Lipponer"` → `"Lipponer"`
   - In `get_or_create_player()` (Zeile 621)
   - In `parse_substitution_entry()` (Zeile 2201-2203)
   - In `parse_goal_table()` (Zeile 2290-2291)

3. **Fehlertext-Präfixe entfernen**: `"FE, Lipponer"` → `"Lipponer"`
   - In `get_or_create_player()` (Zeile 637-640)
   - In `parse_substitution_entry()` (Zeile 2196-2199)
   - In `parse_goal_table()` (Zeile 2287-2288)

4. **"-" als Platzhalter erkennen**: `"-"` → wird als `None` behandelt
   - In `get_or_create_player()` (Zeile 617-619)
   - In `parse_goal_table()` (Zeile 2309-2311)

5. **Assist-Texte filtern** (NEU!): `"Liebers an Klopp"` → wird abgelehnt
   - In `get_or_create_player()` (Zeile 642-645)
   - Assist-Texte werden in `parse_goal_table()` aufgeteilt (Zeile 2302-2307)

### ✅ Team-Konsolidierung (automatisch beim Parsing)

**NEU**: Mainz-Team-Varianten werden jetzt **automatisch beim Parsing** normalisiert:

- `"1. Mainzer FC Hassia 05"` → `"1. FSV Mainz 05"`
- `"1. Mainzer FSV 05"` → `"1. FSV Mainz 05"`
- `"Reichsbahn TSV Mainz 05"` → `"1. FSV Mainz 05"`
- `"Reichsbahn-TSV Mainz 05"` → `"1. FSV Mainz 05"` (NEU!)
- etc.

Dies passiert in `get_or_create_team()` (Zeile 487-510).

### ✅ Assist-Text-Aufteilung (NEU!)

Assist-Texte werden jetzt korrekt aufgeteilt:
- `"FE an Becker"` → `"Becker"` (nur der Teil nach "an")
- `"Liebers an Klopp"` → `"Klopp"`

Dies passiert in `parse_goal_table()` (Zeile 2302-2307).

## Was NICHT automatisch passiert

### ❌ Bereinigung bestehender Daten

Die automatischen Verbesserungen gelten nur für **neue Parsings**. Bestehende Daten in der Datenbank werden **nicht automatisch** bereinigt.

Für bestehende Daten müssen separate Scripts ausgeführt werden:
- `consolidate_all_mainz_teams.py` - Team-Konsolidierung
- `scripts/clean_player_names.py` - Spielernamen-Bereinigung

## Zusammenfassung

| Verbesserung | Automatisch beim Parsing? | Für bestehende Daten? |
|--------------|---------------------------|------------------------|
| "?" entfernen | ✅ Ja | ❌ Nein (Script nötig) |
| "wdh." entfernen | ✅ Ja | ✅ Ja (wird neu geparst) |
| "FE,", "ET," entfernen | ✅ Ja | ✅ Ja (wird neu geparst) |
| Assist-Texte filtern | ✅ Ja (neu!) | ✅ Ja (wird neu geparst) |
| Team-Konsolidierung | ✅ Ja | ❌ Nein (Script nötig) |

## Empfehlung

Nach einem vollständigen Re-Parse sollten keine neuen Probleme entstehen. Bestehende Daten können mit den Cleanup-Scripts bereinigt werden.

