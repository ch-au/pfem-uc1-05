# FSV Mainz 05 Datenbank - Schema Dokumentation

**Datenbank:** Neon Postgres Cloud  
**Version:** Oktober 2025  
**Anzahl Tabellen:** 20  
**Gesamtanzahl Datensätze:** 141.787  
**Letzte Aktualisierung:** 29. Oktober 2025 - Vollständige Datenbereinigung und Parser-Optimierung

---

## Tabellenübersicht

| Tabelle | Datensätze | Zweck |
|---------|-----------|-------|
| teams | 293 | Mannschaften (FSV Mainz, Gegner) |
| competitions | 3 | Wettbewerbe (Bundesliga, DFB-Pokal, Europapokal) |
| seasons | 121 | Saisonen (1905-2026) |
| season_competitions | 175 | Verknüpfung Saison-Wettbewerb |
| referees | 870 | Schiedsrichter |
| coaches | 566 | Trainer (mit Geburtsdaten & Karriere) |
| coach_careers | 522 | Trainer-Karriereverläufe |
| players | 10.094 | Spieler-Stammdaten (bereinigt) |
| player_careers | 4.627 | Spieler-Karriereverläufe |
| season_squads | 468 | Kader pro Saison/Wettbewerb |
| matches | 3.231 | Spiele |
| match_coaches | 5.023 | Trainer-Zuordnungen |
| match_referees | 2.879 | Schiedsrichter-Zuordnungen |
| match_lineups | 84.172 | Aufstellungen |
| match_substitutions | 10.196 | Einwechslungen |
| goals | 5.652 | Tore (ungültige Einträge entfernt) |
| cards | 11.120 | Karten (Gelb/Rot) |
| season_matchdays | 1.775 | Saisonverlauf |

---

## Entitäts-Beziehungsdiagramm

```
teams (293)
  ├── seasons (121) [team_id → team_id]
  ├── matches (3.231) [home_team_id → team_id]
  ├── matches (3.231) [away_team_id → team_id]
  ├── match_coaches (5.023) [team_id → team_id]
  ├── match_lineups (84.172) [team_id → team_id]
  ├── match_substitutions (10.196) [team_id → team_id]
  ├── goals (5.652) [team_id → team_id]
  └── cards (11.120) [team_id → team_id]

competitions (3)
  └── season_competitions (175) [competition_id → competition_id]

seasons (121)
  └── season_competitions (175) [season_id → season_id]

season_competitions (175)
  ├── matches (3.231) [season_competition_id → season_competition_id]
  ├── season_squads (468) [season_competition_id → season_competition_id]
  └── season_matchdays (1.775) [season_competition_id → season_competition_id]

players (10.094) [bereinigt]
  ├── player_aliases (0) [player_id → player_id]
  ├── player_careers (4.627) [player_id → player_id]
  ├── season_squads (468) [player_id → player_id]
  ├── match_lineups (84.172) [player_id → player_id]
  ├── match_substitutions (10.196) [player_on_id, player_off_id → player_id]
  ├── goals (5.652) [player_id, assist_player_id → player_id]
  └── cards (11.120) [player_id → player_id]

coaches (566)
  ├── coach_careers (522) [coach_id → coach_id] [NEU]
  └── match_coaches (5.023) [coach_id → coach_id]

referees (870)
  ├── matches (3.231) [referee_id → referee_id]
  └── match_referees (2.879) [referee_id → referee_id]

matches (3.231)
  ├── match_coaches (5.023) [match_id → match_id]
  ├── match_referees (2.879) [match_id → match_id]
  ├── match_lineups (84.172) [match_id → match_id]
  ├── match_substitutions (10.196) [match_id → match_id]
  ├── goals (5.652) [match_id → match_id]
  ├── cards (11.120) [match_id → match_id]
  └── match_notes (0) [match_id → match_id]
```

---

## Detaillierte Tabellenschemata

### 1. Stammdaten-Tabellen

#### teams
Mannschafts-Stammdaten inkl. FSV Mainz 05 und alle Gegner.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| team_id | INTEGER | PRIMARY KEY | Eindeutige Mannschafts-ID |
| name | TEXT | UNIQUE, NOT NULL | Mannschaftsname |
| normalized_name | TEXT | UNIQUE | Normalisierter Name für Matching |
| team_type | TEXT | | Mannschaftstyp |
| profile_url | TEXT | | Link zum Profil |
| name_embedding | vector(1024) | | Cohere embed-v4.0 Embedding für Fuzzy-Matching |

**Indizes:** 
- `idx_teams_normalized_name` (Textsuche)
- `idx_teams_name_embedding_hnsw` (Vektorsuche)

