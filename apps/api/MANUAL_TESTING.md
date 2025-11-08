# Manual E2E Testing Guide

## Warum manuelles Testen?

Dieser Guide erklärt, wie Sie die **vollständige Pipeline** mit echten Services testen:
- ✅ Echte Gemini API Aufrufe
- ✅ Echte PostgreSQL Datenbankzugriffe
- ✅ Echtes Langfuse Tracing

---

## ⚠️ Container-Limitierung

**Problem**: Der Claude Code Container hat keinen Netzwerkzugriff zu externen APIs.

**Lösung**: Tests müssen auf Ihrem **lokalen System** ausgeführt werden.

---

## 🚀 Setup (Lokal)

### 1. Environment Variables

Erstellen Sie eine `.env` Datei im Projekt-Root:

\`\`\`bash
# PostgreSQL (z.B. Neon)
DB_URL=postgresql://user:password@host:port/database?sslmode=require

# Google Gemini API
GEMINI_API_KEY=AIza...  # Von ai.google.dev/aistudio

# Langfuse (optional - nutzt sonst lokale Prompts)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
\`\`\`

### 2. Dependencies installieren

\`\`\`bash
# Im Project Root
pnpm install
\`\`\`

### 3. Database Migration

\`\`\`bash
# Stelle sicher, dass Schema aktuell ist
psql $DB_URL -f database/quiz_schema.sql
psql $DB_URL -f database/migrations/002_extend_schema_for_ts_app.sql
\`\`\`

---

## 🧪 Test ausführen

### Automatischer E2E Test

\`\`\`bash
cd apps/api

# Stelle sicher ENV vars geladen sind
source ../../.env

# Führe vollständigen Test aus
pnpm exec tsx src/__tests__/manual/e2e-live-test.ts
\`\`\`

**Dieser Test wird**:
1. System Health Check durchführen
2. Chat Flow testen (User Frage → SQL → Antwort)
3. Quiz Flow testen (Game erstellen → Fragen generieren → Antworten)
4. Langfuse Trace IDs ausgeben
5. Zusammenfassung anzeigen

**Erwartete Ausgabe**:

\`\`\`
********************************************************************************
         FSV MAINZ 05 - MANUAL E2E TEST WITH LIVE SERVICES
********************************************************************************

This test will:
  • Make real API calls to Gemini (costs money!)
  • Write to your PostgreSQL database
  • Send traces to Langfuse
  • Take ~30-60 seconds to complete

================================================================================
🏥 SYSTEM HEALTH CHECK
================================================================================

[CHECK] PostgreSQL connection...
[DB] Connected
[CHECK] Gemini API...
[GEMINI] OK
[CHECK] Langfuse...
[LANGFUSE] Enabled
[CHECK] Quiz categories...
[SCHEMA] Found 6 quiz categories

================================================================================
🤖 CHAT FLOW TEST
================================================================================

[STEP 1] Creating chat session...
[SUCCESS] Session created: a1b2c3d4-...
[STEP 2] Sending message: "Wer ist der Rekordtorschütze von Mainz 05?"
[SUCCESS] Response received in 2340ms

📊 CHAT RESULTS
Message ID: msg-123...
Role: assistant
Content:
Der Rekordtorschütze von Mainz 05 ist Bopp mit 100 Toren in seiner Karriere.

Metadata:
  SQL Query: SELECT p.name, COUNT(*) as goals FROM public.goals g JOIN public.players p ON...
  Execution Time: 42ms
  Result Count: 1 rows
  Confidence: 0.95
  Visualization: stat

  Highlights:
    • 100 Tore in allen Wettbewerben
    • Aktiv von 1920 bis 1935
    • Vereinslegende und bis heute unerreicht

  Follow-up Questions:
    ? Wer ist der beste Torschütze in der Bundesliga?
    ? Wie viele Tore hat der zweitbeste Torschütze?

Langfuse Trace:
  Trace ID: trace-abc123
  View at: https://cloud.langfuse.com/traces/trace-abc123

[STEP 4] Verifying message in database...
[SUCCESS] Found 2 messages in history
[STEP 5] Cleaning up session...
[SUCCESS] Session deleted

================================================================================
🎮 QUIZ FLOW TEST
================================================================================

[STEP 1] Creating quiz game (2 rounds, easy difficulty)...
[SUCCESS] Game created in 15230ms: game-xyz789
[STEP 2] Verifying questions in database...
[SUCCESS] Found 2 questions

📊 QUIZ QUESTIONS
Question 1:
  Text: Wer ist der Rekordtorschütze von FSV Mainz 05?
  Difficulty: easy
  SQL: SELECT p.name FROM public.player_statistics ORDER BY tore_gesamt DESC LI...
  Trace: trace-question-1

Question 2:
  Text: In welchem Jahr stieg Mainz 05 zum ersten Mal in die Bundesliga auf?
  Difficulty: easy
  SQL: SELECT MIN(s.start_year) FROM public.seasons s JOIN public.season_compet...
  Trace: trace-question-2

[STEP 4] Starting game...
[SUCCESS] Game started
[STEP 5] Getting first question...

Current Question:
  Wer ist der Rekordtorschütze von FSV Mainz 05?
  Alternatives: Bopp, Szalai, Noveski, Quaison

[STEP 6] Submitting answers...
[PLAYER1] Correct! Points: 94
[PLAYER2] Wrong! Points: 0

Correct Answer: Bopp
Explanation: Bopp ist mit 100 Toren der erfolgreichste Torschütze...

[STEP 7] Getting leaderboard...

🏆 LEADERBOARD
Game ID: game-xyz789

🥇 TestPlayer1
   Score: 94 points
   Correct: 1/1
   Avg Time: 3.5s

🥈 TestPlayer2
   Score: 0 points
   Correct: 0/1
   Avg Time: 8.0s

[STEP 8] Cleaning up game...
[SUCCESS] Game deleted

================================================================================
📝 TEST SUMMARY
================================================================================

System Health:
  Database: ✅
  Gemini API: ✅
  Langfuse: ✅
  Quiz Categories: 6

Chat Flow:
  Status: ✅ Passed
  Duration: 2340ms
  Messages: 2
  Trace: https://cloud.langfuse.com/traces/trace-abc123

Quiz Flow:
  Status: ✅ Passed
  Game Creation: 15230ms
  Questions: 2
  Players: 2
  Traces:
    1. https://cloud.langfuse.com/traces/trace-question-1
    2. https://cloud.langfuse.com/traces/trace-question-2

Overall: ✅ ALL TESTS PASSED

View all traces in Langfuse Dashboard:
https://cloud.langfuse.com
\`\`\`

---

## 🔍 Was wird getestet?

### Chat Flow (PROMPT 1 + PROMPT 2)

1. **Session erstellen** → DB write
2. **User-Frage senden**: "Wer ist Rekordtorschütze?"
3. **PROMPT 1** (Langfuse: `chat-sql-generator`)
   - Input: User-Frage + Schema Context
   - Gemini API Call
   - Output: SQL Query + Confidence
   - Trace in Langfuse
4. **SQL ausführen** → PostgreSQL
5. **PROMPT 2** (Langfuse: `chat-answer-formatter`)
   - Input: Frage + SQL Result
   - Gemini API Call
   - Output: Formatierte Antwort + Highlights
   - Trace in Langfuse
6. **Antwort speichern** → DB write
7. **Verify**: Message in DB History

### Quiz Flow (PROMPT 3 + PROMPT 4)

1. **Game erstellen** mit 2 Runden
2. **PROMPT 3** (Langfuse: `quiz-question-generator`)
   - Input: Kategorie + Difficulty
   - Gemini API Call
   - Output: 2 Fragen mit SQL Queries
   - Trace in Langfuse
3. **Für jede Frage**:
   - SQL ausführen → Daten holen
   - **PROMPT 4** (Langfuse: `quiz-answer-generator`)
     - Input: Frage + SQL Result
     - Gemini API Call
     - Output: Richtige Antwort + 3 Falsche
     - Trace in Langfuse
   - In DB speichern
4. **Game starten**
5. **Frage abrufen**
6. **Antworten einreichen** (2 Spieler)
7. **Leaderboard abrufen**
8. **Verify**: Scores korrekt berechnet

---

## 🔬 Langfuse Traces analysieren

Nach dem Test können Sie in Langfuse:

### 1. Traces Dashboard öffnen
https://cloud.langfuse.com

### 2. Suchen nach Traces
- **Chat**: Suche nach `chat-sql-generation` oder `chat-answer-formatting`
- **Quiz**: Suche nach `quiz-question-generation` oder `quiz-answer-generation`

### 3. Trace Details ansehen
Für jeden Trace sehen Sie:
- **Input**: Prompt mit allen Variablen
- **Output**: Gemini Response (JSON)
- **Tokens**: Prompt Tokens, Completion Tokens, Total
- **Latency**: Zeit in Millisekunden
- **Model**: `gemini-2.0-flash-exp`
- **Metadata**: User Question, Category, Difficulty, etc.

### 4. Verknüpfte Generations
- SQL Generation → Answer Formatting (Chat)
- Question Generation → Answer Generation (Quiz)

---

## 📊 Erwartete Kosten

### Gemini API (gemini-2.0-flash-exp)

**Pricing**:
- Input: $0.075 per 1M tokens
- Output: $0.30 per 1M tokens

**Geschätzt pro Test-Run**:
- Chat Flow: ~2000 input + ~500 output tokens = $0.0003
- Quiz Flow (2 Fragen): ~4000 input + ~1000 output tokens = $0.0006
- **Total**: ~$0.001 (0.1 Cent) pro Test

**Tipp**: Setzen Sie ein Budget Limit in Google AI Studio!

---

## 🐛 Troubleshooting

### Problem: `EAI_AGAIN` oder DNS-Fehler

**Ursache**: Keine Netzwerkverbindung

**Lösung**:
- Prüfen Sie Internet-Verbindung
- Testen Sie: `curl https://generativelanguage.googleapis.com/`
- Bei Firewall: Ports 443 (HTTPS) freigeben

