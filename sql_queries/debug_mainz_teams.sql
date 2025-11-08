-- ============================================================================
-- DEBUG: Welche Mainz-Team-IDs werden gefunden?
-- ============================================================================
-- Diese Query zeigt alle Mainz-Team-Varianten und wie viele Spiele sie haben
-- Führe diese zuerst aus, um zu sehen, welche team_ids verwendet werden sollten

SELECT 
    t.team_id,
    t.name,
    t.normalized_name,
    COUNT(DISTINCT CASE WHEN m.home_team_id = t.team_id THEN m.match_id END) AS heimspiele,
    COUNT(DISTINCT CASE WHEN m.away_team_id = t.team_id THEN m.match_id END) AS auswaertsspiele,
    COUNT(DISTINCT m.match_id) AS spiele_gesamt,
    COUNT(DISTINCT CASE 
        WHEN c.name = 'Bundesliga' THEN m.match_id 
    END) AS bundesliga_spiele
FROM public.teams t
LEFT JOIN public.matches m ON (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
LEFT JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
LEFT JOIN public.competitions c ON sc.competition_id = c.competition_id
WHERE (t.normalized_name LIKE '%mainz%' OR t.name ILIKE '%mainz%')
   OR (t.name ILIKE '%fsv%' AND (t.name ILIKE '%05%' OR t.name ILIKE '%mainz%'))
   OR t.name = 'FSV'
GROUP BY t.team_id, t.name, t.normalized_name
ORDER BY spiele_gesamt DESC;

-- ============================================================================
-- DEBUG: Welche Wettbewerbe haben Spiele mit Mainz-Teams?
-- ============================================================================
SELECT 
    c.name AS wettbewerb,
    COUNT(DISTINCT m.match_id) AS spiele_gesamt,
    COUNT(DISTINCT CASE WHEN m.home_team_id IN (
        SELECT team_id FROM public.teams 
        WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
           OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
           OR name = 'FSV'
    ) THEN m.match_id END) AS heimspiele,
    COUNT(DISTINCT CASE WHEN m.away_team_id IN (
        SELECT team_id FROM public.teams 
        WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
           OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
           OR name = 'FSV'
    ) THEN m.match_id END) AS auswaertsspiele
FROM public.competitions c
LEFT JOIN public.season_competitions sc ON c.competition_id = sc.competition_id
LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
    AND (m.home_team_id IN (
        SELECT team_id FROM public.teams 
        WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
           OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
           OR name = 'FSV'
    ) OR m.away_team_id IN (
        SELECT team_id FROM public.teams 
        WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
           OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
           OR name = 'FSV'
    ))
GROUP BY c.name
HAVING COUNT(DISTINCT m.match_id) > 0
ORDER BY spiele_gesamt DESC;

