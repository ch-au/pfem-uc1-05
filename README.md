# FSV Mainz 05 Database & Archive
**Status:** ✅ Production Ready | **Last Updated:** 2025-11-09

A comprehensive database of **FSV Mainz 05** football data from **1905-2025** (3,305 matches, 10,094 players) with FastAPI backend, React frontend, and natural language SQL querying.

**🎯 New here? Start with:** [QUICK_START.md](QUICK_START.md)

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

### **Start Here**
- 📖 [QUICK_START.md](QUICK_START.md) - Get started in 5 minutes
- 📊 [docs/SCHEMA_DOCUMENTATION_2025.md](docs/SCHEMA_DOCUMENTATION_2025.md) - Complete schema reference (Nov 2025)
- 🚀 [docs/MATERIALIZED_VIEWS_REFERENCE.md](docs/MATERIALIZED_VIEWS_REFERENCE.md) - Fast query guide
- 📝 [COMPLETE_SUMMARY.md](COMPLETE_SUMMARY.md) - Full project summary

### **Technical Details**
- **Parser**: `docs/PARSER_IMPROVEMENTS.md` - Parser documentation
- **Performance**: `docs/PERFORMANCE_OPTIMIZATION.md` - Optimization guide
- **Migrations**: `database/migrations/` - Schema migration history
- **Testing**: `docs/TESTING_GUIDE.md` - How to test
- **Changelog**: `docs/CHANGELOG.md` - Version history

### **Recent Updates (Nov 2025)**
- ✅ Fixed duplicate team issue (Bundesliga data now visible)
- ✅ Added unique constraints (prevent duplicate events)
- ✅ Added foreign keys (enable table joins)
- ✅ Created 4 materialized views (100-400x speedup)
- ✅ Updated parser (recognizes "FSV" = "1. FSV Mainz 05")

## 🧪 Testing

Test the improved parser:
```bash
python tests/test_improved_parser.py --season 2010-11
```

## 📦 Requirements

See `requirements.txt`.

## 📄 License

Parses publicly available historical data from the fsv05.de archive.
