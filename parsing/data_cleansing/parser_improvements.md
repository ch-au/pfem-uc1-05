# Parser-Verbesserungsplan

Basierend auf Analyse von 1,056 dokumentierten Fehlern.

## Übersicht

- **Gesamtfehler**: 1,056
- **Verbesserungen vorgeschlagen**: 7

## Fehler-Verteilung

### Nach Kategorie

- **contains_comma**: 385
- **goal_text**: 299
- **invalid_pattern**: 232
- **trainer_name**: 93
- **referee_name**: 41
- **error_text**: 5
- **too_long**: 1

### Nach Parsing-Methode

- **parse_team_block**: 579
- **parse_goal_table**: 395
- **extract_match_details**: 3

## Parser-Verbesserungen

### 1. Trainer-Namen werden als Spieler erkannt

- **Priorität**: high
- **Betroffene Methode**: `get_or_create_player`
- **Anzahl Fehler**: 93
- **Code-Stelle**: comprehensive_fsv_parser.py:579 (get_or_create_player)
- **Lösung**: Add validation: Check if name contains "Trainer:", "FSV-Trainer", "Coach" before creating player
- **Beispiele**:
  - `FSV-Trainer: Baas Schiedsrichter: Schmitt (Landau) Borussia-Trainer: Oles`
  - `FSV-Trainer: Baas`
  - `Borussia-Trainer: Oles`
  - `FSV-Trainer: Baas Schiedsrichter: Deuschel (Mundenheim) FCK-Trainer: Schneider`
  - `FCK-Trainer: Schneider`

### 2. Schiedsrichter-Namen werden als Spieler erkannt

- **Priorität**: high
- **Betroffene Methode**: `get_or_create_player`
- **Anzahl Fehler**: 41
- **Code-Stelle**: comprehensive_fsv_parser.py:579 (get_or_create_player)
- **Lösung**: Add validation: Check if name contains "Schiedsrichter:", "Schiedsrichterin:" before creating player
- **Beispiele**:
  - `Schiedsrichter: Schmitt (Landau)`
  - `Schiedsrichter: Deuschel (Mundenheim)`
  - `Schiedsrichter: Siebert (Mannheim)`
  - `Schiedsrichter: Bicha (Zweibrücken)`
  - `Schiedsrichter: Sparing (Kassel)`

### 3. Vollständiger Tor-Text wird als Spielername erkannt

- **Priorität**: high
- **Betroffene Methode**: `parse_goal_table`
- **Anzahl Fehler**: 299
- **Code-Stelle**: comprehensive_fsv_parser.py:2104 (parse_goal_table)
- **Lösung**: Improve parse_goal_table: Extract only player name from goal text, not full "Tore 11. 0:1 ..." text
- **Beispiele**:
  - `Tore 5. 1:0 Schneider 42. 2:0 Kasperski 69. 2:1 Reichert (FE, Mangold) 73. 3:1 Sommer (ET)`
  - `5. 1:0 Schneider`
  - `42. 2:0 Kasperski`
  - `69. 2:1 Reichert (FE, Mangold)`
  - `73. 3:1 Sommer (ET)`

### 4. Fehlertext ("FE,", "ET,", "HE,") wird als Spielername erkannt

- **Priorität**: medium
- **Betroffene Methode**: `parse_substitution_entry`
- **Anzahl Fehler**: 5
- **Code-Stelle**: comprehensive_fsv_parser.py:2049 (parse_substitution_entry)
- **Lösung**: Improve parse_substitution_entry: Filter prefixes "FE,", "ET,", "HE," before extracting player names
- **Beispiele**:
  - `FE, Liebers an Klopp`
  - `FE, Klopp an Antwerpen`
  - `FE, Klopp an Rus`
  - `ET, Latza`
  - `HE, Hazard`

### 5. Namen enthalten Kommas (oft Parsing-Fehler)

