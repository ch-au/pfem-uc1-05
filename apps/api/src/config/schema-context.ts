// FSV Mainz 05 Database Schema Context for AI prompts
// Updated: 2025-12-12 - Synced with actual PostgreSQL database

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
            birth_place (TEXT), height_cm (INT), weight_kg (INT), primary_position (TEXT),
            nationality (TEXT), profile_url (TEXT), image_url (TEXT), name_embedding (vector)

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

14. player_careers
    Columns: career_id (INT PK), player_id (INT FK), team_name (TEXT), team_id (INT FK),
             start_year (INT), end_year (INT), notes (TEXT)

15. season_squads
    Columns: season_squad_id (INT PK), season_competition_id (INT FK), player_id (INT FK),
             team_id (INT FK NOT NULL), position_group (TEXT), shirt_number (INT), status (TEXT), notes (TEXT)

16. referees (870 Zeilen)
    Columns: referee_id (INT PK), name (TEXT), normalized_name (TEXT), profile_url (TEXT)

17. match_referees
    Columns: match_referee_id (INT PK), match_id (INT FK), referee_id (INT FK), role (TEXT)

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
- competitions.name Werte: 'Bundesliga', '2. Bundesliga', 'DFB-Pokal', 'Freundschaftsspiele', etc.

TEAM-NAMEN SUCHE:
- NIEMALS exakte Matches (=) für Team-Namen verwenden!
- IMMER ILIKE mit Wildcards für robuste Suche:
  WHERE t.name ILIKE '%mainz%' OR t.normalized_name ILIKE '%mainz%'
  WHERE t.name ILIKE '%bayern%' OR t.normalized_name ILIKE '%bayern%'
- Beispiel normalized_name Werte:
  - '1. fsv mainz 05' (mit Punkt nach der 1!)
  - 'fc bayern munchen' (ohne Umlaut, lowercase)
  - 'borussia dortmund'
  - 'vfb stuttgart'
- Bei Spielen gegen bestimmte Teams:
  WHERE (t_home.name ILIKE '%bayern%' OR t_away.name ILIKE '%bayern%')

SPIELER-NAMEN FUZZY SUCHE:
- pg_trgm Extension aktiviert für Trigram-Similarity
- Kombiniere ILIKE und Trigram für beste Ergebnisse:
  WHERE p.normalized_name ILIKE '%suchname%'
     OR similarity(p.normalized_name, 'suchname') > 0.3
     OR similarity(SUBSTRING(p.normalized_name FROM '([^ ]+)$'), 'suchname') > 0.3
  ORDER BY GREATEST(
    similarity(p.normalized_name, 'suchname'),
    similarity(SUBSTRING(p.normalized_name FROM '([^ ]+)$'), 'suchname')
  ) DESC
- ILIKE findet exakte Substring-Matches
- Trigram mit Nachnamen-Extraktion findet z.B. "MICHAEL THURK" bei Typo "Turk"

BEISPIEL-QUERIES:

-- Top Torschützen aller Zeiten
SELECT p.name, COUNT(g.goal_id) AS tore
FROM goals g
JOIN players p ON g.player_id = p.player_id
WHERE g.team_id = 1 AND (g.event_type IS NULL OR g.event_type != 'own_goal')
GROUP BY p.player_id, p.name
ORDER BY tore DESC
LIMIT 10;

-- Mainz Bundesliga-Siege in Saison 2023-24
SELECT m.match_date, 
       CASE WHEN m.home_team_id = 1 THEN t_away.name ELSE t_home.name END AS gegner,
       CASE WHEN m.home_team_id = 1 THEN m.home_score || ':' || m.away_score 
            ELSE m.away_score || ':' || m.home_score END AS ergebnis
FROM matches m
JOIN season_competitions sc ON m.season_competition_id = sc.season_competition_id
JOIN seasons s ON sc.season_id = s.season_id
JOIN competitions c ON sc.competition_id = c.competition_id
JOIN teams t_home ON m.home_team_id = t_home.team_id
JOIN teams t_away ON m.away_team_id = t_away.team_id
WHERE (m.home_team_id = 1 OR m.away_team_id = 1)
  AND c.name = 'Bundesliga'
  AND s.label = '2023-24'
  AND ((m.home_team_id = 1 AND m.home_score > m.away_score) 
       OR (m.away_team_id = 1 AND m.away_score > m.home_score))
ORDER BY m.match_date;

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

KEY STATISTICS:
- 121 Saisonen (1905-2026)
- 4,680 Spiele
- 10,191 Spieler
- 9,897 Tore
- 5,765 Karten
- 100,373 Lineup-Einträge
- 828 Teams
- 615 Trainer
`;

export const getSchemaContext = (): string => SCHEMA_CONTEXT;
