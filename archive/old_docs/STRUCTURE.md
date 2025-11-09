# Projektstruktur

## Übersicht

Das Projekt wurde neu strukturiert, um eine klarere Trennung zwischen Backend, Frontend und Datenparsing zu schaffen.

## Verzeichnisstruktur

```
05app/
├── backend/              # Backend-Services (FastAPI, Services, Agents)
│   ├── app.py           # Haupt-FastAPI-Anwendung
│   ├── chatbot_service.py
│   ├── quiz_service.py
│   ├── quiz_generator.py
│   ├── final_agent.py   # SQL Agent
│   ├── llm_service.py
│   ├── models.py        # Pydantic Models
│   ├── config.py        # Konfiguration
│   └── prompts.yaml     # LLM Prompts
│
├── parsing/              # Datenparsing-Module
│   ├── comprehensive_fsv_parser.py
│   ├── comprehensive_player_goal_parser.py
│   ├── consolidate_all_mainz_teams.py
│   └── data_cleansing/   # Datenbereinigung
│
├── frontend/             # React Frontend
│   └── src/
│
├── database/            # Database-Scripts und SQL
│
├── scripts/             # Utility-Scripts
│
├── tests/               # Tests
│
├── docs/               # Dokumentation
│
├── archive/            # Alte/Archivierte Dateien
│
├── run.py              # Server-Start-Script
└── start_server.py     # Alternative Server-Start-Script
```

## Wichtige Änderungen

### Backend (`backend/`)
- Alle Backend-Services wurden nach `backend/` verschoben
- Imports verwenden jetzt relative Imports (z.B. `from .config import Config`)
- `app.py` ist die Haupt-FastAPI-Anwendung

### Parsing (`parsing/`)
- Alle Parsing-bezogenen Dateien wurden nach `parsing/` verschoben
- `data_cleansing/` ist jetzt ein Unterordner von `parsing/`

### Server starten

```bash
# Option 1: Mit run.py
python run.py

# Option 2: Mit start_server.py
python start_server.py
```

Beide Scripts wurden aktualisiert, um auf `backend.app:app` zu verweisen.

## Nächste Schritte

- UI/UX Verbesserungen im `frontend/` Verzeichnis
- Datenparsing bleibt isoliert im `parsing/` Verzeichnis

