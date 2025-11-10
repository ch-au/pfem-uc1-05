# Teams-Tabelle Konsolidierung - Zusammenfassung

## Problem

Die Datenbank enthielt **7 verschiedene Mainz-Team-Varianten**:
- team_id = 1: "1. FSV Mainz 05" (Haupt-Team)
- team_id = 3: "1. Mainzer FC Hassia 05"
- team_id = 5: "FC Viktoria 05 Mainz"
- team_id = 15: "1. Mainzer FC Hassia-Hermania 05"
- team_id = 17: "1. Mainzer FV 05"
- team_id = 20: "1. Mainzer FSV 05"
- team_id = 79: "Reichsbahn TSV Mainz 05"

**Problem**: Queries mit `team_id = 1` fanden nur einen kleinen Teil der Matches, da die meisten Matches anderen Mainz-Team-IDs zugeordnet waren.

## Lösung

**Script**: `consolidate_all_mainz_teams.py`

**Durchgeführte Aktionen**:
1. ✅ Alle 6 Mainz-Varianten zu `team_id = 1` konsolidiert
2. ✅ 203 Referenzen aktualisiert (105 home matches + 98 away matches)
3. ✅ 6 Duplikat-Teams gelöscht
4. ✅ Verifizierung: Nur noch 1 Mainz-Team (`team_id = 1`)

## Ergebnis

**Vorher**:
- 7 verschiedene Mainz-Teams
- Queries mit `team_id = 1` fanden nur 10 Matches
- Queries mussten alle Mainz-Varianten berücksichtigen

**Nachher**:
- ✅ Nur noch 1 Mainz-Team: `team_id = 1` = "1. FSV Mainz 05"
- ✅ Alle 213 Mainz-Matches verwenden jetzt `team_id = 1`
- ✅ Queries mit `team_id = 1` funktionieren korrekt
- ✅ Keine komplexen Subqueries mehr nötig

## Verwendung

Das Script kann bei Bedarf erneut ausgeführt werden:

```bash
# Dry-Run (zeigt was gemacht würde)
python consolidate_all_mainz_teams.py --dry-run

# Live (führt Konsolidierung durch)
python consolidate_all_mainz_teams.py
```

## Wichtig für zukünftige Queries

**✅ RICHTIG:**
```sql
WHERE m.home_team_id = 1 OR m.away_team_id = 1
```

**❌ NICHT MEHR NÖTIG:**
```sql
WHERE m.home_team_id IN (SELECT team_id FROM teams WHERE name ILIKE '%mainz%' ...)
```

Alle Mainz-Varianten sind jetzt konsolidiert zu `team_id = 1`!


