// FSV Mainz 05 Database Schema Context for AI prompts
// Updated: 2025-11-25 - Synced with actual PostgreSQL database

export const SCHEMA_CONTEXT = `
FSV Mainz 05 Football Database Schema (PostgreSQL):
Database: Neon PostgreSQL Cloud
Status: ✅ Production Ready (3,956 matches, 9,955 players, 8,312 goals)

HAUPTTABELLEN:

1. teams (585 Zeilen)
   Columns: team_id (INT PK), name (TEXT UNIQUE), normalized_name (TEXT), team_type (TEXT), profile_url (TEXT)
   WICHTIG: FSV Mainz 05 hat IMMER team_id = 1

2. players (9,955 Zeilen)
   Columns: player_id (INT PK), name (TEXT), normalized_name (TEXT), birth_date (DATE), 
            birth_place (TEXT), height_cm (INT), weight_kg (INT), primary_position (TEXT), 
            nationality (TEXT), profile_url (TEXT), image_url (TEXT)

3. matches (3,956 Zeilen - inkl. 668 historische Profirest-Spiele)
   Columns: match_id (INT PK), season_competition_id (INT FK), round_name (TEXT), matchday (INT),
            leg (INT), match_date (DATE), kickoff_time (TEXT), venue (TEXT), attendance (INT),
            referee_id (INT FK), home_team_id (INT FK), away_team_id (INT FK),
            home_score (INT), away_score (INT), halftime_home (INT), halftime_away (INT),
            extra_time_home (INT), extra_time_away (INT), penalties_home (INT), penalties_away (INT),
            source_file (TEXT)

4. goals (8,312 Zeilen)
   Columns: goal_id (INT PK), match_id (INT FK), team_id (INT FK), player_id (INT FK),
            assist_player_id (INT FK), minute (INT), stoppage (INT), score_home (INT), score_away (INT),
            event_type (TEXT: NULL, 'penalty', 'own_goal')

5. cards (5,768 Zeilen)
   Columns: card_id (INT PK), match_id (INT FK), team_id (INT FK), player_id (INT FK),
            minute (INT), stoppage (INT), card_type (TEXT: 'yellow', 'red', 'second_yellow')
   NOTE: 94.5% der Karten haben minute = NULL (historische Daten)

6. match_lineups (91,475 Zeilen)
   Columns: lineup_id (INT PK), match_id (INT FK), team_id (INT FK), player_id (INT FK),
            shirt_number (INT), is_starter (BOOLEAN), minute_on (INT), stoppage_on (INT),
            minute_off (INT), stoppage_off (INT)

7. match_substitutions (10,029 Zeilen)
   Columns: substitution_id (INT PK), match_id (INT FK), player_on_id (INT FK),
            player_off_id (INT FK), minute (INT), stoppage (INT)

8. seasons (121 Zeilen: 1905-2026)
   Columns: season_id (INT PK), label (TEXT: '2023-24'), start_year (INT), end_year (INT), team_id (INT FK)

9. season_competitions (175 Zeilen)
   Columns: season_competition_id (INT PK), season_id (INT FK), competition_id (INT FK),
            stage_label (TEXT), source_path (TEXT)

10. competitions (23 Zeilen)
    Columns: competition_id (INT PK), name (TEXT: 'Bundesliga', 'DFB-Pokal', etc.),
             normalized_name (TEXT), level (TEXT), gender (TEXT)

11. coaches (566 Zeilen)
    Columns: coach_id (INT PK), name (TEXT), normalized_name (TEXT), birth_date (DATE),
             birth_place (TEXT), nationality (TEXT), profile_url (TEXT)

12. coach_careers (522 Zeilen)
    Columns: career_id (INT PK), coach_id (INT FK), team_name (TEXT), start_date (TEXT),
             end_date (TEXT), role (TEXT)

13. match_coaches (2,832 Zeilen)
    Columns: match_coach_id (INT PK), match_id (INT FK), team_id (INT FK), coach_id (INT FK), role (TEXT)

14. player_careers (4,760 Zeilen)
    Columns: career_id (INT PK), player_id (INT FK), team_name (TEXT), team_id (INT FK),
             start_year (INT), end_year (INT), notes (TEXT)

15. season_squads (434 Zeilen)
    Columns: season_squad_id (INT PK), season_competition_id (INT FK), player_id (INT FK),
             team_id (INT FK NOT NULL), position_group (TEXT), shirt_number (INT), status (TEXT), notes (TEXT)

16. referees (870 Zeilen)
    Columns: referee_id (INT PK), name (TEXT), normalized_name (TEXT), profile_url (TEXT)

17. match_referees (2,879 Zeilen)
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

PERFORMANCE TIPS:
1. Nutze WITH (CTEs) für komplexe Abfragen
2. Verwende Tabellenaliase: p=players, m=matches, g=goals, t=teams, s=seasons, c=competitions
3. JOIN-Reihenfolge: Von kleinsten zu größten Tabellen
4. LIMIT wird automatisch hinzugefügt (max 200 Zeilen)
5. Nutze WHERE-Filter vor JOINs wenn möglich

WICHTIGE DATENTYP-HINWEISE:
- EXTRACT() nur mit DATE/TIMESTAMP Spalten verwenden, NICHT mit TEXT!
- DATE-Spalten: match_date (matches), birth_date (players, coaches)
- TEXT-Spalten (für Datumsvergleiche CAST verwenden): start_date/end_date (coach_careers), kickoff_time (matches)
- Für Jahre aus TEXT: Verwende SUBSTRING(start_date, 1, 4) oder WHERE start_date LIKE '2023%'
- Für Jahre aus DATE: Verwende EXTRACT(YEAR FROM match_date)

KEY STATISTICS:
- 121 Saisonen (1905-2026)
- 3,956 Spiele (inkl. 668 historische Profirest-Matches)
- 9,955 Spieler
- 8,312 Tore
- 5,768 Karten
- 91,475 Lineup-Einträge
- Top Scorer: Bopp mit 142 Toren
`;

export const getSchemaContext = (): string => SCHEMA_CONTEXT;
