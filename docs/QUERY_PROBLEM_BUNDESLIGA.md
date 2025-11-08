# Problem: SQL Query zeigt keine Siege in der Bundesliga

## Problem identifiziert

Die ursprüngliche Query filterte nur nach `team_id = 1` ("1. FSV Mainz 05"), aber:
- **"FSV" (team_id 31)** hat 652 Bundesliga-Spiele
- **"1. FSV Mainz 05" (team_id 1)** hat 0 Bundesliga-Spiele

Das bedeutet, dass beim Parsing "FSV" als separates Team erstellt wurde und nicht mit "1. FSV Mainz 05" konsolidiert wurde.

## Lösung

### 1. Korrigierte Query (sofortige Lösung)

Die Query muss auch nach `team_id = 31` ("FSV") filtern:

```sql
WITH mainz_team_ids AS (
    SELECT team_id 
    FROM teams 
    WHERE name LIKE '%Mainz%' AND name LIKE '%05%'
       OR name = 'FSV'  -- "FSV" ist auch Mainz 05!
)
SELECT 
    c.name as wettbewerb,
    COUNT(DISTINCT s.season_id) as saisonen_teilgenommen,
    COUNT(m.match_id) as spiele_gesamt,
    SUM(CASE 
        WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) 
              AND m.home_score > m.away_score) 
          OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) 
              AND m.away_score > m.home_score) 
        THEN 1 ELSE 0 
    END) as siege,
    ...
```

Siehe `docs/KORRIGIERTE_QUERY_WETTBEWERB_STATS.sql` für die vollständige Query.

### 2. Langfristige Lösung: Team-Konsolidierung

Das Problem sollte beim nächsten Parse automatisch behoben werden, da der Parser jetzt "FSV" als Mainz-Team erkennt. Aber für die aktuelle Datenbank müssen wir "FSV" mit "1. FSV Mainz 05" konsolidieren.

**Option A: Manuelle Konsolidierung in Postgres**
```sql
-- Alle Referenzen von team_id 31 ("FSV") zu team_id 1 ("1. FSV Mainz 05") ändern
UPDATE matches SET home_team_id = 1 WHERE home_team_id = 31;
UPDATE matches SET away_team_id = 1 WHERE away_team_id = 31;
UPDATE goals SET team_id = 1 WHERE team_id = 31;
UPDATE match_lineups SET team_id = 1 WHERE team_id = 31;
-- etc.
DELETE FROM teams WHERE team_id = 31;
```

**Option B: Parser verbessern**
Der Parser sollte "FSV" allein als Mainz-Team erkennen, wenn es im Kontext von Mainz-Spielen verwendet wird.

## Fazit

✅ **Die Query ist nicht falsch**, aber sie filtert nicht nach allen Mainz-Team-Varianten.

✅ **Die korrigierte Query** berücksichtigt auch "FSV" (team_id 31) und zeigt jetzt die korrekten Statistiken.

⚠️ **Langfristig** sollte "FSV" mit "1. FSV Mainz 05" konsolidiert werden, um solche Probleme zu vermeiden.