---

#### players
Spieler-Stammdaten mit biografischen Informationen.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| player_id | INTEGER | PRIMARY KEY | Eindeutige Spieler-ID |
| name | TEXT | UNIQUE, NOT NULL | Spielername |
| normalized_name | TEXT | UNIQUE | Normalisierter Name |
| birth_date | DATE | | Geburtsdatum |
| birth_place | TEXT | | Geburtsort |
| height_cm | INTEGER | | Körpergröße in cm |
| weight_kg | INTEGER | | Gewicht in kg |
| primary_position | TEXT | | Hauptposition |
| nationality | TEXT | | Nationalität |
| profile_url | TEXT | | Link zum Profil |
| image_url | TEXT | | Link zum Bild |
| name_embedding | vector(1024) | | Cohere embed-v4.0 Embedding für Fuzzy-Matching |

**Indizes:** 
- `idx_players_normalized_name` (Textsuche)
- `idx_players_name` (Textsuche)
- `idx_players_name_embedding_hnsw` (Vektorsuche)

---

#### coaches
Trainer-Stammdaten mit biografischen Informationen.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| coach_id | INTEGER | PRIMARY KEY | Eindeutige Trainer-ID |
| name | TEXT | UNIQUE, NOT NULL | Trainername |
| normalized_name | TEXT | UNIQUE | Normalisierter Name |
| birth_date | DATE | | Geburtsdatum |
| birth_place | TEXT | | Geburtsort |
| nationality | TEXT | | Nationalität |
| profile_url | TEXT | | Link zum Profil |

**Indizes:** `idx_coaches_normalized_name`

**Datenqualität:** 
- 566 Trainer gesamt
- 52 (9.2%) mit Geburtsdatum
- 522 Karriere-Stationen erfasst

---

#### referees
Schiedsrichter-Stammdaten.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| referee_id | INTEGER | PRIMARY KEY | Eindeutige Schiedsrichter-ID |
| name | TEXT | UNIQUE, NOT NULL | Schiedsrichtername |
| normalized_name | TEXT | UNIQUE | Normalisierter Name |
| profile_url | TEXT | | Link zum Profil |

**Indizes:** `idx_referees_normalized_name`

---

#### competitions
Wettbewerbe (Bundesliga, DFB-Pokal, Europapokal).

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| competition_id | INTEGER | PRIMARY KEY | Eindeutige Wettbewerb-ID |
| name | TEXT | UNIQUE, NOT NULL | Wettbewerbsname |
| normalized_name | TEXT | UNIQUE | Normalisierter Name |
| level | TEXT | | Wettbewerbsebene |
| gender | TEXT | | Geschlechterkategorie |

---

### 2. Saison & Kader Tabellen

#### seasons
Saisondefinitionen von 1905 bis 2026.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| season_id | INTEGER | PRIMARY KEY | Eindeutige Saison-ID |
| label | TEXT | UNIQUE, NOT NULL | Saisonbezeichnung (z.B. "2023-24") |
| start_year | INTEGER | | Startjahr der Saison |
| end_year | INTEGER | | Endjahr der Saison |
| team_id | INTEGER | FOREIGN KEY → teams | Mannschaftsreferenz |

**Indizes:** `idx_seasons_label`, `idx_seasons_years`

---

#### season_competitions
Verknüpfung von Saisonen mit Wettbewerben.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| season_competition_id | INTEGER | PRIMARY KEY | Eindeutige ID |
| season_id | INTEGER | FOREIGN KEY → seasons | Saisonreferenz |
| competition_id | INTEGER | FOREIGN KEY → competitions | Wettbewerbsreferenz |
| stage_label | TEXT | | Wettbewerbsphase |
| source_path | TEXT | | Quelldateipfad |

**Constraint:** `UNIQUE(season_id, competition_id)`  
**Indizes:** `idx_season_competitions_season`, `idx_season_competitions_comp`

---

#### season_squads
Kaderzuordnungen pro Saison/Wettbewerb.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| season_squad_id | INTEGER | PRIMARY KEY | Eindeutige ID |
| season_competition_id | INTEGER | FOREIGN KEY → season_competitions | Saison/Wettbewerb |
| player_id | INTEGER | FOREIGN KEY → players | Spielerreferenz |
| position_group | TEXT | | Positionsgruppe |
| shirt_number | INTEGER | | Rückennummer |
| status | TEXT | | Spielerstatus |
| notes | TEXT | | Zusätzliche Notizen |

**Constraint:** `UNIQUE(season_competition_id, player_id, position_group)`

