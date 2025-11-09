// FSV Mainz 05 Database Schema Context for AI prompts

export const SCHEMA_CONTEXT = `
FSV Mainz 05 Football Database Schema (PostgreSQL):

MAIN TABLES:
- teams: Alle Mannschaften inkl. FSV Mainz (team_id=1) und Gegner
  Columns: team_id (INT), name (TEXT), normalized_name (TEXT), team_type (TEXT)

- players: Spieler-Stammdaten
  Columns: player_id (INT), name (TEXT), normalized_name (TEXT), birth_date (DATE), 
           birth_place (TEXT), height_cm (INT), weight_kg (INT), primary_position (TEXT), nationality (TEXT)

- matches: Spiele
  Columns: match_id (INT), season_competition_id (INT), match_date (DATE), 
           home_team_id (INT), away_team_id (INT), home_score (INT), away_score (INT),
           halftime_home (INT), halftime_away (INT), matchday (INT), round_name (TEXT),
           venue (TEXT), attendance (INT), referee_id (INT)

- goals: Tore
  Columns: goal_id (INT), match_id (INT), player_id (INT), assist_player_id (INT),
           team_id (INT), minute (INT), stoppage (INT), score_home (INT), score_away (INT),
           event_type (TEXT: NULL, 'penalty', 'own_goal')

- cards: Karten
  Columns: card_id (INT), match_id (INT), player_id (INT), team_id (INT),
           card_type (TEXT: 'yellow', 'red', 'second_yellow'), minute (INT)

- match_lineups: Aufstellungen
  Columns: lineup_id (INT), match_id (INT), player_id (INT), team_id (INT),
           is_starter (BOOLEAN), minute_on (INT), minute_off (INT), shirt_number (INT)

- match_substitutions: Einwechslungen
  Columns: substitution_id (INT), match_id (INT), player_on_id (INT), player_off_id (INT),
           minute (INT), stoppage (INT)

- seasons: Saisonen
  Columns: season_id (INT), label (TEXT: '2023-24'), start_year (INT), end_year (INT), team_id (INT)

- season_competitions: Verknüpfung Saison-Wettbewerb
  Columns: season_competition_id (INT), season_id (INT), competition_id (INT)

- competitions: Wettbewerbe
  Columns: competition_id (INT), name (TEXT: 'Bundesliga', 'DFB-Pokal', etc.)

- coaches: Trainer
  Columns: coach_id (INT), name (TEXT), normalized_name (TEXT)

- coach_careers: Trainer-Karrierestationen
  Columns: career_id (INT), coach_id (INT), team_name (TEXT), start_date (TEXT), end_date (TEXT), role (TEXT)

- player_careers: Spieler-Karrierestationen
  Columns: career_id (INT), player_id (INT), team_name (TEXT), start_year (INT), end_year (INT), team_id (INT)

WICHTIGE FILTER:
- FSV Mainz 05 hat IMMER team_id = 1
- Heimspiele: m.home_team_id = 1
- Auswärtsspiele: m.away_team_id = 1
- Alle FSV Spiele: (m.home_team_id = 1 OR m.away_team_id = 1)
- FSV Tore: g.team_id = 1 AND (g.event_type IS NULL OR g.event_type != 'own_goal')
- Gegner-Tore: g.team_id != 1 (in Spielen wo FSV beteiligt)

PERFORMANCE BEST PRACTICES:
1. Use JOINs efficiently for aggregations
2. Use table aliases: p=players, m=matches, g=goals, t=teams, s=seasons, etc.
3. Add LIMIT 200 to all queries
4. Use ORDER BY for predictable results
5. Avoid DISTINCT unless necessary
6. Use WHERE filters before JOINs when possible

KEY STATISTICS:
- 109 Saisonen, 2,774 Spiele, 8,136 Spieler, 6,288 Tore
- Daten von 1905-2025
- Top Scorer: Bopp mit 100 Toren
`;

export const getSchemaContext = (): string => SCHEMA_CONTEXT;
