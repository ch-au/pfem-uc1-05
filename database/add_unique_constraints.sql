-- Unique Constraints für PostgreSQL Schema
-- Verhindert Duplikate auf Datenbankebene
-- WICHTIG: Verwendet Partial Indexes für NULL-Handling

-- 1. Cards: Separate Indexes für NULL/non-NULL minute
-- 94.5% der Cards haben NULL minute (10,506 von 11,120)

-- Für non-NULL minute (nur 614 von 11,120 Einträgen)
DROP INDEX IF EXISTS public.cards_unique_nonnull;
CREATE UNIQUE INDEX cards_unique_nonnull 
ON public.cards (match_id, player_id, minute, card_type)
WHERE minute IS NOT NULL AND player_id IS NOT NULL;

-- Für NULL minute (94.5% der Fälle)
DROP INDEX IF EXISTS public.cards_unique_null_minute;
CREATE UNIQUE INDEX cards_unique_null_minute
ON public.cards (match_id, player_id, card_type)
WHERE minute IS NULL AND player_id IS NOT NULL;

-- 2. Match Substitutions: Functional Index mit COALESCE
-- 98.2% haben NULL stoppage, aber minute ist immer gesetzt
DROP INDEX IF EXISTS public.match_substitutions_unique_idx;
CREATE UNIQUE INDEX match_substitutions_unique_idx
ON public.match_substitutions (
    match_id, player_on_id, player_off_id, minute, 
    COALESCE(stoppage, -1)
)
WHERE player_on_id IS NOT NULL AND player_off_id IS NOT NULL;

-- 3. Goals: Functional Index mit COALESCE
-- 98.9% haben NULL stoppage, aber minute ist immer gesetzt
DROP INDEX IF EXISTS public.goals_unique_idx;
CREATE UNIQUE INDEX goals_unique_idx
ON public.goals (match_id, player_id, minute, COALESCE(stoppage, -1))
WHERE player_id IS NOT NULL;

-- Für own goals (player_id IS NULL), verwende alternative Prüfung
-- (kann nicht durch Unique Index abgedeckt werden, da player_id Teil des Keys ist)
-- Diese werden durch Code-Deduplizierung behandelt

-- 4. Match Lineups: Standard Partial Index
-- Keine NULL-Werte in der Praxis für Schlüsselfelder
DROP INDEX IF EXISTS public.match_lineups_unique_idx;
CREATE UNIQUE INDEX match_lineups_unique_idx
ON public.match_lineups (match_id, player_id, team_id)
WHERE match_id IS NOT NULL AND player_id IS NOT NULL AND team_id IS NOT NULL;

-- 5. Match Coaches: Standard Partial Index
-- Keine NULL-Werte in der Praxis für Schlüsselfelder
DROP INDEX IF EXISTS public.match_coaches_unique_idx;
CREATE UNIQUE INDEX match_coaches_unique_idx
ON public.match_coaches (match_id, team_id, coach_id, role)
WHERE match_id IS NOT NULL AND team_id IS NOT NULL AND coach_id IS NOT NULL;

-- 6. Match Referees: Standard Partial Index
-- Keine NULL-Werte in der Praxis für Schlüsselfelder
DROP INDEX IF EXISTS public.match_referees_unique_idx;
CREATE UNIQUE INDEX match_referees_unique_idx
ON public.match_referees (match_id, referee_id, role)
WHERE match_id IS NOT NULL AND referee_id IS NOT NULL;

-- Übersicht der erstellten Indexes
-- SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE '%unique%';




