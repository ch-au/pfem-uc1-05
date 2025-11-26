# Zusammenfassung: Parser-Korrektur für Freundschaftsspiele

## Durchgeführte Änderungen

### 1. Parser korrigiert ✅
**Datei:** `parsing/comprehensive_fsv_parser.py`

**Änderung:**
- `"profirest"` wurde aus der Liste der europäischen Wettbewerbe entfernt
- Freundschaftsspiele werden jetzt korrekt als "Freundschaftsspiele" klassifiziert

**Vorher:**
```python
for european_stub in ["profiuefa", "profiuec", "profiuecl", "profiintertoto", "profiueclq", "profirest"]:
    # "profirest" wurde fälschlicherweise als "Europapokal" klassifiziert
```

**Nachher:**
```python
# Europapokal-Wettbewerbe
for european_stub in ["profiuefa", "profiuec", "profiuecl", "profiintertoto", "profiueclq"]:
    ...

# Freundschaftsspiele separat
profirest_file = season_path / "profirest.html"
if profirest_file.exists():
    overview_files.append(("Freundschaftsspiele", "friendly", profirest_file))
```

### 2. Datenbank-Migration durchgeführt ✅
**Script:** `scripts/fix_freundschaftsspiele_classification.py`

**Ergebnis:**
- ✅ Wettbewerb "Freundschaftsspiele" erstellt (ID: 24)
- ✅ 66 falsch klassifizierte Spiele korrigiert
- ✅ 21 Saisons aktualisiert (2000-01 bis 2025-26)
- ✅ 0 falsch klassifizierte Europapokal-Spiele verbleiben

### 3. Query aktualisiert ✅
**Datei:** `sql_queries/siegquote_nach_saison_wettbewerb.sql`

**Änderung:**
- Filter für falsch klassifizierte Spiele entfernt (nicht mehr nötig)
- Hinweis hinzugefügt, wie man nur offizielle Wettbewerbsspiele filtert

## Ergebnis

Die Query zeigt jetzt korrekte Ergebnisse:
- **Freundschaftsspiele** werden als separater Wettbewerb angezeigt
- **Europapokal** zeigt nur noch echte Europapokal-Spiele
- **Bundesliga** und **DFB-Pokal** bleiben unverändert

### Beispiel: Saison 2018-19
- Bundesliga: 34 Spiele
- DFB-Pokal: 2 Spiele  
- Freundschaftsspiele: 3 Spiele (vorher fälschlicherweise als "Europapokal")
- Europapokal: 0 Spiele (korrekt - keine echten Europapokal-Spiele)

## Nächste Schritte

Für zukünftige Parses:
- ✅ Parser klassifiziert Freundschaftsspiele korrekt
- ✅ Keine manuelle Korrektur mehr nötig

Für bestehende Daten:
- ✅ Alle falsch klassifizierten Spiele wurden korrigiert
- ✅ Datenbank ist konsistent

## Verwandte Dateien

- `parsing/comprehensive_fsv_parser.py` - Parser (korrigiert)
- `scripts/fix_freundschaftsspiele_classification.py` - Migrations-Script
- `sql_queries/siegquote_nach_saison_wettbewerb.sql` - Query (aktualisiert)
- `docs/PARSER_KORREKTUR_PROFIREST.md` - Dokumentation
- `docs/EUROPAPOKAL_FALSCH_KLASSIFIZIERT.md` - Problem-Analyse