---

### Problem: `DB connection failed`

**Ursache**: Datenbank nicht erreichbar oder falsche Credentials

**Lösung**:
\`\`\`bash
# Test connection
psql $DB_URL -c "SELECT 1"

# Check SSL mode
echo $DB_URL | grep sslmode
\`\`\`

---

### Problem: `Gemini API error`

**Ursache**: Invalid API Key oder Quota exceeded

**Lösung**:
\`\`\`bash
# Test API key
curl -H "Content-Type: application/json" \\
  -d '{"contents":[{"parts":[{"text":"test"}]}]}' \\
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=$GEMINI_API_KEY"

# Check quota: https://ai.google.dev/pricing
\`\`\`

---

### Problem: `Langfuse not working`

**Ursache**: Keys nicht gesetzt (nicht kritisch!)

**Lösung**:
- Tests funktionieren **ohne Langfuse** (nutzen lokale Prompts)
- Für Tracing: Keys in `.env` setzen
- Verify: https://cloud.langfuse.com/settings

---

## 🎯 Manueller Test (ohne Script)

Falls Sie den Test manuell durchführen möchten:

### Chat Test

\`\`\`bash
cd apps/api

# Start server
pnpm dev

# In neuem Terminal:
# 1. Create session
SESSION_ID=$(curl -X POST http://localhost:8000/api/chat/session | jq -r '.session_id')

# 2. Send message
curl -X POST http://localhost:8000/api/chat/message \\
  -H "Content-Type: application/json" \\
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"content\": \"Wer ist der Rekordtorschütze von Mainz 05?\"
  }" | jq

# 3. Check Langfuse trace ID in response
\`\`\`

### Quiz Test

\`\`\`bash
# 1. Create game
GAME_ID=$(curl -X POST http://localhost:8000/api/quiz/game \\
  -H "Content-Type: application/json" \\
  -d '{
    "difficulty": "easy",
    "num_rounds": 1,
    "player_names": ["TestPlayer"]
  }' | jq -r '.game_id')

# 2. Start game
curl -X POST http://localhost:8000/api/quiz/game/$GAME_ID/start

# 3. Get question
curl http://localhost:8000/api/quiz/game/$GAME_ID/question | jq

# 4. Submit answer
curl -X POST http://localhost:8000/api/quiz/game/$GAME_ID/answer \\
  -H "Content-Type: application/json" \\
  -d '{
    "player_name": "TestPlayer",
    "answer": "Bopp",
    "time_taken": 5.0
  }' | jq

# 5. Get leaderboard
curl http://localhost:8000/api/quiz/game/$GAME_ID/leaderboard | jq
\`\`\`

---

## ✅ Erwartetes Ergebnis

Nach erfolgreichem Test sollten Sie haben:

1. ✅ Chat-Antwort mit Highlights und Follow-up Questions
2. ✅ Quiz mit generierten Fragen und Antworten
3. ✅ Alle Daten in PostgreSQL gespeichert
4. ✅ Langfuse Traces sichtbar im Dashboard
5. ✅ Beide Flows in <60s abgeschlossen

---

## 📚 Weiterführende Links

- **Gemini API Docs**: https://ai.google.dev/gemini-api/docs
- **Langfuse Dashboard**: https://cloud.langfuse.com
- **PostgreSQL**: https://neon.tech/docs
- **API Reference**: siehe `apps/api/README.md`