---

#### player_aliases
Alternative Spielernamen.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| alias_id | INTEGER | PRIMARY KEY | Eindeutige ID |
| player_id | INTEGER | FOREIGN KEY → players (CASCADE DELETE) | Spielerreferenz |
| alias | TEXT | | Alternativname |
| normalized_alias | TEXT | | Normalisierter Alias |

**Constraint:** `UNIQUE(player_id, normalized_alias)`

---

#### player_careers
Karriereverläufe der Spieler.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| career_id | INTEGER | PRIMARY KEY | Eindeutige ID |
| player_id | INTEGER | FOREIGN KEY → players (CASCADE DELETE) | Spielerreferenz |
| team_name | TEXT | NOT NULL | Vereinsname |
| start_year | INTEGER | | Startjahr |
| end_year | INTEGER | | Endjahr |
| notes | TEXT | | Notizen |

---

#### coach_careers
Karriereverläufe der Trainer mit detaillierten Stationen.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| career_id | INTEGER | PRIMARY KEY | Eindeutige ID |
| coach_id | INTEGER | FOREIGN KEY → coaches (CASCADE DELETE) | Trainerreferenz |
| team_name | TEXT | NOT NULL | Vereinsname |
| start_date | TEXT | | Startdatum (flexible Formate: YYYY, DD.MM.YYYY) |
| end_date | TEXT | | Enddatum (flexible Formate) |
| role | TEXT | | Rolle (z.B. "Cheftrainer", "Co-Trainer", "U23") |

**Beispiel-Daten (Jan Siewert):**
- 14 Karriere-Stationen von 2009-2025
- Deutschland Nachwuchskoordinator, BVB U23, Mainz 05, SpVgg Fürth

---

### 3. Spiel-Tabellen

#### matches
Spiel-Stammdaten mit Ergebnissen und Metadaten.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| match_id | INTEGER | PRIMARY KEY | Eindeutige Spiel-ID |
| season_competition_id | INTEGER | FOREIGN KEY → season_competitions | Saison/Wettbewerb |
| round_name | TEXT | | Rundenbezeichnung |
| matchday | INTEGER | | Spieltag |
| leg | INTEGER | | Spielnummer (bei Hin-/Rückspiel) |
| match_date | DATE | | Spieldatum |
| kickoff_time | TEXT | | Anstoßzeit |
| venue | TEXT | | Stadion/Spielort |
| attendance | INTEGER | | Zuschauerzahl |
| referee_id | INTEGER | FOREIGN KEY → referees | Hauptschiedsrichter |
| home_team_id | INTEGER | FOREIGN KEY → teams | Heimmannschaft |
| away_team_id | INTEGER | FOREIGN KEY → teams | Auswärtsmannschaft |
| home_score | INTEGER | | Tore Heimmannschaft |
| away_score | INTEGER | | Tore Auswärtsmannschaft |
| halftime_home | INTEGER | | Halbzeitstand Heim |
| halftime_away | INTEGER | | Halbzeitstand Auswärts |
| extra_time_home | INTEGER | | Verlängerung Heim |
| extra_time_away | INTEGER | | Verlängerung Auswärts |
| penalties_home | INTEGER | | Elfmeterschießen Heim |
| penalties_away | INTEGER | | Elfmeterschießen Auswärts |
| source_file | TEXT | | Quelldatei |

**Constraint:** `UNIQUE(season_competition_id, source_file)`  
**Indizes:** `idx_matches_date`, `idx_matches_season_comp`, `idx_matches_home_team`, `idx_matches_away_team`

---

#### match_lineups
Spieleraufstellungen (Stammelf und Einwechselspieler).

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| lineup_id | INTEGER | PRIMARY KEY | Eindeutige ID |
| match_id | INTEGER | FOREIGN KEY → matches (CASCADE DELETE) | Spielreferenz |
| team_id | INTEGER | FOREIGN KEY → teams | Mannschaftsreferenz |
| player_id | INTEGER | FOREIGN KEY → players | Spielerreferenz |
| shirt_number | INTEGER | | Rückennummer |
| is_starter | BOOLEAN | | Startelfspieler |
| minute_on | INTEGER | | Einwechslungsminute |
| stoppage_on | INTEGER | | Nachspielzeit Einwechslung |
| minute_off | INTEGER | | Auswechslungsminute |
| stoppage_off | INTEGER | | Nachspielzeit Auswechslung |

**Indizes:** `idx_lineups_match`, `idx_lineups_player`, `idx_lineups_team`

---

