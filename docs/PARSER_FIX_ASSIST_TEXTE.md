# Problem: Assist-Texte werden als Spieler erfasst

## Problem identifiziert

Die Query `SELECT p.name, COUNT(g.goal_id) as anzahl_tore FROM players p LEFT JOIN goals g ON p.player_id = g.player_id WHERE p.name LIKE '%Klopp%'` zeigt:

**Echte Spieler:**
- ✅ "Klopp": 44 Tore, 351 Aufstellungen (korrekt!)

**Parsing-Fehler (keine echten Spieler):**
- ❌ "Liebers an Klopp": 0 Tore, 0 Aufstellungen
- ❌ "Linke an Klopp": 0 Tore, 0 Aufstellungen  
- ❌ "Klopp an Antwerpen": 0 Tore, 0 Aufstellungen
- ❌ "Klopp an Rus": 0 Tore, 0 Aufstellungen

**Statistik:**
- 256 Spieler mit " an " im Namen
- 255 davon ohne Aufstellungen (Parsing-Fehler!)

## Ursache

Im HTML gibt es Tor-Einträge wie:
```html
56. 1:3 Falkenmayer (FE an Becker)
```

Das bedeutet: "Falkenmayer hat getroffen, Assist von FE an Becker"

Der Parser erstellt aber Spieler-Einträge für:
- "FE an Becker" (sollte nur "Becker" sein)
- "Liebers an Klopp" (sollte nur "Klopp" sein)

## Lösung

### 1. In `parse_goal_table` (Zeile 2293-2303)

Assist-Texte mit " an " werden jetzt aufgeteilt:
- "FE an Becker" → "Becker"
- "Liebers an Klopp" → "Klopp"

```python
# WICHTIG: Extrahiere Spielernamen aus "an"-Konstruktionen
if ' an ' in assist.lower():
    parts = re.split(r'\s+an\s+', assist, flags=re.IGNORECASE)
    if len(parts) > 1:
        assist = parts[-1].strip()  # Nimm den Teil NACH "an"
```

### 2. In `get_or_create_player` (Zeile 637-643)

Namen mit " an " werden jetzt abgelehnt:
```python
# WICHTIG: Filtere Assist-Texte mit " an " - das sind keine Spielernamen!
if ' an ' in name_clean.lower():
    raise ValueError(f"Invalid player name (assist text): {name_clean}")
```

## Ergebnis

Beim nächsten Parse werden:
- ✅ Assist-Texte korrekt aufgeteilt ("FE an Becker" → "Becker")
- ✅ Namen mit " an " werden nicht als Spieler erstellt
- ✅ Nur echte Spieler werden erfasst

Die 255 falschen Einträge müssen manuell aus der Datenbank entfernt werden oder beim nächsten vollständigen Re-Parse automatisch korrigiert werden.

