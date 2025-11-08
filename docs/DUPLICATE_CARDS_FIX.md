# Problem: Duplikate in cards Tabelle

## Problem identifiziert

Die `cards` Tabelle enthält **Duplikate** - dieselbe Karte wird mehrfach gespeichert. Bei Dominik Kohr wurden 46 Duplikate gefunden.

### Beispiel:
- Match 3152: Gelbe Karte 2x gespeichert
- Match 3154: Gelbe Karte 2x gespeichert
- etc.

## Lösung: DISTINCT verwenden

Um korrekte Werte zu bekommen, muss die Query Duplikate entfernen:

```sql
-- FALSCH (zählt Duplikate mit):
SELECT COUNT(*) FILTER (WHERE c.card_type = 'yellow')
FROM public.cards c
JOIN public.players p ON c.player_id = p.player_id
WHERE p.name ILIKE '%Kohr%';

-- RICHTIG (entfernt Duplikate):
SELECT COUNT(DISTINCT (c.match_id, c.player_id, COALESCE(c.minute, 0), c.card_type)) 
       FILTER (WHERE c.card_type = 'yellow')
FROM public.cards c
JOIN public.players p ON c.player_id = p.player_id
WHERE p.name ILIKE '%Kohr%';
```

## Korrigierte Query für gelbe Karten

```sql
SELECT 
    p.name as spieler_name,
    COUNT(DISTINCT (c.match_id, c.player_id, COALESCE(c.minute, 0), c.card_type)) 
        FILTER (WHERE c.card_type = 'yellow') AS gelbe_karten,
    COUNT(DISTINCT (c.match_id, c.player_id, COALESCE(c.minute, 0), c.card_type)) 
        FILTER (WHERE c.card_type = 'second_yellow') AS gelb_rot,
    COUNT(DISTINCT (c.match_id, c.player_id, COALESCE(c.minute, 0), c.card_type)) 
        FILTER (WHERE c.card_type = 'red') AS rote_karten
FROM public.cards c
JOIN public.players p ON c.player_id = p.player_id
JOIN public.match_lineups ml ON c.match_id = ml.match_id AND c.player_id = ml.player_id
WHERE ml.team_id = 36  -- Mainz 05
  AND c.card_type IN ('yellow', 'second_yellow', 'red')
GROUP BY p.player_id, p.name
ORDER BY gelbe_karten DESC
LIMIT 20;
```

## Validierung: Dominik Kohr

Mit korrigierter Query (ohne Duplikate):
- Gelbe Karten: 50 (Bundesliga + Pokal)
- Website zeigt: 56 (inkl. Sonstige Spiele)

Die Abweichung kommt daher, dass die Website auch "Sonstige Spiele" zählt, während die Query nur Bundesliga und Pokal berücksichtigt.


