-- KORRIGIERTES QUERY: Wettbewerbs-Statistiken für FSV Mainz 05
-- Problem: Es gibt mehrere Team-Varianten für FSV Mainz (team_id 1, 20, etc.)
-- Lösung: Verwende alle Mainz-Team-IDs oder finde die richtige

-- OPTION 1: Verwende alle Mainz-Team-Varianten (empfohlen)
SELECT 
    c.name as wettbewerb,
    COUNT(DISTINCT s.season_id) as saisonen_teilgenommen,
    COUNT(m.match_id) as spiele_gesamt,
    SUM(CASE 
        WHEN (m.home_team_id IN (1, 20, 3, 5, 15, 17, 79) AND m.home_score > m.away_score) 
          OR (m.away_team_id IN (1, 20, 3, 5, 15, 17, 79) AND m.away_score > m.home_score) 
        THEN 1 ELSE 0 
    END) as siege,
    SUM(CASE 
        WHEN m.home_score = m.away_score 
          AND (m.home_team_id IN (1, 20, 3, 5, 15, 17, 79) OR m.away_team_id IN (1, 20, 3, 5, 15, 17, 79))
        THEN 1 ELSE 0 
    END) as unentschieden,
    SUM(CASE 
        WHEN (m.home_team_id IN (1, 20, 3, 5, 15, 17, 79) AND m.home_score < m.away_score) 
          OR (m.away_team_id IN (1, 20, 3, 5, 15, 17, 79) AND m.away_score < m.home_score) 
        THEN 1 ELSE 0 
    END) as niederlagen,
    ROUND(
        100.0 * SUM(CASE 
            WHEN (m.home_team_id IN (1, 20, 3, 5, 15, 17, 79) AND m.home_score > m.away_score) 
              OR (m.away_team_id IN (1, 20, 3, 5, 15, 17, 79) AND m.away_score > m.home_score) 
            THEN 1 ELSE 0 
        END) / NULLIF(COUNT(m.match_id), 0),
        1
    ) as siegquote_prozent
FROM public.competitions c
JOIN public.season_competitions sc ON c.competition_id = sc.competition_id
LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
    AND (m.home_team_id IN (1, 20, 3, 5, 15, 17, 79) OR m.away_team_id IN (1, 20, 3, 5, 15, 17, 79))
JOIN public.seasons s ON sc.season_id = s.season_id
GROUP BY c.name
HAVING COUNT(m.match_id) > 0
ORDER BY spiele_gesamt DESC;

-- OPTION 2: Dynamisch alle Mainz-Teams finden (besser)
SELECT 
    c.name as wettbewerb,
    COUNT(DISTINCT s.season_id) as saisonen_teilgenommen,
    COUNT(m.match_id) as spiele_gesamt,
    SUM(CASE 
        WHEN (m.home_team_id IN (SELECT team_id FROM public.teams WHERE name ILIKE '%mainz%' AND (name ILIKE '%05%' OR name ILIKE '%fsv%')) AND m.home_score > m.away_score) 
          OR (m.away_team_id IN (SELECT team_id FROM public.teams WHERE name ILIKE '%mainz%' AND (name ILIKE '%05%' OR name ILIKE '%fsv%')) AND m.away_score > m.home_score) 
        THEN 1 ELSE 0 
    END) as siege,
    SUM(CASE 
        WHEN m.home_score = m.away_score 
          AND (m.home_team_id IN (SELECT team_id FROM public.teams WHERE name ILIKE '%mainz%' AND (name ILIKE '%05%' OR name ILIKE '%fsv%')) 
               OR m.away_team_id IN (SELECT team_id FROM public.teams WHERE name ILIKE '%mainz%' AND (name ILIKE '%05%' OR name ILIKE '%fsv%')))
        THEN 1 ELSE 0 
    END) as unentschieden,
    SUM(CASE 
        WHEN (m.home_team_id IN (SELECT team_id FROM public.teams WHERE name ILIKE '%mainz%' AND (name ILIKE '%05%' OR name ILIKE '%fsv%')) AND m.home_score < m.away_score) 
          OR (m.away_team_id IN (SELECT team_id FROM public.teams WHERE name ILIKE '%mainz%' AND (name ILIKE '%05%' OR name ILIKE '%fsv%')) AND m.away_score < m.home_score) 
        THEN 1 ELSE 0 
    END) as niederlagen,
    ROUND(
        100.0 * SUM(CASE 
            WHEN (m.home_team_id IN (SELECT team_id FROM public.teams WHERE name ILIKE '%mainz%' AND (name ILIKE '%05%' OR name ILIKE '%fsv%')) AND m.home_score > m.away_score) 
              OR (m.away_team_id IN (SELECT team_id FROM public.teams WHERE name ILIKE '%mainz%' AND (name ILIKE '%05%' OR name ILIKE '%fsv%')) AND m.away_score > m.home_score) 
            THEN 1 ELSE 0 
        END) / NULLIF(COUNT(m.match_id), 0),
        1
    ) as siegquote_prozent
FROM public.competitions c
JOIN public.season_competitions sc ON c.competition_id = sc.competition_id
LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
    AND (m.home_team_id IN (SELECT team_id FROM public.teams WHERE name ILIKE '%mainz%' AND (name ILIKE '%05%' OR name ILIKE '%fsv%'))
         OR m.away_team_id IN (SELECT team_id FROM public.teams WHERE name ILIKE '%mainz%' AND (name ILIKE '%05%' OR name ILIKE '%fsv%')))
JOIN public.seasons s ON sc.season_id = s.season_id
GROUP BY c.name
HAVING COUNT(m.match_id) > 0
ORDER BY spiele_gesamt DESC;


