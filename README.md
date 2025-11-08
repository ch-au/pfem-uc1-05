# FSV Mainz 05 SQL Assistant & Archive

FastAPI app that lets you ask natural-language questions about the FSV Mainz 05 database and returns SQL + results, with configurable prompts loaded from YAML. Includes parsers and notebooks to rebuild or explore the historical archive.

## 🗂️ Structure

```
05app/
├── app.py                    # FastAPI app
├── final_agent.py            # LLM-driven SQL agent
├── config.py                 # Configuration via env vars
├── prompts.yaml              # Editable prompts (YAML)
├── frontend/                 # React + TypeScript frontend
├── comprehensive_fsv_parser.py  # Main parser with validation
├── data_cleansing/           # Data quality scripts
├── tests/                    # Test scripts
├── docs/                     # Documentation
└── archive/                  # Archived/legacy files
```

## 🚀 Quick Start

### Backend Setup

1) Install dependencies
```bash
python3 -m pip install -r requirements.txt
```

2) Configure environment (create `.env` or export directly)
```bash
export OPENAI_API_KEY="sk-..."
export PG_ENABLED=true
export PG_HOST=your-host
export PG_PORT=5432
export PG_DATABASE=fsv05
export PG_USER=your-user
export PG_PASSWORD=your-password
```

3) Start server
```bash
uvicorn app:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## 📊 Database & Parser

### Rebuild Database

To rebuild the SQLite database from the HTML archive:

```bash
python archive/scripts/reparse_and_upload.py
```

This will:
1. Parse all seasons with improved parser (validation, duplicate prevention)
2. Upload to PostgreSQL
3. Apply performance optimizations

### Parser Features

- ✅ **Automatic league extraction** - Detects league names from HTML (no hardcoded "Bundesliga")
- ✅ **Competition level detection** - Classifies leagues (first_division, second_division, cup, etc.)
- ✅ **Duplicate prevention** - Prevents duplicate cards, goals, substitutions, lineups
- ✅ **European competitions** - Full support for UEFA, Europa League, Intertoto, etc.
- ✅ **Data validation** - Filters invalid player names (trainers, referees, goal text)
- ✅ **Unicode support** - Handles names with accents (Á, É, etc.)
- ✅ **Transaction-based** - Ensures data integrity

### Data Quality

The parser includes comprehensive validation:
- Filters trainer names, referee names, goal text
- Validates name patterns (length, characters)
- Handles Unicode characters correctly
- Logs warnings for suspicious entries

See `data_cleansing/` for data quality scripts and analysis.

## 📚 Documentation

- **Parser**: `docs/PARSER_IMPROVEMENTS.md` - Complete parser documentation
- **Schema**: `docs/SCHEMA_DOCUMENTATION.md` - Database schema
- **Performance**: `docs/PERFORMANCE_OPTIMIZATION.md` - Optimization guide
- **Testing**: `docs/TESTING_GUIDE.md` - How to test
- **Changelog**: `docs/CHANGELOG.md` - Version history

## 🧪 Testing

Test the improved parser:
```bash
python tests/test_improved_parser.py --season 2010-11
```

## 📦 Requirements

See `requirements.txt`.

## 📄 License

Parses publicly available historical data from the fsv05.de archive.