#### match_substitutions
Auswechslungen während der Spiele.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| substitution_id | INTEGER | PRIMARY KEY | Eindeutige ID |
| match_id | INTEGER | FOREIGN KEY → matches (CASCADE DELETE) | Spielreferenz |
| team_id | INTEGER | FOREIGN KEY → teams | Mannschaftsreferenz |
| minute | INTEGER | | Minute der Auswechslung |
| stoppage | INTEGER | | Nachspielzeit |
| player_on_id | INTEGER | FOREIGN KEY → players | Eingewechselter Spieler |
| player_off_id | INTEGER | FOREIGN KEY → players | Ausgewechselter Spieler |

**Indizes:** `idx_subs_match`, `idx_subs_player_on`, `idx_subs_player_off`

---

#### goals
Torereignisse mit Torschützen und Vorlagen.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| goal_id | INTEGER | PRIMARY KEY | Eindeutige ID |
| match_id | INTEGER | FOREIGN KEY → matches (CASCADE DELETE) | Spielreferenz |
| team_id | INTEGER | FOREIGN KEY → teams | Torschützenteam |
| player_id | INTEGER | FOREIGN KEY → players | Torschütze |
| assist_player_id | INTEGER | FOREIGN KEY → players | Vorlagengeber |
| minute | INTEGER | | Torminute |
| stoppage | INTEGER | | Nachspielzeit |
| score_home | INTEGER | | Heimstand nach Tor |
| score_away | INTEGER | | Auswärtsstand nach Tor |
| event_type | TEXT | | Torart (regulär, Elfmeter, Eigentor) |

**Indizes:** `idx_goals_match`, `idx_goals_player`, `idx_goals_assist`

---

#### cards
Gelbe und Rote Karten.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| card_id | INTEGER | PRIMARY KEY | Eindeutige ID |
| match_id | INTEGER | FOREIGN KEY → matches (CASCADE DELETE) | Spielreferenz |
| team_id | INTEGER | FOREIGN KEY → teams | Mannschaftsreferenz |
| player_id | INTEGER | FOREIGN KEY → players | Spielerreferenz |
| minute | INTEGER | | Minute der Karte |
| stoppage | INTEGER | | Nachspielzeit |
| card_type | TEXT | | Kartentyp (yellow, red, second_yellow) |

**Indizes:** `idx_cards_match`, `idx_cards_player`

---

#### match_coaches
Trainerzuordnungen pro Spiel.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| match_coach_id | INTEGER | PRIMARY KEY | Eindeutige ID |
| match_id | INTEGER | FOREIGN KEY → matches (CASCADE DELETE) | Spielreferenz |
| team_id | INTEGER | FOREIGN KEY → teams | Mannschaftsreferenz |
| coach_id | INTEGER | FOREIGN KEY → coaches | Trainerreferenz |
| role | TEXT | | Trainerrolle |

---

#### match_referees
Schiedsrichterzuordnungen pro Spiel.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| match_referee_id | INTEGER | PRIMARY KEY | Eindeutige ID |
| match_id | INTEGER | FOREIGN KEY → matches (CASCADE DELETE) | Spielreferenz |
| referee_id | INTEGER | FOREIGN KEY → referees | Schiedsrichterreferenz |
| role | TEXT | | Rolle (Hauptschiedsrichter, Assistent, 4. Offizieller) |

---

#### match_notes
Zusätzliche Spielinformationen.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| note_id | INTEGER | PRIMARY KEY | Eindeutige ID |
| match_id | INTEGER | FOREIGN KEY → matches (CASCADE DELETE) | Spielreferenz |
| note | TEXT | | Notizinhalt |
| note_type | TEXT | | Notiztyp/Kategorie |

---

#### season_matchdays
Saisonverlauf mit Tabellenständen.

| Spalte | Typ | Constraints | Beschreibung |
|--------|-----|-------------|--------------|
| season_matchday_id | INTEGER | PRIMARY KEY | Eindeutige ID |
| season_competition_id | INTEGER | FOREIGN KEY → season_competitions | Saison/Wettbewerb |
| matchday | INTEGER | | Spieltag |
| date | DATE | | Datum |
| position | INTEGER | | Tabellenplatz |
| points | INTEGER | | Gesammelte Punkte |
| goals_for | INTEGER | | Erzielte Tore |
| goals_against | INTEGER | | Gegentore |
| goal_difference | INTEGER | | Tordifferenz |

---

## Performance-Indizes

### Textbasierte Suche