- **Priorität**: medium
- **Betroffene Methode**: `get_or_create_player`
- **Anzahl Fehler**: 385
- **Code-Stelle**: comprehensive_fsv_parser.py:579 (get_or_create_player)
- **Lösung**: Add validation: Warn or reject player names containing commas (unless it's a known pattern)
- **Beispiele**:
  - `ET, Schmitt`
  - `wdh. FE, Lipponer`
  - `FE, Janowski an Dr. Brandel`
  - `FE, Rauch an Bickerle`
  - `ET, Becker`

### 6. Namen beginnen mit ungültigen Zeichen oder sind zu kurz

- **Priorität**: medium
- **Betroffene Methode**: `get_or_create_player`
- **Anzahl Fehler**: 232
- **Code-Stelle**: comprehensive_fsv_parser.py:579 (get_or_create_player)
- **Lösung**: Add validation: Reject names starting with non-letters, single characters, or only numbers
- **Beispiele**:
  - `? BAPTISTELLA`
  - `ET`
  - `-`
  - `? SCHULZ`
  - `? VEITH`

### 7. Trainer-Namen werden aus Team-Block als Spieler extrahiert

- **Priorität**: high
- **Betroffene Methode**: `parse_team_block`
- **Anzahl Fehler**: 579
- **Code-Stelle**: comprehensive_fsv_parser.py:2004 (parse_team_block)
- **Lösung**: Improve parse_team_block: Filter out cells containing "Trainer:", "FSV-Trainer" before processing
- **Beispiele**:
  - `? BAPTISTELLA`
  - `? SCHULZ`
  - `? VEITH`
  - `? SANDER`
  - `HE`
  - `? NEISCHE`
  - `? LORENZ`
  - `? ENDERS`
  - `? BRANDNER`
  - `? GRASS`

## Beispiele nach Kategorie

### invalid_pattern

- **Falsch**: `? BAPTISTELLA`
  - **Korrekt**: `? BAPTISTELLA`
  - **Methode**: `parse_team_block`
- **Falsch**: `ET`
  - **Korrekt**: `KARL-HEINZ WETTIG`
  - **Methode**: `parse_goal_table`
- **Falsch**: `-`
  - **Korrekt**: `MANFRED KIPP`
  - **Methode**: `parse_goal_table`
- **Falsch**: `? SCHULZ`
  - **Korrekt**: `? SCHULZ`
  - **Methode**: `parse_team_block`
- **Falsch**: `? VEITH`
  - **Korrekt**: `? VEITH`
  - **Methode**: `parse_team_block`

### contains_comma

- **Falsch**: `ET, Schmitt`
  - **Korrekt**: `FRANK SCHMITT`
  - **Methode**: `parse_goal_table`
- **Falsch**: `wdh. FE, Lipponer`
  - **Korrekt**: `PAUL LIPPONER sen.`
  - **Methode**: `parse_goal_table`
- **Falsch**: `FE, Janowski an Dr. Brandel`
  - **Korrekt**: `FELIX BRAND`
  - **Methode**: `parse_goal_table`
- **Falsch**: `FE, Rauch an Bickerle`
  - **Korrekt**: `HORST-DIETER RAUCH`
  - **Methode**: `parse_goal_table`
- **Falsch**: `ET, Becker`
  - **Korrekt**: `TIMOTHY BECK`
  - **Methode**: `parse_goal_table`

### goal_text

- **Falsch**: `Tore 5. 1:0 Schneider 42. 2:0 Kasperski 69. 2:1 Reichert (FE, Mangold) 73. 3:1 Sommer (ET)`
  - **Korrekt**: `ROMAN SCHNEIDER`
  - **Methode**: `parse_team_block`
- **Falsch**: `5. 1:0 Schneider`
  - **Korrekt**: `ROMAN SCHNEIDER`
  - **Methode**: `parse_team_block`
- **Falsch**: `42. 2:0 Kasperski`
  - **Methode**: `parse_team_block`
- **Falsch**: `69. 2:1 Reichert (FE, Mangold)`
  - **Korrekt**: `WILLI REICHERT`
  - **Methode**: `parse_team_block`
- **Falsch**: `73. 3:1 Sommer (ET)`
  - **Korrekt**: `WERNER SOMMER`
  - **Methode**: `parse_team_block`

### trainer_name

- **Falsch**: `FSV-Trainer: Baas Schiedsrichter: Schmitt (Landau) Borussia-Trainer: Oles`
  - **Korrekt**: `MANFRED RUSS`
  - **Methode**: `parse_team_block`
- **Falsch**: `FSV-Trainer: Baas`
  - **Methode**: `parse_team_block`
- **Falsch**: `Borussia-Trainer: Oles`
  - **Korrekt**: `MANFRED RUSS`
  - **Methode**: `parse_team_block`
- **Falsch**: `FSV-Trainer: Baas Schiedsrichter: Deuschel (Mundenheim) FCK-Trainer: Schneider`
  - **Korrekt**: `ROMAN SCHNEIDER`
  - **Methode**: `parse_team_block`
- **Falsch**: `FCK-Trainer: Schneider`
  - **Korrekt**: `ROMAN SCHNEIDER`
  - **Methode**: `parse_team_block`

### referee_name

- **Falsch**: `Schiedsrichter: Schmitt (Landau)`
  - **Korrekt**: `FRANK SCHMITT`
  - **Methode**: `parse_team_block`
- **Falsch**: `Schiedsrichter: Deuschel (Mundenheim)`
  - **Korrekt**: `HANS-JÜRGEN RICHTER`
  - **Methode**: `parse_team_block`
- **Falsch**: `Schiedsrichter: Siebert (Mannheim)`
  - **Korrekt**: `? SIEBERT`
  - **Methode**: `parse_team_block`
- **Falsch**: `Schiedsrichter: Bicha (Zweibrücken)`
  - **Korrekt**: `CHA DU-RI`
  - **Methode**: `parse_team_block`
- **Falsch**: `Schiedsrichter: Sparing (Kassel)`
  - **Korrekt**: `HARALD KASSEL`
  - **Methode**: `parse_team_block`

### error_text

- **Falsch**: `FE, Liebers an Klopp`
  - **Korrekt**: `FOLKER LIEBE`
  - **Methode**: `parse_goal_table`
- **Falsch**: `FE, Klopp an Antwerpen`
  - **Korrekt**: `JÜRGEN KLOPP`
  - **Methode**: `parse_goal_table`
- **Falsch**: `FE, Klopp an Rus`
  - **Korrekt**: `JÜRGEN KLOPP`
  - **Methode**: `parse_goal_table`
- **Falsch**: `ET, Latza`
  - **Korrekt**: `DANNY LATZA`
  - **Methode**: `parse_goal_table`
- **Falsch**: `HE, Hazard`
  - **Methode**: `parse_goal_table`

### too_long

- **Falsch**: `Hälfte: 22 Stöger 36 D. Schmidt 26 Nebel 23 Lucoqui 38 Fi. Müller 24 Papela 3 Aarón 43 Wilhelm 16 Bell 34 Nemeth 32 Rieß 80. 44 Roos`
  - **Korrekt**: `LARS SCHMIDT`
  - **Methode**: `parse_team_block`

