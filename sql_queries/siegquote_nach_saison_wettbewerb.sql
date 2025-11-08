-- ============================================================================
-- SIEGQUOTE VON MAINZ 05 NACH SAISON UND WETTBEWERB
-- ============================================================================
-- 
-- Diese Abfrage zeigt eine Übersicht über die Leistung von Mainz 05
-- gruppiert nach Saison und Wettbewerb.
--
-- Ausgabe:
-- - Saison (z.B. "2023-24")
-- - Wettbewerb (Bundesliga, DFB-Pokal, Europapokal)
-- - Anzahl Spiele gesamt
-- - Anzahl Siege
-- - Anzahl Unentschieden  
-- - Anzahl Niederlagen
-- - Siegquote in Prozent
-- - Gesamtpunkte (3 für Sieg, 1 für Unentschieden)
-- - Punkte pro Spiel
--
-- Verwendung:
-- 1. Direkt in PostgreSQL ausführen
-- 2. Oder über die API mit: "Zeige mir die Siegquote von Mainz 05 nach Saison und Wettbewerb"
--
-- TROUBLESHOOTING:
-- Falls die Bundesliga nicht erscheint:
-- 1. Führe zuerst debug_mainz_teams.sql aus, um zu sehen, welche team_ids verwendet werden
-- 2. Prüfe, ob "FSV" (team_id 31) oder andere Varianten existieren
-- 3. Falls nötig, verwende die alternative Version unten mit expliziten team_ids
--
-- WICHTIG: Falls ungewöhnliche Ergebnisse (z.B. 100% Siegquote im Europapokal):
-- 1. Führe debug_europapokal_2018_19.sql aus, um zu prüfen, welche Spiele erfasst sind
-- 2. Möglicherweise sind nicht alle Spiele geparst worden (nur Siege, nur Gruppenspiele, etc.)
-- 3. Prüfe die Datenqualität - es könnten Spiele fehlen
-- ============================================================================

WITH mainz_team_ids AS (
    -- Finde ALLE Mainz-Team-Varianten
    -- WICHTIG: Es gibt möglicherweise mehrere Varianten (team_id = 1, team_id = 31 "FSV", etc.)
    -- Laut Dokumentation sollten alle zu team_id = 1 konsolidiert sein, aber zur Sicherheit
    -- suchen wir nach allen Varianten
    SELECT team_id 
    FROM public.teams 
    WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
       OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
       OR name = 'FSV'  -- "FSV" allein kann auch Mainz 05 sein
    -- Fallback: Falls nichts gefunden wird, verwende team_id = 1 (laut Dokumentation)
    UNION ALL
    SELECT 1 AS team_id WHERE NOT EXISTS (
        SELECT 1 FROM public.teams 
        WHERE (normalized_name LIKE '%mainz%' OR name ILIKE '%mainz%')
           OR (name ILIKE '%fsv%' AND (name ILIKE '%05%' OR name ILIKE '%mainz%'))
           OR name = 'FSV'
    )
),
match_results AS (
    SELECT 
        s.label AS saison,
        c.name AS wettbewerb,
        m.match_id,
        -- Prüfe ob Mainz 05 gewonnen hat (prüfe gegen ALLE Mainz-Team-IDs)
        CASE 
            WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.home_score > m.away_score)
              OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.away_score > m.home_score)
            THEN 1 ELSE 0 
        END AS sieg,
        -- Prüfe ob Unentschieden
        CASE 
            WHEN m.home_score = m.away_score THEN 1 ELSE 0 
        END AS unentschieden,
        -- Prüfe ob Niederlage
        CASE 
            WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.home_score < m.away_score)
              OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.away_score < m.home_score)
            THEN 1 ELSE 0 
        END AS niederlage,
        -- Punkte berechnen (3 für Sieg, 1 für Unentschieden, 0 für Niederlage)
        CASE 
            WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.home_score > m.away_score)
              OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.away_score > m.home_score)
            THEN 3
            WHEN m.home_score = m.away_score THEN 1
            ELSE 0
        END AS punkte
    FROM public.matches m
    JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
    JOIN public.seasons s ON sc.season_id = s.season_id
    JOIN public.competitions c ON sc.competition_id = c.competition_id
    WHERE (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) 
        OR m.away_team_id IN (SELECT team_id FROM mainz_team_ids))
      AND m.home_score IS NOT NULL 
      AND m.away_score IS NOT NULL
      -- Hinweis: Freundschaftsspiele werden jetzt korrekt als "Freundschaftsspiele" klassifiziert
      -- Falls nur offizielle Wettbewerbsspiele gewünscht sind, kann hier gefiltert werden:
      -- AND c.name IN ('Bundesliga', 'DFB-Pokal', 'Europapokal')
)
SELECT 
    saison,
    wettbewerb,
    COUNT(*) AS spiele_gesamt,
    SUM(sieg) AS siege,
    SUM(unentschieden) AS unentschieden,
    SUM(niederlage) AS niederlagen,
    ROUND(
        100.0 * SUM(sieg) / NULLIF(COUNT(*), 0), 
        2
    ) AS siegquote_prozent,
    SUM(punkte) AS punkte_gesamt,
    ROUND(
        SUM(punkte)::numeric / NULLIF(COUNT(*), 0), 
        2
    ) AS punkte_pro_spiel
