# Datenbankschema

Dieses Dokument beschreibt die aktuell beabsichtigte Schemaform der aktiven Pipeline. Historische Row-Counts und alte Sync-Status-Snapshots werden bewusst nicht mitgefuehrt.

## Quellen der Wahrheit

- SQLite-Parsing-Schema: `parsing/comprehensive_fsv_parser.py`
- PostgreSQL-Basisschema: `database/001_create_schema.sql`
- PostgreSQL-Folgeaenderungen: `database/migrations/*.sql`
- Materialized Views: `database/002_materialized_views.sql` und `database/migrations/007_create_materialized_views.sql`

## Zentrale Fachtabellen

| Tabelle | Rolle |
|---------|-------|
| `teams` | FSV Mainz und alle Gegnerteams |
| `players` | Spieler-Stammdaten |
| `coaches` | Trainer-Stammdaten |
| `referees` | Schiedsrichter-Stammdaten |
| `competitions` | Wettbewerbs-Katalog |
| `seasons` | Saison-Katalog |
| `season_competitions` | Verknuepfung zwischen Saison und Wettbewerb |
| `matches` | Match-Header |
| `match_lineups` | Spielereinsaetze |
| `match_substitutions` | Wechselereignisse |
| `goals` | Toreignisse |
| `cards` | Kartenereignisse |
| `match_coaches` | Trainerzuordnungen |
| `match_referees` | Schiedsrichterzuordnungen |
| `season_squads` | Saisonkader-Snapshots |
| `player_careers` | Karriere-Metadaten fuer Spieler |
| `coach_careers` | Karriere-Metadaten fuer Trainer |
| `player_aliases` | Alternative Spielernamen |
| `match_notes` | Freitext-Notizen zu Spielen |
| `season_matchdays` | Tabellenstand-Snapshots pro Spieltag |

## Anwendungstabellen

Diese Tabellen werden ueber die SQL-Assets in `database/quiz_schema.sql` und `database/migrations/` gepflegt.

| Tabellenfamilie | Zweck |
|-----------------|-------|
| `quiz_*` | Quiz-Generierung und Spielbetrieb |
| `chat_*` | Chat-Historie und Metadaten |

## Embeddings

Das aktive Schema geht fuer `name_embedding`-Spalten von `vector(1024)` aus.

Betroffene Tabellen:

- `teams`
- `players`
- `coaches`

Relevante Fakten:

- `database/001_create_schema.sql` definiert `vector(1024)`
- `.env.example` und `config.py` verwenden standardmaessig 1024 Dimensionen zur Kompatibilitaet

## Repräsentative Definitionen

### `teams`

```sql
CREATE TABLE teams (
    team_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    normalized_name TEXT UNIQUE NOT NULL,
    team_type TEXT,
    profile_url TEXT,
    name_embedding vector(1024)
);
```

### `players`

```sql
CREATE TABLE players (
    player_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    normalized_name TEXT UNIQUE NOT NULL,
    birth_date TEXT,
    birth_place TEXT,
    height_cm INTEGER,
    weight_kg INTEGER,
    primary_position TEXT,
    nationality TEXT,
    profile_url TEXT,
    image_url TEXT,
    name_embedding vector(1024)
);
```

### `coaches`

```sql
CREATE TABLE coaches (
    coach_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    normalized_name TEXT UNIQUE NOT NULL,
    birth_date TEXT,
    birth_place TEXT,
    nationality TEXT,
    profile_url TEXT,
    name_embedding vector(1024)
);
```

### `matches`

```sql
CREATE TABLE matches (
    match_id SERIAL PRIMARY KEY,
    season_competition_id INTEGER REFERENCES season_competitions,
    round_name TEXT,
    matchday INTEGER,
    leg INTEGER,
    match_date TEXT,
    kickoff_time TEXT,
    venue TEXT,
    attendance INTEGER,
    referee_id INTEGER REFERENCES referees,
    home_team_id INTEGER REFERENCES teams,
    away_team_id INTEGER REFERENCES teams,
    home_score INTEGER,
    away_score INTEGER,
    halftime_home INTEGER,
    halftime_away INTEGER,
    extra_time_home INTEGER,
    extra_time_away INTEGER,
    penalties_home INTEGER,
    penalties_away INTEGER,
    source_file TEXT,
    UNIQUE (season_competition_id, source_file)
);
```

## Betriebshinweis

Falls Schemadokumentation und SQL-Dateien auseinanderlaufen, gelten die SQL-Dateien und der aktive Code als massgeblich. Dieses Dokument sollte dann sofort nachgezogen werden.
