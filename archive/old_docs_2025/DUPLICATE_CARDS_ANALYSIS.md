# Duplikate in cards Tabelle - Root Cause Analysis

## Problem identifiziert

**48.1% der Karten sind Duplikate!** (5,354 von 11,120 Karten)

### Root Cause

In `comprehensive_fsv_parser.py` werden Karten **zweimal** eingefügt:

1. **Aus Lineups** (Zeile 1001-1002):
   ```python
   for minute, stoppage, card_type in appearance.card_events:
       self.db.add_card(match_id, team_id, player_id, minute, stoppage, card_type)
   ```

2. **Aus separater cards Liste** (Zeile 1026-1036):
   ```python
   for card in cards:
       team_id = home_team_id if card["team_role"] == "home" else away_team_id
       self.db.add_card(match_id, team_id, player_id, card["minute"], card["stoppage"], card["card_type"])
   ```

### Warum entstehen Duplikate?

- **Fehlende Unique Constraint**: Die `cards` Tabelle hat KEINEN Unique Constraint auf `(match_id, player_id, minute, card_type)`
- **Doppelte Einfügung**: Derselbe Parser fügt Karten aus zwei verschiedenen Quellen ein
- **Unterschiedliche team_id**: Einige Duplikate haben unterschiedliche `team_id` Werte (29 Gruppen), was darauf hindeutet, dass die team_id beim Parsen unterschiedlich gesetzt wird

### Beispiel

Match 2384, Player 6456, gelbe Karte:
- 10 Duplikate!
- 5x mit `team_id = 240` (VfL Bochum - Home)
- 5x mit `team_id = 36` (Mainz 05 - Away)

### Statistiken

- **Total cards**: 11,120
- **Unique cards**: 5,766
- **Duplicates**: 5,354 (48.1%)
- **Duplicates with different team_id**: 29 Gruppen

## Lösung

### Option 1: Unique Constraint hinzufügen (empfohlen)

```sql
ALTER TABLE public.cards
ADD CONSTRAINT cards_unique_match_player_minute_type 
UNIQUE (match_id, player_id, COALESCE(minute, -1), card_type);
```

**Problem**: `COALESCE` funktioniert nicht direkt in Constraints. Alternativ:

```sql
-- Erstelle Unique Index statt Constraint
CREATE UNIQUE INDEX cards_unique_idx 
ON public.cards (match_id, player_id, COALESCE(minute, -1), card_type);

-- Oder mit NULL handling:
CREATE UNIQUE INDEX cards_unique_idx 
ON public.cards (match_id, player_id, minute, card_type)
WHERE minute IS NOT NULL;

CREATE UNIQUE INDEX cards_unique_idx_null 
ON public.cards (match_id, player_id, card_type)
WHERE minute IS NULL;
```

### Option 2: Parser fixen (langfristig)

Entferne die doppelte Einfügung:
- Entweder nur aus `appearance.card_events` ODER nur aus `cards` Liste
- Oder: Prüfe vor dem Einfügen, ob die Karte bereits existiert

### Option 3: Datenbereinigung (sofort)

```sql
-- Lösche Duplikate, behalte nur die erste (niedrigste card_id)
DELETE FROM public.cards
WHERE card_id NOT IN (
    SELECT MIN(card_id)
    FROM public.cards
    GROUP BY match_id, player_id, COALESCE(minute, -1), card_type
);
```

## Empfohlene Vorgehensweise

1. **Sofort**: Datenbereinigung durchführen (Option 3)
2. **Kurzfristig**: Unique Constraint/Index hinzufügen (Option 1)
3. **Langfristig**: Parser fixen um Duplikate zu vermeiden (Option 2)


