# Parser-Korrektur: profirest.html wird nicht mehr als Europapokal klassifiziert

## Problem

Der Parser hat `profirest.html` (Freundschaftsspiele) fälschlicherweise als "Europapokal" klassifiziert, weil `"profirest"` in der Liste der europäischen Wettbewerbe enthalten war.

## Parser-Korrektur (durchgeführt)

**Datei:** `parsing/comprehensive_fsv_parser.py`  
**Zeile:** 1458-1467

**Änderung:**
- `"profirest"` wurde aus der Liste der europäischen Wettbewerbe entfernt
- Freundschaftsspiele werden jetzt nicht mehr geparst (da sie keine offiziellen Wettbewerbsspiele sind)

**Vorher:**
```python
for european_stub in ["profiuefa", "profiuec", "profiuecl", "profiintertoto", "profiueclq", "profirest"]:
```

**Nachher:**
```python
for european_stub in ["profiuefa", "profiuec", "profiuecl", "profiintertoto", "profiueclq"]:
# "profirest" entfernt - das sind Freundschaftsspiele, kein Europapokal!
```

## Bereits falsch klassifizierte Daten korrigieren

Falls bereits falsch klassifizierte Spiele in der Datenbank existieren (z.B. aus Saison 2018-19), können diese mit folgendem SQL korrigiert werden:

### Option 1: Falsch klassifizierte Spiele löschen

```sql
-- Finde und lösche falsch klassifizierte "Europapokal"-Spiele aus profirest.html
DELETE FROM public.matches
WHERE match_id IN (
    SELECT m.match_id
    FROM public.matches m
    JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
    JOIN public.competitions c ON sc.competition_id = c.competition_id
    WHERE c.name = 'Europapokal'
      AND m.source_file LIKE '%profirest%'
);
```

### Option 2: Zu neuem Wettbewerb "Freundschaftsspiele" umbuchen

```sql
-- 1. Erstelle neuen Wettbewerb "Freundschaftsspiele"
INSERT INTO public.competitions (name, normalized_name, level, gender)
VALUES ('Freundschaftsspiele', 'freundschaftsspiele', 'friendly', 'male')
ON CONFLICT (name) DO NOTHING;

-- 2. Finde die falsch klassifizierten Spiele
WITH falsche_europa_spiele AS (
    SELECT 
        m.match_id,
        sc.season_competition_id,
        sc.season_id,
        (SELECT competition_id FROM public.competitions WHERE name = 'Freundschaftsspiele') AS freundschafts_competition_id
    FROM public.matches m
    JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id
    JOIN public.competitions c ON sc.competition_id = c.competition_id
    WHERE c.name = 'Europapokal'
      AND m.source_file LIKE '%profirest%'
)
-- 3. Erstelle neue season_competition für Freundschaftsspiele
INSERT INTO public.season_competitions (season_id, competition_id, stage_label, source_path)
SELECT DISTINCT 
    season_id,
    freundschafts_competition_id,
    'Freundschaftsspiele',
    'profirest.html'
FROM falsche_europa_spiele
ON CONFLICT (season_id, competition_id) DO NOTHING
RETURNING season_competition_id, season_id;

-- 4. Update der Matches (manuell für jede Saison)
-- Beispiel für 2018-19:
UPDATE public.matches m
SET season_competition_id = (
    SELECT sc_new.season_competition_id
    FROM public.season_competitions sc_new
    JOIN public.seasons s ON sc_new.season_id = s.season_id
    JOIN public.competitions c_new ON sc_new.competition_id = c_new.competition_id
    WHERE s.label = '2018-19'
      AND c_new.name = 'Freundschaftsspiele'
    LIMIT 1
)
WHERE m.match_id IN (
    SELECT m2.match_id
    FROM public.matches m2
    JOIN public.season_competitions sc ON m2.season_competition_id = sc.season_competition_id
    JOIN public.seasons s ON sc.season_id = s.season_id
    JOIN public.competitions c ON sc.competition_id = c.competition_id
    WHERE s.label = '2018-19'
      AND c.name = 'Europapokal'
      AND m2.source_file LIKE '%profirest%'
);
```

## Empfehlung

**Für die aktuelle Situation:**
- Die Query wurde bereits korrigiert und filtert falsch klassifizierte Spiele heraus
- Der Parser wurde korrigiert, sodass zukünftige Parses korrekt sind

**Für eine vollständige Datenbereinigung:**
- Option 1 (Löschen) ist einfacher, wenn Freundschaftsspiele nicht benötigt werden
- Option 2 (Umbuchen) ist besser, wenn Freundschaftsspiele später analysiert werden sollen

## Verwandte Dateien

- `parsing/comprehensive_fsv_parser.py` - Parser (korrigiert)
- `sql_queries/siegquote_nach_saison_wettbewerb.sql` - Query (korrigiert mit Filter)
- `docs/EUROPAPOKAL_FALSCH_KLASSIFIZIERT.md` - Analyse des Problems