```sql
-- Stammdaten-Lookups
CREATE INDEX idx_teams_normalized_name ON public.teams(normalized_name);
CREATE INDEX idx_players_normalized_name ON public.players(normalized_name);
CREATE INDEX idx_players_name ON public.players(name);
CREATE INDEX idx_coaches_normalized_name ON public.coaches(normalized_name);
CREATE INDEX idx_referees_normalized_name ON public.referees(normalized_name);

-- Saison- und Wettbewerbs-Lookups
CREATE INDEX idx_seasons_label ON public.seasons(label);
CREATE INDEX idx_seasons_years ON public.seasons(start_year, end_year);
CREATE INDEX idx_season_competitions_season ON public.season_competitions(season_id);
CREATE INDEX idx_season_competitions_comp ON public.season_competitions(competition_id);

-- Spiel-Queries
CREATE INDEX idx_matches_date ON public.matches(match_date);
CREATE INDEX idx_matches_season_comp ON public.matches(season_competition_id);
CREATE INDEX idx_matches_home_team ON public.matches(home_team_id);
CREATE INDEX idx_matches_away_team ON public.matches(away_team_id);

-- Spielereignisse
CREATE INDEX idx_lineups_match ON public.match_lineups(match_id);
CREATE INDEX idx_lineups_player ON public.match_lineups(player_id);
CREATE INDEX idx_lineups_team ON public.match_lineups(team_id);
CREATE INDEX idx_goals_match ON public.goals(match_id);
CREATE INDEX idx_goals_player ON public.goals(player_id);
CREATE INDEX idx_goals_assist ON public.goals(assist_player_id);
CREATE INDEX idx_cards_match ON public.cards(match_id);
CREATE INDEX idx_cards_player ON public.cards(player_id);
CREATE INDEX idx_subs_match ON public.match_substitutions(match_id);
CREATE INDEX idx_subs_player_on ON public.match_substitutions(player_on_id);
CREATE INDEX idx_subs_player_off ON public.match_substitutions(player_off_id);
```

### Vektorbasierte Ähnlichkeitssuche

```sql
-- HNSW-Indizes für schnelle semantische Suche
CREATE INDEX idx_players_name_embedding_hnsw 
ON public.players 
USING hnsw (name_embedding vector_cosine_ops);

CREATE INDEX idx_teams_name_embedding_hnsw 
ON public.teams 
USING hnsw (name_embedding vector_cosine_ops);
```

