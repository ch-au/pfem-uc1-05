-- ============================================================================
-- DEBUG: Prüfe Europapokal-Spiele für Mainz 05 in Saison 2018-19
-- ============================================================================
-- Diese Query zeigt alle Europapokal-Spiele von Mainz 05 in der Saison 2018-19
-- um zu prüfen, ob die Daten vollständig sind

WITH mainz_team_ids AS (
    SELECT team_id 
    FROM public.teams 
    WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
       OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
       OR name = 'FSV'
)
SELECT 
    s.label AS saison,
    c.name AS wettbewerb,
    m.match_date AS datum,
    t_home.name AS heimmannschaft,
    t_away.name AS gastmannschaft,
    m.home_score AS tore_heim,
    m.away_score AS tore_gast,
    CASE 
        WHEN m.home_team_id IN (SELECT team_id FROM mainz_team_ids) THEN 'Heim'
        WHEN m.away_team_id IN (SELECT team_id FROM mainz_team_ids) THEN 'Auswärts'
        ELSE 'Unbekannt'
    END AS spielort,
    CASE 
        WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.home_score > m.away_score)
          OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.away_score > m.home_score)
        THEN 'Sieg'
        WHEN m.home_score = m.away_score THEN 'Unentschieden'
        ELSE 'Niederlage'
    END AS ergebnis,
    m.round_name AS runde,
    m.matchday AS spieltag
FROM public.matches m
JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
JOIN public.seasons s ON sc.season_id = s.season_id
JOIN public.competitions c ON sc.competition_id = c.competition_id
JOIN public.teams t_home ON m.home_team_id = t_home.team_id
JOIN public.teams t_away ON m.away_team_id = t_away.team_id
WHERE (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) 
    OR m.away_team_id IN (SELECT team_id FROM mainz_team_ids))
  AND s.label = '2018-19'
  AND c.name = 'Europapokal'
  AND m.home_score IS NOT NULL 
  AND m.away_score IS NOT NULL
ORDER BY m.match_date, m.matchday;

-- ============================================================================
-- DEBUG: Prüfe alle Wettbewerbe für Mainz 05 in Saison 2018-19
-- ============================================================================
WITH mainz_team_ids AS (
    SELECT team_id 
    FROM public.teams 
    WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
       OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
       OR name = 'FSV'
)
SELECT 
    c.name AS wettbewerb,
    COUNT(*) AS spiele_gesamt,
    COUNT(DISTINCT m.match_date) AS verschiedene_spieltage,
    MIN(m.match_date) AS erstes_spiel,
    MAX(m.match_date) AS letztes_spiel,
    STRING_AGG(DISTINCT m.round_name, ', ' ORDER BY m.round_name) AS runden
FROM public.matches m
JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
JOIN public.seasons s ON sc.season_id = s.season_id
JOIN public.competitions c ON sc.competition_id = c.competition_id
WHERE (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) 
    OR m.away_team_id IN (SELECT team_id FROM mainz_team_ids))
  AND s.label = '2018-19'
  AND m.home_score IS NOT NULL 
  AND m.away_score IS NOT NULL
GROUP BY c.name
ORDER BY spiele_gesamt DESC;

