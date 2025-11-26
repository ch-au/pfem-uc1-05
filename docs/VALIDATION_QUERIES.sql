-- Validation Queries for FSV Mainz 05 Archive Database
-- After full parsing is complete

-- ================================================================
-- 1. Jürgen Klopp Spielerstatistiken
-- ================================================================

-- Wieviele Spiele hat Jürgen Klopp als Spieler gewonnen?
SELECT
    'Jürgen Klopp Statistiken (als Spieler)' as category,
    COUNT(DISTINCT m.match_id) as total_games,
    COUNT(DISTINCT CASE
        WHEN (t.team_id = m.home_team_id AND m.home_score > m.away_score)
          OR (t.team_id = m.away_team_id AND m.away_score > m.home_score)
        THEN m.match_id
    END) as wins,
    COUNT(DISTINCT CASE
        WHEN m.home_score = m.away_score THEN m.match_id
    END) as draws,
    COUNT(DISTINCT CASE
        WHEN (t.team_id = m.home_team_id AND m.home_score < m.away_score)
          OR (t.team_id = m.away_team_id AND m.away_score < m.home_score)
        THEN m.match_id
    END) as losses
FROM players p
JOIN match_lineups ml ON p.player_id = ml.player_id
JOIN matches m ON ml.match_id = m.match_id
JOIN teams t ON ml.team_id = t.team_id
WHERE p.name LIKE '%KLOPP%'
  AND t.name LIKE '%Mainz%'
  AND m.home_score IS NOT NULL
  AND m.away_score IS NOT NULL;

-- Detailierte Klopp Spiele (Auswahl)
SELECT
    m.match_date,
    m.home_team_name || ' vs ' || m.away_team_name as match,
    m.home_score || ':' || m.away_score as result,
    CASE
        WHEN ml.is_starter = 1 THEN 'Startelf'
        ELSE 'Einwechslung'
    END as einsatz,
    ml.minute_off as ausgewechselt
FROM players p
JOIN match_lineups ml ON p.player_id = ml.player_id
JOIN matches m ON ml.match_id = m.match_id
WHERE p.name LIKE '%KLOPP%'
  AND m.match_date IS NOT NULL
ORDER BY m.match_date
LIMIT 20;

-- ================================================================
-- 2. André Schürrle erstes Spiel
-- ================================================================

-- Wann war das erste Spiel von André Schürrle?
SELECT
    'André Schürrle - Erstes Spiel' as info,
    m.match_date as datum,
    m.home_team_name || ' ' || m.home_score || ':' || m.away_score || ' ' || m.away_team_name as spiel,
    m.competition_name as wettbewerb,
    CASE
        WHEN ml.is_starter = 1 THEN 'Startelf'
        ELSE 'Eingewechselt in Minute ' || ml.minute_on
    END as einsatz,
    ml.shirt_number as rueckennummer
FROM players p
JOIN match_lineups ml ON p.player_id = ml.player_id
JOIN matches m ON ml.match_id = m.match_id
WHERE p.name LIKE '%SCHÜRRLE%'
  AND m.match_date IS NOT NULL
ORDER BY m.match_date ASC
LIMIT 1;

-- Alle Schürrle Spiele
SELECT
    m.match_date,
    m.home_team_name || ' ' || COALESCE(CAST(m.home_score AS TEXT), '?') || ':' || COALESCE(CAST(m.away_score AS TEXT), '?') || ' ' || m.away_team_name as match,
    m.competition_name,
    CASE WHEN ml.is_starter = 1 THEN 'Start' ELSE 'Bank' END as position
FROM players p
JOIN match_lineups ml ON p.player_id = ml.player_id
JOIN matches m ON ml.match_id = m.match_id
WHERE p.name LIKE '%SCHÜRRLE%'
ORDER BY m.match_date;

-- ================================================================
-- 3. Spieler mit vollen Namen vs. nur Nachnamen
-- ================================================================

SELECT
    'Datenqualität: Spielernamen' as kategorie,
    COUNT(*) as gesamt_spieler,
    COUNT(CASE WHEN name LIKE '% %' THEN 1 END) as mit_vornamen,
    COUNT(CASE WHEN name NOT LIKE '% %' THEN 1 END) as nur_nachname,
    ROUND(100.0 * COUNT(CASE WHEN name LIKE '% %' THEN 1 END) / COUNT(*), 1) || '%' as prozent_vollstaendig
