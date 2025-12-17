// FSV Mainz 05 Database Schema Context for AI prompts
// Updated: 2025-12-17 - Fixed data quality issues, enhanced MV guidance

export const SCHEMA_CONTEXT = `
FSV Mainz 05 Football Database Schema (PostgreSQL):
Database: Neon PostgreSQL Cloud
Status: ✅ Production Ready (4,680 matches, 10,191 players, 9,897 goals)

HAUPTTABELLEN:

1. teams (828 Zeilen)
   Columns: team_id (INT PK), name (TEXT UNIQUE), normalized_name (TEXT), team_type (TEXT), profile_url (TEXT), name_embedding (vector)
   WICHTIG: FSV Mainz 05 hat IMMER team_id = 1

2. players (10,191 Zeilen)
   Columns: player_id (INT PK), name (TEXT), normalized_name (TEXT), birth_date (TEXT),
            birth_place (TEXT), death_date (TEXT), height_cm (INT), weight_kg (INT), primary_position (TEXT),
            nationality (TEXT), profile_url (TEXT), image_url (TEXT), name_embedding (vector)
   NOTE: death_date ist für verstorbene Spieler verfügbar (72 Spieler haben Sterbedaten)

3. matches (4,680 Zeilen)
   Columns: match_id (INT PK), season_competition_id (INT FK), round_name (TEXT), matchday (INT),
            leg (INT), match_date (TEXT), kickoff_time (TEXT), venue (TEXT), attendance (INT),
            referee_id (INT FK), home_team_id (INT FK), away_team_id (INT FK),
            home_score (INT), away_score (INT), halftime_home (INT), halftime_away (INT),
            extra_time_home (INT), extra_time_away (INT), penalties_home (INT), penalties_away (INT),
            source_file (TEXT)

4. goals (9,897 Zeilen)
   Columns: goal_id (INT PK), match_id (INT FK), team_id (INT FK), player_id (INT FK),
            assist_player_id (INT FK), minute (INT), stoppage (INT), score_home (INT), score_away (INT),
            event_type (TEXT: 'goal', 'penalty', 'own_goal')

5. cards (5,765 Zeilen)
   Columns: card_id (INT PK), match_id (INT FK), team_id (INT FK), player_id (INT FK),
            minute (INT), stoppage (INT), card_type (TEXT: 'yellow', 'red', 'second_yellow')
   NOTE: Viele historische Karten haben minute = NULL

6. match_lineups (100,373 Zeilen)
   Columns: lineup_id (INT PK), match_id (INT FK), team_id (INT FK), player_id (INT FK),
            shirt_number (INT), is_starter (BOOLEAN), minute_on (INT), stoppage_on (INT),
            minute_off (INT), stoppage_off (INT)

7. match_substitutions (13,339 Zeilen)
   Columns: substitution_id (INT PK), match_id (INT FK), team_id (INT FK), player_on_id (INT FK),
            player_off_id (INT FK), minute (INT), stoppage (INT)

8. seasons (121 Zeilen: 1905-2026)
   Columns: season_id (INT PK), label (TEXT: '2023-24'), start_year (INT), end_year (INT), team_id (INT FK)

9. season_competitions
   Columns: season_competition_id (INT PK), season_id (INT FK), competition_id (INT FK),
            stage_label (TEXT), source_path (TEXT)

10. competitions (24 Zeilen)
    Columns: competition_id (INT PK), name (TEXT: 'Bundesliga', 'DFB-Pokal', etc.),
             normalized_name (TEXT), level (TEXT), gender (TEXT)

11. coaches (615 Zeilen)
    Columns: coach_id (INT PK), name (TEXT), normalized_name (TEXT), birth_date (TEXT),
             birth_place (TEXT), nationality (TEXT), profile_url (TEXT)

12. coach_careers
    Columns: career_id (INT PK), coach_id (INT FK), team_name (TEXT), start_date (TEXT),
             end_date (TEXT), role (TEXT)

13. match_coaches
    Columns: match_coach_id (INT PK), match_id (INT FK), team_id (INT FK), coach_id (INT FK), role (TEXT)

14. player_careers (7,527 Zeilen)
    Columns: career_id (INT PK), player_id (INT FK), team_name (TEXT),
             start_year (INT), end_year (INT), notes (TEXT)
    WICHTIG: Enthält Karriere-Stationen bei ANDEREN Vereinen (vor/nach Mainz)
    KEIN team_id! Nur team_name als Text-Feld verfügbar.

15. season_squads
    Columns: season_squad_id (INT PK), season_competition_id (INT FK), player_id (INT FK),
             team_id (INT FK NOT NULL), position_group (TEXT), shirt_number (INT), status (TEXT), notes (TEXT)

16. referees (870 Zeilen)
    Columns: referee_id (INT PK), name (TEXT), normalized_name (TEXT), profile_url (TEXT)

17. match_referees
    Columns: match_referee_id (INT PK), match_id (INT FK), referee_id (INT FK), role (TEXT)

KRITISCH - KEINE FAKTEN RATEN!
- NIEMALS spezifische Werte raten (Spieltage, Ergebnisse, Daten)
- IMMER per ORDER BY + LIMIT abfragen statt WHERE mit geratenen Werten
- Falsch: WHERE m.matchday = 27 AND m.home_score = 0 AND m.away_score = 6
- Richtig: ORDER BY tordifferenz DESC LIMIT 1 (findet höchste Niederlage)
- Bei "höchste Niederlage": Nicht raten "0:6", sondern sortieren nach Tordifferenz
- Bei "Spiel gegen X": Nicht Spieltag raten, sondern alle Spiele gegen X abfragen
- Bei "wann war...": Nicht Datum raten, sondern mit ORDER BY finden

SQL ANTI-PATTERNS - NIEMALS SO!

1. MAINZ IMMER MIT team_id = 1, NICHT PER JOIN SUCHEN!
   FALSCH:
     JOIN teams t_mainz ON t_mainz.normalized_name = '1. fsv mainz 05'
     WHERE m.home_team_id = t_mainz.team_id
   RICHTIG:
     WHERE m.home_team_id = 1 OR m.away_team_id = 1

2. KEINE UNBENUTZTEN CTEs!
   FALSCH:
     WITH MatchedTeam AS (SELECT ... FROM teams)  -- wird nie verwendet!
     SELECT ... FROM matches ...
   RICHTIG:
     Jede CTE MUSS im Hauptquery referenziert werden

3. KEINE KARTESISCHEN PRODUKTE!
   FALSCH:
     JOIN teams t ON t.normalized_name = '...'  -- keine Verbindung zu anderen Tabellen
   RICHTIG:
     JOIN teams t ON m.home_team_id = t.team_id  -- verbunden mit matches

4. KEINE UNBENUTZTEN JOINS!
   FALSCH:
     JOIN competitions c ON ...  -- c wird nie in SELECT/WHERE verwendet
   RICHTIG:
     Nur Tabellen joinen die auch benutzt werden

5. IMMER WHERE-FILTER FÜR MAINZ-SPIELE!
   FALSCH:
     SELECT ... FROM matches m  -- gibt ALLE Spiele zurück
   RICHTIG:
     SELECT ... FROM matches m WHERE m.home_team_id = 1 OR m.away_team_id = 1

QUERY-STRATEGIE:
1. Explorative Queries statt exakte Matches
2. ORDER BY + LIMIT für "größte/erste/letzte" Fragen
3. Aggregationen (COUNT, MAX, MIN) für Statistik-Fragen
4. Nur WHERE mit exakten Werten wenn User diese explizit nennt
5. Minimale JOINs - nur was wirklich gebraucht wird
6. team_id = 1 statt JOIN auf Mainz-Name

WICHTIGE FILTER:
- FSV Mainz 05 hat IMMER team_id = 1
- Heimspiele: m.home_team_id = 1
- Auswärtsspiele: m.away_team_id = 1
- Alle FSV Spiele: (m.home_team_id = 1 OR m.away_team_id = 1)
- FSV Tore: g.team_id = 1 AND (g.event_type IS NULL OR g.event_type != 'own_goal')
- Gegentore: g.team_id != 1 (in Spielen wo FSV beteiligt ist)
- Eigentore: g.event_type = 'own_goal'
- Elfmetertore: g.event_type = 'penalty'

PFLICHTSPIELE vs FREUNDSCHAFTSSPIELE:
- Standardmäßig NUR Pflichtspiele (Bundesliga, DFB-Pokal, 2. Bundesliga, etc.)
- Filter: JOIN competitions c ON ... WHERE c.name != 'Freundschaftsspiele'
- Freundschaftsspiele nur inkludieren wenn explizit angefragt

WETTBEWERBS-NAMEN (competitions.name):
- Aktuelle: 'Bundesliga', '2. Bundesliga', 'DFB-Pokal', 'Europapokal'
- Freundschaftsspiele: 'Freundschaftsspiele'
- Historisch: 'Oberliga Südwest', 'Regionalliga Südwest', 'Amateur-Oberliga Südwest'
- Für "nur Liga-Spiele": c.name IN ('Bundesliga', '2. Bundesliga')

FSV SIEG/UNENTSCHIEDEN/NIEDERLAGE BERECHNUNG:
- FSV Sieg (Heimspiel): m.home_team_id = 1 AND m.home_score > m.away_score
- FSV Sieg (Auswärts): m.away_team_id = 1 AND m.away_score > m.home_score
- Unentschieden: m.home_score = m.away_score
- FSV Niederlage: Umkehrung der Sieg-Logik

Beispiel für Sieg-Zählung:
  SELECT
    SUM(CASE WHEN (m.home_team_id = 1 AND m.home_score > m.away_score)
               OR (m.away_team_id = 1 AND m.away_score > m.home_score) THEN 1 ELSE 0 END) AS siege,
    SUM(CASE WHEN m.home_score = m.away_score THEN 1 ELSE 0 END) AS unentschieden,
    SUM(CASE WHEN (m.home_team_id = 1 AND m.home_score < m.away_score)
               OR (m.away_team_id = 1 AND m.away_score < m.home_score) THEN 1 ELSE 0 END) AS niederlagen
  FROM matches m WHERE m.home_team_id = 1 OR m.away_team_id = 1;

NORMALIZED_NAME FORMAT:
- Alle Tabellen (players, coaches, teams, referees) haben normalized_name
- Format: Kleinbuchstaben, Umlaute aufgelöst, keine Sonderzeichen
- Umwandlung: ü→u, ö→o, ä→a, ß→ss, é→e, è→e, ç→c, etc.
- Beispiele: "Jürgen Klopp"→"jurgen klopp", "1. FSV Mainz 05"→"1. fsv mainz 05"

FUZZY SUCHE FÜR ALLE ENTITÄTEN (WICHTIG!):
- Benutzer können Namen falsch schreiben! IMMER Fuzzy-Matching verwenden.
- pg_trgm Extension ist aktiviert für Trigram-Similarity

Spieler-Suche (players):
  SELECT player_id, name, similarity(normalized_name, 'suchbegriff') AS sim
  FROM players
  WHERE normalized_name ILIKE '%suchbegriff%'
     OR similarity(normalized_name, 'suchbegriff') > 0.3
     OR similarity(SUBSTRING(normalized_name FROM '([^ ]+)$'), 'suchbegriff') > 0.5
  ORDER BY sim DESC LIMIT 5;

Trainer-Suche (coaches):
  SELECT coach_id, name, similarity(normalized_name, 'suchbegriff') AS sim
  FROM coaches
  WHERE normalized_name ILIKE '%suchbegriff%'
     OR similarity(normalized_name, 'suchbegriff') > 0.3
     OR similarity(SUBSTRING(normalized_name FROM '([^ ]+)$'), 'suchbegriff') > 0.5
  ORDER BY sim DESC LIMIT 5;

Team-Suche (teams):
  SELECT team_id, name, similarity(normalized_name, 'suchbegriff') AS sim
  FROM teams
  WHERE normalized_name ILIKE '%suchbegriff%'
     OR similarity(normalized_name, 'suchbegriff') > 0.3
  ORDER BY sim DESC LIMIT 5;

CTE-PATTERN FÜR ENTITY-AUFLÖSUNG:
- Bei komplexen Queries: Erst Entity per Fuzzy-Match finden, dann verwenden
- Beispiel mit Trainer:
  WITH MatchedCoach AS (
    SELECT coach_id FROM coaches
    WHERE normalized_name ILIKE '%klopp%'
       OR similarity(normalized_name, 'klopp') > 0.3
    ORDER BY similarity(normalized_name, 'klopp') DESC LIMIT 1
  )
  SELECT ... FROM matches m
  JOIN match_coaches mc ON m.match_id = mc.match_id
  WHERE mc.coach_id = (SELECT coach_id FROM MatchedCoach)
    AND mc.team_id = 1;

TRAINER-DATEN (match_coaches):
- match_coaches verknüpft Trainer mit einzelnen Spielen
- Wichtig: mc.team_id = 1 für FSV Mainz 05 Trainer filtern
- coach_careers enthält Karriere-Stationen (start_date, end_date, role)
- mv_coach_record enthält aggregierte Trainer-Bilanzen (schneller!)

SPIELER-EINSÄTZE UND DEBÜTS:
- match_lineups enthält alle Spielereinsätze pro Spiel
- Erstes Spiel eines Spielers für FSV: MIN(match_date) WHERE team_id = 1
- is_starter = true → Startelfeinsatz, false → Einwechslung
- minute_on/minute_off für Ein-/Auswechselzeiten

KOMPLEXE QUERY-PATTERNS MIT CTEs:

-- Pattern 1: Entity per Fuzzy-Match finden und verwenden
WITH MatchedEntity AS (
  SELECT entity_id FROM entity_table
  WHERE similarity(normalized_name, 'suchbegriff') > 0.3
  ORDER BY similarity(normalized_name, 'suchbegriff') DESC LIMIT 1
),
-- Pattern 2: Spiele unter bestimmten Bedingungen filtern
FilteredMatches AS (
  SELECT m.match_id, m.match_date, m.home_score, m.away_score
  FROM matches m
  WHERE /* Bedingungen */
),
-- Pattern 3: Aggregationen pro Spieler/Team/etc.
Aggregations AS (
  SELECT player_id, COUNT(*) AS anzahl, MIN(match_date) AS erstes_spiel
  FROM match_lineups ml
  JOIN FilteredMatches fm ON ml.match_id = fm.match_id
  GROUP BY player_id
)
SELECT ... FROM Aggregations ...;

-- Spieler-Debüt unter bestimmtem Trainer
WITH MatchedCoach AS (
  SELECT coach_id FROM coaches
  WHERE similarity(normalized_name, 'trainername') > 0.3
  ORDER BY similarity(normalized_name, 'trainername') DESC LIMIT 1
),
TrainerSpiele AS (
  SELECT m.match_id, m.match_date
  FROM matches m
  JOIN match_coaches mc ON m.match_id = mc.match_id
  WHERE mc.coach_id = (SELECT coach_id FROM MatchedCoach)
    AND mc.team_id = 1
),
SpielerErstesSpielGesamt AS (
  SELECT player_id, MIN(m.match_date) AS erstes_spiel
  FROM match_lineups ml
  JOIN matches m ON ml.match_id = m.match_id
  WHERE ml.team_id = 1
  GROUP BY player_id
)
SELECT p.name, ts.match_date AS debut_datum
FROM match_lineups ml
JOIN TrainerSpiele ts ON ml.match_id = ts.match_id
JOIN players p ON ml.player_id = p.player_id
JOIN SpielerErstesSpielGesamt seg ON ml.player_id = seg.player_id
WHERE ml.team_id = 1 AND ts.match_date = seg.erstes_spiel
GROUP BY p.player_id, p.name, ts.match_date
ORDER BY ts.match_date;

-- Tore eines Spielers (mit Fuzzy-Match)
WITH MatchedPlayer AS (
  SELECT player_id FROM players
  WHERE similarity(normalized_name, 'spielername') > 0.3
  ORDER BY similarity(normalized_name, 'spielername') DESC LIMIT 1
)
SELECT p.name, COUNT(g.goal_id) AS tore
FROM goals g
JOIN players p ON g.player_id = p.player_id
WHERE g.player_id = (SELECT player_id FROM MatchedPlayer)
  AND g.team_id = 1 AND (g.event_type IS NULL OR g.event_type != 'own_goal')
GROUP BY p.player_id, p.name;

-- Spiele gegen ein bestimmtes Team (mit Fuzzy-Match)
WITH MatchedTeam AS (
  SELECT team_id FROM teams
  WHERE similarity(normalized_name, 'teamname') > 0.3
  ORDER BY similarity(normalized_name, 'teamname') DESC LIMIT 1
)
SELECT m.match_date, t_home.name AS heim, t_away.name AS auswaerts,
       m.home_score || ':' || m.away_score AS ergebnis
FROM matches m
JOIN teams t_home ON m.home_team_id = t_home.team_id
JOIN teams t_away ON m.away_team_id = t_away.team_id
WHERE (m.home_team_id = 1 AND m.away_team_id = (SELECT team_id FROM MatchedTeam))
   OR (m.away_team_id = 1 AND m.home_team_id = (SELECT team_id FROM MatchedTeam))
ORDER BY m.match_date DESC;

BEISPIEL-QUERIES (EXPLORATIV - KEINE GERATENEN WERTE!):

-- Höchste Niederlage einer Saison (NICHT: WHERE score = '0:6')
SELECT m.match_date, t_home.name AS heim, t_away.name AS auswaerts,
       m.home_score || ':' || m.away_score AS ergebnis,
       CASE WHEN m.home_team_id = 1 THEN m.away_score - m.home_score
            ELSE m.home_score - m.away_score END AS gegentore_differenz
FROM matches m
JOIN teams t_home ON m.home_team_id = t_home.team_id
JOIN teams t_away ON m.away_team_id = t_away.team_id
JOIN season_competitions sc ON m.season_competition_id = sc.season_competition_id
JOIN seasons s ON sc.season_id = s.season_id
WHERE (m.home_team_id = 1 OR m.away_team_id = 1) AND s.label = '2022-23'
  AND ((m.home_team_id = 1 AND m.home_score < m.away_score)
       OR (m.away_team_id = 1 AND m.away_score < m.home_score))
ORDER BY gegentore_differenz DESC LIMIT 3;

-- Alle Spiele gegen ein Team (NICHT: WHERE matchday = 27)
WITH MatchedTeam AS (
  SELECT team_id FROM teams
  WHERE similarity(normalized_name, 'bayern') > 0.3
  ORDER BY similarity(normalized_name, 'bayern') DESC LIMIT 1
)
SELECT m.match_date, s.label AS saison, m.matchday AS spieltag,
       t_home.name AS heim, t_away.name AS auswaerts,
       m.home_score || ':' || m.away_score AS ergebnis
FROM matches m
JOIN teams t_home ON m.home_team_id = t_home.team_id
JOIN teams t_away ON m.away_team_id = t_away.team_id
JOIN season_competitions sc ON m.season_competition_id = sc.season_competition_id
JOIN seasons s ON sc.season_id = s.season_id
WHERE (m.home_team_id = 1 OR m.away_team_id = 1)
  AND (m.home_team_id = (SELECT team_id FROM MatchedTeam)
       OR m.away_team_id = (SELECT team_id FROM MatchedTeam))
ORDER BY m.match_date DESC;

-- Top Torschützen (IMMER Materialized View verwenden!)
SELECT name, goals AS tore FROM mv_player_career_stats ORDER BY goals DESC LIMIT 10;

-- Trainer-Bilanz (IMMER Materialized View verwenden!)
SELECT name, total_matches AS spiele, wins AS siege, draws AS unentschieden, losses AS niederlagen
FROM mv_coach_record
WHERE similarity(normalized_name, 'klopp') > 0.3
ORDER BY similarity(normalized_name, 'klopp') DESC LIMIT 1;

-- Erstes/Letztes Spiel eines Spielers (ORDER BY statt WHERE date = 'x')
WITH MatchedPlayer AS (
  SELECT player_id FROM players
  WHERE similarity(normalized_name, 'spielername') > 0.3
  ORDER BY similarity(normalized_name, 'spielername') DESC LIMIT 1
)
SELECT p.name, m.match_date, t_home.name || ' vs ' || t_away.name AS spiel
FROM match_lineups ml
JOIN matches m ON ml.match_id = m.match_id
JOIN players p ON ml.player_id = p.player_id
JOIN teams t_home ON m.home_team_id = t_home.team_id
JOIN teams t_away ON m.away_team_id = t_away.team_id
WHERE ml.player_id = (SELECT player_id FROM MatchedPlayer) AND ml.team_id = 1
ORDER BY m.match_date ASC LIMIT 1; -- ASC für erstes, DESC für letztes

MATERIALIZED VIEWS (für schnelle Aggregat-Abfragen):

mv_player_career_stats - Spieler-Karrierestatistiken
  Columns: player_id, name, normalized_name, birth_date, total_matches, wins, draws, losses,
           goals, assists, yellow_cards, red_cards, first_match, last_match

mv_team_stats - Statistiken aller Teams gegen FSV
  Columns: team_id, name, normalized_name, total_matches, wins, draws, losses,
           goals_for, goals_against, first_match, last_match

mv_season_summary - Saison-Zusammenfassungen pro Wettbewerb
  Columns: season_id, season, competition, competition_level, matches_played,
           home_wins, away_wins, draws, total_goals, season_start, season_end

mv_coach_record - Trainer-Bilanzen
  Columns: coach_id, name, normalized_name, birth_date, total_matches,
           wins, draws, losses, first_match, last_match

PERFORMANCE TIPS:
1. Nutze Materialized Views für Aggregatstatistiken (100-400x schneller)
2. Nutze WITH (CTEs) für komplexe Abfragen
3. Verwende Tabellenaliase: p=players, m=matches, g=goals, t=teams, s=seasons, c=competitions
4. JOIN-Reihenfolge: Von kleinsten zu größten Tabellen
5. LIMIT wird automatisch hinzugefügt (max 200 Zeilen)
6. Nutze WHERE-Filter vor JOINs wenn möglich

PFLICHT: MATERIALIZED VIEWS FÜR AGGREGAT-STATISTIKEN!
Bei diesen Fragen IMMER die Materialized Views verwenden (konsistente, schnelle Ergebnisse):

-- "Wer hat die meisten Tore geschossen?" / "Top Torschützen"
SELECT name, goals FROM mv_player_career_stats ORDER BY goals DESC LIMIT 10;

-- "Spieler mit den meisten Einsätzen"
SELECT name, total_matches FROM mv_player_career_stats ORDER BY total_matches DESC LIMIT 10;

-- "Spieler mit den meisten Gelben Karten"
SELECT name, yellow_cards FROM mv_player_career_stats ORDER BY yellow_cards DESC LIMIT 10;

-- "Trainer-Bilanz" / "Erfolgreichster Trainer"
SELECT name, total_matches, wins, draws, losses FROM mv_coach_record ORDER BY wins DESC LIMIT 10;

-- "Gegen welches Team hat Mainz am häufigsten gespielt?"
SELECT name, total_matches FROM mv_team_stats ORDER BY total_matches DESC LIMIT 10;

-- "Bilanz gegen Bayern" (mit Fuzzy-Match)
-- WICHTIG: mv_team_stats zeigt Bilanz AUS SICHT DES GEGNERS!
-- wins = Siege des Gegners gegen FSV, losses = Niederlagen des Gegners gegen FSV
SELECT name, total_matches, wins AS gegner_siege, draws, losses AS gegner_niederlagen,
       goals_for AS gegner_tore, goals_against AS fsv_tore
FROM mv_team_stats WHERE similarity(normalized_name, 'bayern') > 0.3
ORDER BY similarity(normalized_name, 'bayern') DESC LIMIT 1;

-- "Top Vorlagengeber / Meiste Assists"
SELECT name, assists FROM mv_player_career_stats ORDER BY assists DESC LIMIT 10;

-- "Meiste Rote Karten"
SELECT name, red_cards FROM mv_player_career_stats ORDER BY red_cards DESC LIMIT 10;

-- "Spieler mit meisten Siegen"
SELECT name, wins, total_matches FROM mv_player_career_stats ORDER BY wins DESC LIMIT 10;

-- "Saison-Übersicht / Wie lief die Saison?"
SELECT season, competition, matches_played, home_wins, away_wins, draws, total_goals
FROM mv_season_summary WHERE season = '2023-24' ORDER BY competition;

-- NUR BUNDESLIGA-SPIELE (ohne Pokal, Freundschaftsspiele etc.)
SELECT m.match_date, m.home_score, m.away_score
FROM matches m
JOIN season_competitions sc ON m.season_competition_id = sc.season_competition_id
JOIN competitions c ON sc.competition_id = c.competition_id
WHERE (m.home_team_id = 1 OR m.away_team_id = 1)
  AND c.name = 'Bundesliga'
ORDER BY m.match_date DESC LIMIT 10;

NIEMALS für diese Aggregat-Fragen direkt aus goals/cards/match_lineups aggregieren!

SPIELER-KARRIEREN (player_careers):
Enthält Karriere-Stationen von Spielern bei ANDEREN Vereinen (vor/nach Mainz).
WICHTIG: KEIN team_id in dieser Tabelle! Nur team_name als Text.

-- "Welche Spieler haben auch bei Bayern gespielt?"
SELECT DISTINCT p.name, p.birth_date, p.death_date,
       pc.team_name AS station, pc.start_year, pc.end_year
FROM players p
JOIN player_careers pc ON p.player_id = pc.player_id
WHERE pc.team_name ILIKE '%bayern m%'
ORDER BY p.name;

-- "Spieler die auch bei [Team] gespielt haben" (allgemein)
SELECT DISTINCT p.name, pc.team_name, pc.start_year, pc.end_year
FROM players p
JOIN player_careers pc_mainz ON p.player_id = pc_mainz.player_id
JOIN player_careers pc_other ON p.player_id = pc_other.player_id
WHERE pc_mainz.team_name ILIKE '%mainz%'
  AND pc_other.team_name ILIKE '%[team-suche]%'
ORDER BY p.name;

-- "Verstorbene Spieler"
SELECT name, birth_date, death_date, birth_place
FROM players
WHERE death_date IS NOT NULL
ORDER BY death_date DESC LIMIT 20;

DATEN-LIMITIERUNGEN:
- Datenbank enthält NUR FSV Mainz 05 Spiele und Statistiken
- player_careers enthält Karriere-Stationen bei anderen Vereinen (7.527 Einträge)
- Keine Nationalmannschafts-Daten
- Bei Fragen nach "erfolgreicher Karriere" → player_careers abfragen

HISTORISCHE DATENLÜCKEN (WICHTIG!):
- TRAINER-DATEN erst ab 1926-27 Saison verfügbar!
  - Erster dokumentierter Trainer: Tibor Hesser (ab 19.12.1926)
  - Vor 1926: Keine Trainer-Informationen in den Archiv-Quellen
  - 1.797 Spiele haben keinen Trainer-Eintrag
  - Bei Fragen nach "erstem Trainer" → Hinweis geben, dass Daten erst ab 1926 vorliegen
- SPIEL-DATEN ab 1906 verfügbar (frühestes Spiel: 07.10.1906)
  - Verein gegründet 1905, aber erste dokumentierte Spiele ab 1906
- Frühe Statistiken (1905-1950) oft unvollständig:
  - Fehlende Aufstellungen, Torschützen, Minuten
  - Teilweise nur Ergebnisse dokumentiert

KEY STATISTICS:
- 121 Saisonen (1905-2026)
- 4,680 Spiele
- 10,191 Spieler (72 mit Sterbedaten)
- 9,897 Tore
- 5,765 Karten
- 100,373 Lineup-Einträge
- 7,527 Karriere-Stationen (player_careers)
- 828 Teams
- 615 Trainer
`;

export const getSchemaContext = (): string => SCHEMA_CONTEXT;
