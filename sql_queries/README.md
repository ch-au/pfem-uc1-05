# SQL Queries für FSV Mainz 05 Datenbank

Dieses Verzeichnis enthält nützliche SQL-Abfragen für die Analyse der Mainz 05 Daten.

## Verfügbare Queries

### siegquote_nach_saison_wettbewerb.sql

Zeigt eine Übersicht über den Anteil an Siegen von Mainz 05 je Saison und Wettbewerb.

**Ausgabe:**
- Saison (z.B. "2023-24")
- Wettbewerb (Bundesliga, DFB-Pokal, Europapokal)
- Anzahl Spiele gesamt
- Anzahl Siege
- Anzahl Unentschieden
- Anzahl Niederlagen
- Siegquote in Prozent
- Gesamtpunkte
- Punkte pro Spiel

**Verwendung:**

1. **Direkt in PostgreSQL:**
   ```bash
   psql $DB_URL -f sql_queries/siegquote_nach_saison_wettbewerb.sql
   ```

2. **Über die API:**
   ```
   "Zeige mir die Siegquote von Mainz 05 nach Saison und Wettbewerb"
   ```

3. **In Python:**
   ```python
   import psycopg2
   from pathlib import Path
   
   with open('sql_queries/siegquote_nach_saison_wettbewerb.sql') as f:
       query = f.read()
   
   conn = psycopg2.connect(os.getenv("DB_URL"))
   with conn.cursor() as cur:
       cur.execute(query)
       results = cur.fetchall()
       for row in results:
           print(row)
   ```

## Hinweise

- Die Abfrage verwendet eine CTE (Common Table Expression), um die team_id von Mainz 05 automatisch zu finden
- Falls die team_id bekannt ist, kann die vereinfachte Version am Ende der Datei verwendet werden
- Die Abfrage filtert automatisch Spiele ohne Ergebnis (NULL-Werte) heraus
- Sortierung: Neueste Saisons zuerst, dann nach Wettbewerb

