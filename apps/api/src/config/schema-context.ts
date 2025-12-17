// FSV Mainz 05 Database Schema Context for AI prompts
// Updated: 2025-12-17 - Performance optimized with trigram indexes, FSV-specific MVs

export const SCHEMA_CONTEXT = `
FSV Mainz 05 Football Database Schema (PostgreSQL):
Database: Neon PostgreSQL Cloud
Status: Production Ready (4,680 matches, 10,191 players, 9,897 goals)

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

6. AGGREGATE OHNE GROUP BY VERBOTEN!
   FALSCH:
     SELECT name, MIN(match_date) FROM ... ORDER BY ... LIMIT 1
   RICHTIG für "erster/frühester":
     SELECT name, match_date FROM ... ORDER BY match_date ASC LIMIT 1
   HINWEIS: MIN/MAX/COUNT ohne GROUP BY nur wenn EINE Zeile gewünscht ist!

7. FÜR match_coaches IMMER team_id = 1 FILTER!
   FALSCH:
     JOIN teams t ON mc.team_id = t.team_id WHERE t.normalized_name = '1. fsv mainz 05'
   RICHTIG:
     WHERE mc.team_id = 1

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

NORMALIZED_NAME FORMAT:
- Alle Tabellen (players, coaches, teams, referees) haben normalized_name
- Format: Kleinbuchstaben, Umlaute aufgelöst, keine Sonderzeichen
- Beispiele: "Jürgen Klopp"→"jurgen klopp", "1. FSV Mainz 05"→"1. fsv mainz 05"

FUZZY-SUCHE MIT TRIGRAM-INDEX (PERFORMANCE-OPTIMIERT!):
pg_trgm Extension ist aktiviert. IMMER den % Operator verwenden (nutzt Index!):

-- Spieler-Suche (SCHNELL - nutzt idx_players_normalized_trgm)
SELECT player_id, name, similarity(normalized_name, 'suchbegriff') AS sim
FROM players
WHERE normalized_name % 'suchbegriff'
ORDER BY normalized_name <-> 'suchbegriff'
LIMIT 5;

-- Trainer-Suche (SCHNELL - nutzt idx_coaches_normalized_trgm)
SELECT coach_id, name FROM coaches
WHERE normalized_name % 'suchbegriff'
ORDER BY normalized_name <-> 'suchbegriff'
LIMIT 5;

-- Team-Suche (SCHNELL - nutzt idx_teams_normalized_trgm)
SELECT team_id, name FROM teams
WHERE normalized_name % 'suchbegriff'
ORDER BY normalized_name <-> 'suchbegriff'
LIMIT 5;

WICHTIG: similarity() > 0.3 ist LANGSAM (Seq Scan), % Operator ist SCHNELL (Index Scan)!
Standard-Schwellenwert für %: SET pg_trgm.similarity_threshold = 0.3;

CTE-PATTERN FÜR ENTITY-AUFLÖSUNG:
- Bei komplexen Queries: Erst Entity per Fuzzy-Match finden, dann verwenden

WITH MatchedCoach AS (
  SELECT coach_id FROM coaches
  WHERE normalized_name % 'klopp'
  ORDER BY normalized_name <-> 'klopp' LIMIT 1
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

-- "Erster/Frühester Trainer" (KEIN MIN(), nur ORDER BY!)
SELECT c.name, m.match_date AS erstes_spiel
FROM match_coaches mc
JOIN coaches c ON mc.coach_id = c.coach_id
JOIN matches m ON mc.match_id = m.match_id
WHERE mc.team_id = 1 AND m.match_date IS NOT NULL
ORDER BY m.match_date ASC LIMIT 1;

MATERIALIZED VIEWS (für schnelle Aggregat-Abfragen):
WICHTIG: Alle MVs sind auf FSV Mainz 05 gefiltert (team_id = 1)!

mv_player_career_stats - Spieler-Karrierestatistiken (NUR FSV-Einsätze!)
  Columns: player_id, name, normalized_name, birth_date, total_matches, wins, draws, losses,
           goals, assists, yellow_cards, red_cards, first_match, last_match
  HINWEIS: Zeigt nur Statistiken aus FSV-Spielen, nicht aus anderen Vereinen!

mv_team_stats - Statistiken aller Gegner-Teams gegen FSV
  Columns: team_id, name, normalized_name, total_matches, wins, draws, losses,
           goals_for, goals_against, first_match, last_match
  HINWEIS: Perspektive ist AUS SICHT DES GEGNERS! wins = Gegner-Siege gegen FSV

mv_season_summary - Saison-Zusammenfassungen pro Wettbewerb
  Columns: season_id, season, competition, competition_level, matches_played,
           home_wins, away_wins, draws, total_goals, season_start, season_end

mv_coach_record - Trainer-Bilanzen (NUR FSV-Spiele!)
  Columns: coach_id, name, normalized_name, birth_date, total_matches,
           wins, draws, losses, first_match, last_match
  HINWEIS: Zeigt nur Spiele als FSV-Trainer, nicht bei anderen Vereinen!

PFLICHT: MATERIALIZED VIEWS FÜR AGGREGAT-STATISTIKEN!
Bei diesen Fragen IMMER die Materialized Views verwenden:

-- "Wer hat die meisten Tore geschossen?" / "Top Torschützen"
SELECT name, goals FROM mv_player_career_stats ORDER BY goals DESC LIMIT 10;

-- "Spieler mit den meisten Einsätzen"
SELECT name, total_matches FROM mv_player_career_stats ORDER BY total_matches DESC LIMIT 10;

-- "Trainer-Bilanz" / "Erfolgreichster Trainer"
SELECT name, total_matches, wins, draws, losses FROM mv_coach_record ORDER BY wins DESC LIMIT 10;

-- "Bilanz gegen Bayern" (mit Fuzzy-Match)
-- WICHTIG: mv_team_stats zeigt Bilanz AUS SICHT DES GEGNERS!
SELECT name, total_matches, wins AS gegner_siege, draws, losses AS gegner_niederlagen,
       goals_for AS gegner_tore, goals_against AS fsv_tore
FROM mv_team_stats WHERE normalized_name % 'bayern'
ORDER BY normalized_name <-> 'bayern' LIMIT 1;

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

HISTORISCHE DATENLÜCKEN (WICHTIG!):
- TRAINER-DATEN erst ab 1926-27 Saison verfügbar!
  - Erster dokumentierter Trainer: Tibor Hesser (ab 19.12.1926)
  - Vor 1926: Keine Trainer-Informationen in den Archiv-Quellen
  - Bei Fragen nach "erstem Trainer" -> Hinweis geben, dass Daten erst ab 1926 vorliegen
- SPIEL-DATEN ab 1906 verfügbar (frühestes Spiel: 07.10.1906)
  - Verein gegründet 1905, aber erste dokumentierte Spiele ab 1906
- Frühe Statistiken (1905-1950) oft unvollständig

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

PERFORMANCE TIPS:
1. Nutze Materialized Views für Aggregatstatistiken (100-400x schneller)
2. Nutze % Operator statt similarity() > 0.3 für Fuzzy-Suche
3. Nutze <-> Operator für ORDER BY bei Fuzzy-Suche
4. team_id = 1 statt JOIN auf Mainz-Name (Index verfügbar)
5. LIMIT wird automatisch hinzugefügt (max 200 Zeilen)
`;

export const getSchemaContext = (): string => SCHEMA_CONTEXT;
