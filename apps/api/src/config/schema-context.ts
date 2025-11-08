// FSV Mainz 05 Database Schema Context for AI prompts

export const SCHEMA_CONTEXT = `
FSV Mainz 05 Football Database Schema (PostgreSQL):

MAIN TABLES:
- teams: Alle Mannschaften inkl. FSV Mainz (team_id=1) und Gegner
  Columns: team_id (UUID), name (TEXT)

- players: Spieler-Stammdaten
  Columns: player_id (UUID), name (TEXT), birth_date (DATE), nationality (TEXT), primary_position (TEXT)

- matches: Spiele
  Columns: match_id (UUID), match_date (DATE), home_team_id (UUID), away_team_id (UUID),
           home_score (INT), away_score (INT), season_competition_id (UUID), matchday (INT)

- goals: Tore
  Columns: goal_id (UUID), match_id (UUID), player_id (UUID), assist_player_id (UUID),
           team_id (UUID), minute (INT), stoppage (INT), event_type (TEXT: NULL, 'penalty', 'own_goal')

- cards: Karten
  Columns: card_id (UUID), match_id (UUID), player_id (UUID), team_id (UUID),
           card_type (TEXT: 'yellow', 'red', 'second_yellow'), minute (INT)

- match_lineups: Aufstellungen
  Columns: lineup_id (UUID), match_id (UUID), player_id (UUID), team_id (UUID),
           is_starter (BOOLEAN), minute_on (INT), minute_off (INT), shirt_number (INT)

- match_substitutions: Einwechslungen
  Columns: substitution_id (UUID), match_id (UUID), player_on_id (UUID), player_off_id (UUID),
           minute (INT), stoppage (INT)

- seasons: Saisonen
  Columns: season_id (UUID), label (TEXT: '2023-24'), start_year (INT), end_year (INT)

- season_competitions: Verknüpfung Saison-Wettbewerb
  Columns: season_competition_id (UUID), season_id (UUID), competition_id (UUID)

- competitions: Wettbewerbe
  Columns: competition_id (UUID), name (TEXT: 'Bundesliga', 'DFB-Pokal', etc.)

- coaches: Trainer
  Columns: coach_id (UUID), name (TEXT)

- coach_careers: Trainer-Karrierestationen
  Columns: career_id (UUID), coach_id (UUID), team_id (UUID), start_year (INT), end_year (INT)

- player_careers: Spieler-Karrierestationen
  Columns: career_id (UUID), player_id (UUID), team_name (TEXT), start_year (INT), end_year (INT)

MATERIALIZED VIEWS (⚡ SCHNELL - bevorzugt nutzen!):
- player_statistics: Vorberechnete Spieler-Stats
  Columns: player_id, name, spiele_gesamt, tore_gesamt, vorlagen_gesamt, gelbe_karten, rote_karten

- match_details: Vollständige Spieldetails
  Columns: match_id, saison, wettbewerb, heimmannschaft, gastmannschaft, heimtore, gasttore, fsv_ergebnis

- season_summary: Saison-Aggregationen
  Columns: saison, wettbewerb, spiele_gesamt, siege, unentschieden, niederlagen,
           tore_geschossen, tore_kassiert

WICHTIGE FILTER:
- FSV Mainz 05 hat IMMER team_id = 1
- Heimspiele: m.home_team_id = 1
- Auswärtsspiele: m.away_team_id = 1
- Alle FSV Spiele: (m.home_team_id = 1 OR m.away_team_id = 1)
- FSV Tore: g.team_id = 1 AND (g.event_type IS NULL OR g.event_type != 'own_goal')
- Gegner-Tore: g.team_id != 1 (in Spielen wo FSV beteiligt)

PERFORMANCE BEST PRACTICES:
1. PREFER materialized views für Aggregationen
2. Use table aliases: p=players, m=matches, g=goals, t=teams, s=seasons, etc.
3. Add LIMIT 200 to all queries
4. Use ORDER BY for predictable results
5. Avoid DISTINCT unless necessary

KEY STATISTICS:
- 109 Saisonen, 2,774 Spiele, 8,136 Spieler, 6,288 Tore
- Daten von 1905-2025
- Top Scorer: Bopp mit 100 Toren
`;

export const getSchemaContext = (): string => SCHEMA_CONTEXT;