FROM players
WHERE name NOT LIKE 'Tor %'
  AND name NOT LIKE 'Die Aufstellung%';

-- ================================================================
-- 4. Top 10 Torschützen (mit vollen Namen)
-- ================================================================

SELECT
    p.name,
    COUNT(*) as tore,
    MIN(m.match_date) as erstes_tor,
    MAX(m.match_date) as letztes_tor
FROM goals g
JOIN players p ON g.player_id = p.player_id
JOIN matches m ON g.match_id = m.match_id
JOIN teams t ON g.team_id = t.team_id
WHERE t.name LIKE '%Mainz%'
  AND g.goal_type != 'own_goal'
GROUP BY p.player_id, p.name
ORDER BY tore DESC
LIMIT 10;

-- ================================================================
-- 5. Duplicate Players Check
-- ================================================================

-- Finde potenzielle Duplikate (gleicher Nachname)
SELECT
    SUBSTR(normalized_name, INSTR(normalized_name, ' ') + 1) as surname_normalized,
    COUNT(*) as count,
    GROUP_CONCAT(name, ' | ') as player_names
FROM players
WHERE name LIKE '% %'  -- Nur volle Namen
GROUP BY SUBSTR(normalized_name, INSTR(normalized_name, ' ') + 1)
HAVING COUNT(*) > 1
ORDER BY count DESC
LIMIT 20;

-- ================================================================
-- 6. Spieler mit meisten Einsätzen
-- ================================================================

SELECT
    p.name,
    COUNT(DISTINCT ml.match_id) as spiele,
    COUNT(CASE WHEN ml.is_starter = 1 THEN 1 END) as startelf,
    COUNT(CASE WHEN ml.is_starter = 0 THEN 1 END) as einwechslungen,
    MIN(m.match_date) as von,
    MAX(m.match_date) as bis
FROM players p
JOIN match_lineups ml ON p.player_id = ml.player_id
JOIN matches m ON ml.match_id = m.match_id
JOIN teams t ON ml.team_id = t.team_id
WHERE t.name LIKE '%Mainz%'
GROUP BY p.player_id, p.name
ORDER BY spiele DESC
LIMIT 15;

-- ================================================================
-- 7. Ungültige Spielernamen (Navigationselemente, etc.)
-- ================================================================

SELECT
    name,
    COUNT(DISTINCT ml.match_id) as erscheint_in_matches
FROM players p
LEFT JOIN match_lineups ml ON p.player_id = ml.player_id
WHERE name IN ('Übersicht', 'zurückblättern', 'weiterblättern', 'Hinspiel', 'Rückspiel')
   OR name LIKE 'Tor %'
   OR name LIKE 'Die Aufstellung%'
GROUP BY name
ORDER BY erscheint_in_matches DESC;

-- ================================================================
-- 8. Profile URL Coverage
-- ================================================================

SELECT
    'Profile URL Abdeckung' as kategorie,
    COUNT(*) as gesamt_spieler,
    COUNT(CASE WHEN profile_url IS NOT NULL THEN 1 END) as mit_profile_url,
    COUNT(CASE WHEN profile_url IS NULL THEN 1 END) as ohne_profile_url,
    ROUND(100.0 * COUNT(CASE WHEN profile_url IS NOT NULL THEN 1 END) / COUNT(*), 1) || '%' as prozent_mit_url
FROM players
WHERE name NOT LIKE 'Tor %'
  AND name NOT LIKE 'Die Aufstellung%';

-- ================================================================
-- 9. Matches per Competition
-- ================================================================

SELECT
    competition_name,
    COUNT(*) as anzahl_spiele,
    MIN(match_date) as erstes_spiel,
    MAX(match_date) as letztes_spiel
FROM matches
WHERE competition_name IS NOT NULL
GROUP BY competition_name
ORDER BY anzahl_spiele DESC;

-- ================================================================
-- 10. Saison mit den meisten Spielen
-- ================================================================

SELECT
    s.label as saison,
    COUNT(DISTINCT m.match_id) as spiele,
    s.start_year || '-' || s.end_year as jahre
FROM seasons s
LEFT JOIN matches m ON m.source_file LIKE s.label || '%'
GROUP BY s.season_id, s.label, s.start_year, s.end_year
ORDER BY spiele DESC
LIMIT 15;
