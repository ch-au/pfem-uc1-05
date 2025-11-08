-- PROBLEM IDENTIFIZIERT:
-- "FSV" (team_id 31) hat 652 Bundesliga-Spiele
-- "1. FSV Mainz 05" (team_id 1) hat 0 Bundesliga-Spiele
-- 
-- Die Query filtert nur nach team_id = 1, aber die Bundesliga-Spiele sind mit team_id = 31 verknüpft!

-- KORRIGIERTE QUERY: Berücksichtigt alle Mainz-Team-Varianten inkl. "FSV"
SELECT 
    c.name as wettbewerb,
    COUNT(DISTINCT s.season_id) as saisonen_teilgenommen,
    COUNT(m.match_id) as spiele_gesamt,
    SUM(CASE 
        WHEN (m.home_team_id IN (SELECT team_id FROM teams WHERE name LIKE '%Mainz%' AND name LIKE '%05%')
              OR m.home_team_id IN (SELECT team_id FROM teams WHERE name = 'FSV'))
              AND m.home_score > m.away_score
          OR (m.away_team_id IN (SELECT team_id FROM teams WHERE name LIKE '%Mainz%' AND name LIKE '%05%')
              OR m.away_team_id IN (SELECT team_id FROM teams WHERE name = 'FSV'))
              AND m.away_score > m.home_score
        THEN 1 ELSE 0 
    END) as siege,
    SUM(CASE 
        WHEN m.home_score = m.away_score 
        THEN 1 ELSE 0 
    END) as unentschieden,
    SUM(CASE 
        WHEN (m.home_team_id IN (SELECT team_id FROM teams WHERE name LIKE '%Mainz%' AND name LIKE '%05%')
              OR m.home_team_id IN (SELECT team_id FROM teams WHERE name = 'FSV'))
              AND m.home_score < m.away_score
          OR (m.away_team_id IN (SELECT team_id FROM teams WHERE name LIKE '%Mainz%' AND name LIKE '%05%')
              OR m.away_team_id IN (SELECT team_id FROM teams WHERE name = 'FSV'))
              AND m.away_score < m.home_score
        THEN 1 ELSE 0 
    END) as niederlagen,
    ROUND(
        100.0 * SUM(CASE 
            WHEN (m.home_team_id IN (SELECT team_id FROM teams WHERE name LIKE '%Mainz%' AND name LIKE '%05%')
                  OR m.home_team_id IN (SELECT team_id FROM teams WHERE name = 'FSV'))
                  AND m.home_score > m.away_score
              OR (m.away_team_id IN (SELECT team_id FROM teams WHERE name LIKE '%Mainz%' AND name LIKE '%05%')
                  OR m.away_team_id IN (SELECT team_id FROM teams WHERE name = 'FSV'))
                  AND m.away_score > m.home_score
            THEN 1 ELSE 0 
        END) / NULLIF(COUNT(m.match_id), 0),
        1
    ) as siegquote_prozent
FROM public.competitions c
JOIN public.season_competitions sc ON c.competition_id = sc.competition_id
LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
    AND (m.home_team_id IN (SELECT team_id FROM teams WHERE name LIKE '%Mainz%' AND name LIKE '%05%')
         OR m.away_team_id IN (SELECT team_id FROM teams WHERE name LIKE '%Mainz%' AND name LIKE '%05%')
         OR m.home_team_id IN (SELECT team_id FROM teams WHERE name = 'FSV')
         OR m.away_team_id IN (SELECT team_id FROM teams WHERE name = 'FSV'))
JOIN public.seasons s ON sc.season_id = s.season_id
GROUP BY c.name
HAVING COUNT(m.match_id) > 0
ORDER BY spiele_gesamt DESC;

-- BESSERE LÖSUNG: Mit CTE für alle Mainz-Team-IDs
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
    SUM(CASE 
        WHEN m.home_score = m.away_score 
        THEN 1 ELSE 0 
    END) as unentschieden,
    SUM(CASE 
        WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) 
              AND m.home_score < m.away_score) 
          OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) 
              AND m.away_score < m.home_score) 
        THEN 1 ELSE 0 
    END) as niederlagen,
    ROUND(
        100.0 * SUM(CASE 
            WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) 
                  AND m.home_score > m.away_score) 
              OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) 
                  AND m.away_score > m.home_score) 
            THEN 1 ELSE 0 
        END) / NULLIF(COUNT(m.match_id), 0),
        1
    ) as siegquote_prozent
FROM public.competitions c
JOIN public.season_competitions sc ON c.competition_id = sc.competition_id
LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
    AND (m.home_team_id IN (SELECT team_id FROM mainz_team_ids)
         OR m.away_team_id IN (SELECT team_id FROM mainz_team_ids))
JOIN public.seasons s ON sc.season_id = s.season_id
GROUP BY c.name
HAVING COUNT(m.match_id) > 0
ORDER BY spiele_gesamt DESC;
