-- KORRIGIERTE QUERY für Nachspielzeit-Tore

-- Problem: Die ursprüngliche Query verwendet nur `minute > 90`
-- Viele Nachspielzeit-Tore werden aber als `minute = 90` mit `stoppage > 0` gespeichert

-- Option 1: Explizit beide Fälle abfragen
SELECT COUNT(*) AS nachspielzeit_tore_70er
FROM public.goals g
JOIN public.matches m ON g.match_id = m.match_id
JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
JOIN public.seasons s ON sc.season_id = s.season_id
WHERE s.start_year BETWEEN 1970 AND 2020
  AND (g.minute > 90 OR (g.minute = 90 AND g.stoppage > 0))
LIMIT 200;

-- Option 2: Berechnete Gesamtminute verwenden
SELECT COUNT(*) AS nachspielzeit_tore_70er
FROM public.goals g
JOIN public.matches m ON g.match_id = m.match_id
JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
JOIN public.seasons s ON sc.season_id = s.season_id
WHERE s.start_year BETWEEN 1970 AND 2020
  AND (g.minute + COALESCE(g.stoppage, 0)) > 90
LIMIT 200;

-- Ergebnis: 42 Tore statt nur 15 Tore
-- Aufteilung:
--   - 15 Tore nach der 90. Minute (minute > 90)
--   - 27 Tore in der 90. Minute + Nachspielzeit (minute = 90 AND stoppage > 0)