**Referenz:** [Neon pgvector Guide](https://neon.com/guides/ai-embeddings-postgres-search)

---

## Beispiel-Queries

### Query 1: Semantische Ähnlichkeitssuche - Spielernamen

Finde Spieler mit ähnlichen Namen (behandelt Tippfehler, Variationen, Sonderzeichen):

```sql
-- Finde Spieler ähnlich zu "Muller" (findet Müller, Mueller, etc.)
WITH search_player AS (
    SELECT name_embedding 
    FROM public.players 
    WHERE name = 'Müller' 
    LIMIT 1
)
SELECT 
    p.player_id,
    p.name,
    p.nationality,
    p.primary_position,
    1 - (p.name_embedding <=> sp.name_embedding) as aehnlichkeit,
    (SELECT COUNT(*) FROM public.goals WHERE player_id = p.player_id) as tore_gesamt
FROM public.players p, search_player sp
WHERE p.name_embedding IS NOT NULL
ORDER BY p.name_embedding <=> sp.name_embedding
LIMIT 10;
```

**Ergebnis:** Spieler mit semantisch ähnlichen Namen, sortiert nach Ähnlichkeit (1.0 = perfekte Übereinstimmung)

**Technologie:** pgvector mit Cohere embed-v4.0 Embeddings  
**Referenz:** [Neon pgvector Guide](https://neon.com/guides/ai-embeddings-postgres-search)

---

### Query 2: Top-Torschützen mit Statistiken

Ermittle die besten Torschützen aller Zeiten mit detaillierten Statistiken:

```sql
SELECT 
    p.name,
    p.nationality as nationalitaet,
    p.primary_position as position,
    COUNT(DISTINCT g.goal_id) as tore_gesamt,
    COUNT(DISTINCT g.match_id) as spiele_mit_tor,
    COUNT(DISTINCT ml.match_id) as einsaetze_gesamt,
    ROUND(
        COUNT(DISTINCT g.goal_id)::numeric / NULLIF(COUNT(DISTINCT ml.match_id), 0), 
        3
    ) as tore_pro_spiel,
    MIN(m.match_date) as erstes_tor,
    MAX(m.match_date) as letztes_tor
FROM public.players p
LEFT JOIN public.goals g ON p.player_id = g.player_id 
    AND (g.event_type IS NULL OR g.event_type != 'own_goal')
LEFT JOIN public.match_lineups ml ON p.player_id = ml.player_id
LEFT JOIN public.matches m ON g.match_id = m.match_id
GROUP BY p.player_id, p.name, p.nationality, p.primary_position
HAVING COUNT(DISTINCT g.goal_id) > 0
ORDER BY tore_gesamt DESC
LIMIT 20;
```

**Ergebnis:** Top 20 Torschützen mit Tor-pro-Spiel-Quote, Karrierespanne und Einsatzstatistiken

---

### Query 3: Vollständige Spieldetails

Umfassende Spielinformationen inkl. Aufstellungen, Tore und Torschützen:

```sql
-- Vollständige Details für ein bestimmtes Spiel
WITH spiel_info AS (
    SELECT 
        m.match_id,
        s.label as saison,
        c.name as wettbewerb,
        m.match_date as datum,
        m.venue as stadion,
        m.attendance as zuschauer,
        t_home.name as heimmannschaft,
        t_away.name as gastmannschaft,
        m.home_score as tore_heim,
        m.away_score as tore_gast,
        m.halftime_home as halbzeit_heim,
        m.halftime_away as halbzeit_gast
    FROM public.matches m
    JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
    JOIN public.seasons s ON sc.season_id = s.season_id
    JOIN public.competitions c ON sc.competition_id = c.competition_id
    JOIN public.teams t_home ON m.home_team_id = t_home.team_id
    JOIN public.teams t_away ON m.away_team_id = t_away.team_id
    WHERE m.match_id = 3355
),
spiel_tore AS (
    SELECT 
        g.minute,
        g.stoppage as nachspielzeit,
        p.name as torschuetze,
        t.name as mannschaft,
        g.score_home || ':' || g.score_away as zwischenstand,
        g.event_type as tor_art,
        p_assist.name as vorlage_von
    FROM public.goals g
    JOIN public.players p ON g.player_id = p.player_id
    JOIN public.teams t ON g.team_id = t.team_id
    LEFT JOIN public.players p_assist ON g.assist_player_id = p_assist.player_id
    WHERE g.match_id = 3355
    ORDER BY g.minute, g.stoppage
),
spiel_aufstellung AS (
    SELECT 
        t.name as mannschaft,
        p.name as spieler,
        ml.shirt_number as rueckennummer,
        ml.is_starter as stammelf,
        ml.minute_on as einwechslung,
        ml.minute_off as auswechslung,
        p.primary_position as position
    FROM public.match_lineups ml
    JOIN public.players p ON ml.player_id = p.player_id
    JOIN public.teams t ON ml.team_id = t.team_id
    WHERE ml.match_id = 3355
    ORDER BY t.name, ml.is_starter DESC, ml.shirt_number
)
SELECT 
    'Spiel-Info' as daten_typ,
    json_build_object(
        'saison', saison,
        'wettbewerb', wettbewerb,
        'datum', datum,
        'stadion', stadion,
        'zuschauer', zuschauer,
        'heimmannschaft', heimmannschaft,
        'gastmannschaft', gastmannschaft,
        'ergebnis', tore_heim || ':' || tore_gast,
        'halbzeit', halbzeit_heim || ':' || halbzeit_gast
    ) as details
FROM spiel_info

UNION ALL

SELECT 
    'Tore' as daten_typ,
    json_agg(
        json_build_object(
            'minute', minute,
            'torschuetze', torschuetze,
            'mannschaft', mannschaft,
            'zwischenstand', zwischenstand,
            'tor_art', tor_art,
            'vorlage', vorlage_von
        ) ORDER BY minute
    ) as details
FROM spiel_tore

UNION ALL

SELECT 
    'Aufstellung' as daten_typ,
    json_agg(
        json_build_object(
            'mannschaft', mannschaft,
            'spieler', spieler,
            'rueckennummer', rueckennummer,
            'stammelf', stammelf,
            'position', position
        )
    ) as details
FROM spiel_aufstellung;
```

**Ergebnis:** Vollständige Spielzusammenfassung mit allen Details im JSON-Format

---

### Query 4: Leistung nach Wettbewerb

Analyse der FSV Mainz 05 Leistung in verschiedenen Wettbewerben:

```sql
SELECT 
    c.name as wettbewerb,
    COUNT(DISTINCT s.season_id) as saisonen_teilgenommen,
    COUNT(m.match_id) as spiele_gesamt,
    SUM(CASE 
        WHEN (m.home_team_id = 1 AND m.home_score > m.away_score) 
          OR (m.away_team_id = 1 AND m.away_score > m.home_score) 
        THEN 1 ELSE 0 
    END) as siege,
    SUM(CASE 
        WHEN m.home_score = m.away_score 
        THEN 1 ELSE 0 
    END) as unentschieden,
    SUM(CASE 
        WHEN (m.home_team_id = 1 AND m.home_score < m.away_score) 
          OR (m.away_team_id = 1 AND m.away_score < m.home_score) 
        THEN 1 ELSE 0 
    END) as niederlagen,
    ROUND(
        100.0 * SUM(CASE 
            WHEN (m.home_team_id = 1 AND m.home_score > m.away_score) 
              OR (m.away_team_id = 1 AND m.away_score > m.home_score) 
            THEN 1 ELSE 0 
        END) / NULLIF(COUNT(m.match_id), 0),
        1
    ) as siegquote_prozent
FROM public.competitions c
JOIN public.season_competitions sc ON c.competition_id = sc.competition_id
LEFT JOIN public.matches m ON sc.season_competition_id = m.season_competition_id
JOIN public.seasons s ON sc.season_id = s.season_id
WHERE c.name IN ('Bundesliga', 'DFB-Pokal', 'Europapokal')
GROUP BY c.name
ORDER BY spiele_gesamt DESC;
```

**Ergebnis:** Sieg/Niederlage/Unentschieden-Statistiken pro Wettbewerb

---

### Query 5: Trainer-Karrieren mit Laufbahn

Detaillierte Trainer-Historie mit allen Stationen:

```sql
SELECT 
    c.name as trainer,
    c.birth_date as geburtsdatum,
    c.birth_place as geburtsort,
    COUNT(DISTINCT cc.career_id) as anzahl_stationen,
    STRING_AGG(
        cc.team_name || ' (' || cc.start_date || ' - ' || cc.end_date || '): ' || COALESCE(cc.role, '-'),
        E'\n' 
        ORDER BY cc.start_date
    ) as karriere_verlauf
FROM coaches c
LEFT JOIN coach_careers cc ON c.coach_id = cc.coach_id
WHERE c.name ILIKE '%siewert%'
GROUP BY c.coach_id, c.name, c.birth_date, c.birth_place;
```

**Beispiel-Ergebnis (Jan Siewert):**
- Geburtsdatum: 1982-08-23
- Geburtsort: Mayen
- 14 Karriere-Stationen: Deutschland (Nachwuchskoordinator), BVB U23, Huddersfield Town, Mainz 05, SpVgg Fürth

---

## Semantische Suche mit Cohere API

Für die Ähnlichkeitssuche mit benutzerdefiniertem Suchbegriff:

```python
import cohere
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# 1. Embedding für Suchbegriff generieren
cohere_client = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))
response = cohere_client.embed(
    texts=["Brosinzki"],  # Suchbegriff (darf Rechtschreibfehler enthalten!)
    model="embed-v4.0",
    input_type="search_query",
    embedding_types=["float"],
    output_dimension=1024
)

query_embedding = response.embeddings.float_[0]
query_vec = '[' + ','.join(str(x) for x in query_embedding) + ']'

# 2. Datenbank mit Kosinus-Ähnlichkeit durchsuchen
conn = psycopg2.connect(os.getenv("DB_URL"))
with conn.cursor() as cur:
    cur.execute("""
        SELECT 
            player_id,
            name,
            nationality as nationalitaet,
            1 - (name_embedding <=> %s::vector) as aehnlichkeit
        FROM public.players
        WHERE name_embedding IS NOT NULL
        ORDER BY name_embedding <=> %s::vector
        LIMIT 10
    """, (query_vec, query_vec))
    
    results = cur.fetchall()
    for player_id, name, nationalitaet, aehnlichkeit in results:
        print(f"{name:30s} ({nationalitaet}) - {aehnlichkeit:.3f}")

conn.close()
```

**Ergebnis:** Spieler nach semantischer Ähnlichkeit zum Suchbegriff sortiert

**Hinweis:** Der `<=>` Operator berechnet die Kosinus-Distanz. Durch Subtraktion von 1 wird diese in Ähnlichkeit konvertiert (1.0 = perfekte Übereinstimmung).

---

## Verwendung der Fuzzy-Suche

### Beispiel: Spielersuche mit Tippfehlern

```python
# Utility-Script verwenden
from test_name_similarity import search_similar_players

# Suche mit Rechtschreibfehler
ergebnisse = search_similar_players("Brosinzki", limit=5)

for player_id, name, aehnlichkeit in ergebnisse:
    if aehnlichkeit > 0.85:
        print(f"✓ Gefunden: {name} (Übereinstimmung: {aehnlichkeit:.1%})")
```

**Beispielergebnis:**
```
✓ Gefunden: Brosiski (Übereinstimmung: 66.4%)
✓ Gefunden: Brosinski (Übereinstimmung: 64.7%)
✓ Gefunden: Broschinski (Übereinstimmung: 61.1%)
```

### Beispiel: Mannschaftssuche

```python
from test_name_similarity import search_similar_teams

# Suche mit englischer Schreibweise
ergebnisse = search_similar_teams("Bayern Munich", limit=3)

for team_id, name, aehnlichkeit in ergebnisse:
    print(f"{name}: {aehnlichkeit:.1%}")
```

**Beispielergebnis:**
```
FC Bayern München: 53.9%
FC Bayern Hof: 48.6%
Bayer 04 Leverkusen: 40.7%
```

---

## Datenqualität

### Abdeckung
- **Saisonen:** 121 (1905-2026)
- **Spiele:** 3.231 (bereinigt)
- **Spieler:** 10.094 (654 ungültige Einträge entfernt)
- **Embeddings:** 100% Abdeckung

### Parser-Optimierungen (Oktober 2025)

**Spieler-Daten:**
- ✅ Nationalität: 1.163 Spieler (11.5%) - NEU implementiert
- ✅ Größe/Gewicht: Regex korrigiert für 2- und 3-stellige Werte
- ✅ Position: Robusteres Parsing
- ✅ Intelligentes Name-Matching: 650 Spieler zusätzlich angereichert

**Zuschauerzahlen:**
- ✅ 1950er-1970er: **100% Vollständigkeit** (vorher 0%!)
- ✅ Alt-Format ohne Uhrzeit jetzt unterstützt
- ✅ COVID-Geisterspiele korrekt als NULL erfasst

**Trainer-Daten (NEU):**
- ✅ 52 Trainer mit Geburtsdaten (9.2%)
- ✅ 522 Karriere-Stationen erfasst
- ✅ Detaillierte Laufbahn-Historie

**Datenbereinigung:**
- ✅ 654 ungültige Spieler-Einträge entfernt (FE/HE/ET-Beschreibungen, Trikot-Nummern)
- ✅ 1.175 fehlerhafte Tor-Einträge gelöscht
- ✅ 111 ungültige Daten korrigiert

### Wettbewerbe
- **Bundesliga:** ~2.900 Spiele (111 Saisonen)
- **DFB-Pokal:** ~180 Spiele (59 Saisonen)
- **Europapokal:** ~15 Spiele (5 Saisonen)

### Top-Spieler
- **Rekordtorschütze:** Bopp (136 Tore) - deutsch, Stürmer
- **Aktuelle Top-Scorer:** Burkardt (32 Tore) - deutsch, Angriff, 181cm
- **Meiste Einsätze:** Müller (694 Spiele)

---

## Changelog

### Version 2.0 - 29. Oktober 2025

**Umfassende Parser-Optimierung und Datenbereinigung**

**Neue Features:**
- ✅ **Coach-Karrieren**: Neue `coach_careers` Tabelle mit 522 Stationen
- ✅ **Trainer-Biografie**: `birth_date`, `birth_place`, `nationality` für coaches
- ✅ **Intelligentes Name-Matching**: 650 zusätzliche Spieler angereichert
- ✅ **Nationalitäts-Parsing**: Komplett neu implementiert (1.163 Spieler)

**Parser-Korrekturen:**
- ✅ Größe-Parsing: Regex korrigiert (`\d{2,3}` statt `\d{3}`)
- ✅ Zuschauerzahlen: Alt-Format (1950er-70er) ohne Uhrzeit unterstützt
- ✅ Position-Parsing: Robustere Logik
- ✅ Datum-Parsing: DOTALL-Flag für Multiline-Matching

**Datenbereinigung:**
- ✅ 654 ungültige Spieler entfernt (FE/HE/ET-Tor-Beschreibungen, Trikot-Nummern)
- ✅ 1.175 fehlerhafte Tor-Einträge gelöscht
- ✅ 111 ungültige Daten korrigiert

**Qualitätsverbesserungen:**
- ✅ Zuschauerzahlen 1950er-1970er: 0% → **100%**
- ✅ Spieler mit Nationalität: ~3% → **11.5%**
- ✅ Top-Scorer Profile: 40% → **80%** vollständig

**Technische Details:**
- Gesamtdatensätze reduziert: 143.820 → 141.787 (durch Bereinigung)
- Datenintegrität verbessert durch Constraint-Validierung
- Foreign Key Referenzen bereinigt

---

**Ende der Schema-Dokumentation**