FROM match_results
GROUP BY saison, wettbewerb
ORDER BY 
    -- Sortiere nach Startjahr der Saison (neueste zuerst)
    CAST(SUBSTRING(saison FROM '^(\d{4})') AS INTEGER) DESC,
    wettbewerb;

-- ============================================================================
-- VARIANTE: Nur offizielle Wettbewerbsspiele (ohne Freundschaftsspiele)
-- ============================================================================
-- Falls nur offizielle Wettbewerbsspiele gewünscht sind, füge diese Zeile hinzu:
-- AND c.name IN ('Bundesliga', 'DFB-Pokal', 'Europapokal')
-- 
-- Oder verwende diese vollständige Variante:
--
-- [Gleiche Query wie oben, aber mit zusätzlichem Filter:]
-- WHERE ... AND c.name IN ('Bundesliga', 'DFB-Pokal', 'Europapokal')
-- ============================================================================
--
-- ALTERNATIVE: Vereinfachte Version mit bekannter team_id
-- ============================================================================
-- Falls die team_id von Mainz 05 bekannt ist (z.B. 1), kann diese Version verwendet werden:
--
-- WITH mainz_team_ids AS (
--     SELECT team_id FROM (VALUES (1), (31)) AS t(team_id)  -- Anpassen!
-- )
-- SELECT 
--     s.label AS saison,
--     c.name AS wettbewerb,
--     COUNT(*) AS spiele_gesamt,
--     SUM(CASE 
--         WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.home_score > m.away_score)
--           OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.away_score > m.home_score)
--         THEN 1 ELSE 0 
--     END) AS siege,
--     SUM(CASE WHEN m.home_score = m.away_score THEN 1 ELSE 0 END) AS unentschieden,
--     SUM(CASE 
--         WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.home_score < m.away_score)
--           OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.away_score < m.home_score)
--         THEN 1 ELSE 0 
--     END) AS niederlagen,
--     ROUND(100.0 * SUM(CASE 
--         WHEN (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.home_score > m.away_score)
--           OR (m.away_team_id IN (SELECT team_id FROM mainz_team_ids) AND m.away_score > m.home_score)
--         THEN 1 ELSE 0 
--     END) / NULLIF(COUNT(*), 0), 2) AS siegquote_prozent
-- FROM public.matches m
-- JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
-- JOIN public.seasons s ON sc.season_id = s.season_id
-- JOIN public.competitions c ON sc.competition_id = c.competition_id
-- WHERE (m.home_team_id IN (SELECT team_id FROM mainz_team_ids) 
--     OR m.away_team_id IN (SELECT team_id FROM mainz_team_ids))
--   AND m.home_score IS NOT NULL 
--   AND m.away_score IS NOT NULL
-- GROUP BY s.label, c.name
-- ORDER BY CAST(SUBSTRING(s.label FROM '^(\d{4})') AS INTEGER) DESC, c.name;
-- ============================================================================
