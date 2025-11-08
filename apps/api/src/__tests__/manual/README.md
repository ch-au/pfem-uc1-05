# Manual Testing Scripts

Diese Skripte testen die **vollständige Pipeline** mit echten Services.

## ⚠️ Wichtig

Diese Tests:
- Machen **echte API Calls** zu Gemini (kostet Geld!)
- Schreiben in Ihre **echte Datenbank**
- Senden **Traces** zu Langfuse
- Müssen **lokal** (nicht im Container) ausgeführt werden

## 📁 Dateien

### `e2e-live-test.ts`

Vollständiger automatischer E2E Test:
- System Health Check
- Chat Flow (PROMPT 1 + PROMPT 2)
- Quiz Flow (PROMPT 3 + PROMPT 4)
- Langfuse Traces
- Zusammenfassung mit Links

**Ausführen**:
\`\`\`bash
# Stelle sicher ENV vars geladen sind
cd apps/api
source ../../.env

# Run test
pnpm exec tsx src/__tests__/manual/e2e-live-test.ts
\`\`\`

**Output**:
- Farbige Console-Ausgabe
- Schritt-für-Schritt Fortschritt
- Langfuse Trace URLs
- Test Summary

## 🚫 Warum nicht im Container?

Der Claude Code Container hat **keinen Netzwerkzugriff** zu:
- Gemini API (`generativelanguage.googleapis.com`)
- Neon Database (externe PostgreSQL)
- Langfuse Cloud (`cloud.langfuse.com`)

**Fehler**: `EAI_AGAIN` DNS Resolution Error

**Lösung**: Tests lokal auf Ihrem System ausführen.

## 📖 Dokumentation

Siehe `MANUAL_TESTING.md` für:
- Setup Anleitung
- Erwartete Ausgabe
- Langfuse Traces analysieren
- Troubleshooting
- Kosten-Kalkulation

## ✅ Voraussetzungen

1. **Environment Variables**:
   \`\`\`bash
   DB_URL=postgresql://...
   GEMINI_API_KEY=AIza...
   LANGFUSE_PUBLIC_KEY=pk-lf-...  # optional
   LANGFUSE_SECRET_KEY=sk-lf-...  # optional
   \`\`\`

2. **Database Schema**:
   \`\`\`bash
   psql $DB_URL -f database/quiz_schema.sql
   psql $DB_URL -f database/migrations/002_extend_schema_for_ts_app.sql
   \`\`\`

3. **Dependencies**:
   \`\`\`bash
   pnpm install
   \`\`\`

## 🎯 Schnelltest

Wenn Sie nur prüfen wollen ob alles funktioniert:

\`\`\`bash
# Start API server
cd apps/api
pnpm dev

# In neuem Terminal: Test Chat
curl -X POST http://localhost:8000/api/chat/session | jq
\`\`\`

Wenn das funktioniert, sollte auch der volle E2E Test laufen.
