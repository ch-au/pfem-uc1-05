# AI Prompts Configuration

Diese Datei erklärt wie du die AI-Prompts für deine Anwendung konfigurierst.

## 📁 Dateien

- **`prompts.yaml`**: Zentrale Konfiguration aller AI-Prompts
- **`../../../prompts/fallback/*.txt`**: Fallback-Prompts als lokale Dateien

## 🎯 Wie funktioniert es?

Das System lädt Prompts in dieser Reihenfolge:

1. **Langfuse** (wenn aktiviert und verfügbar)
   - Prompt-Name aus `langfuse_name` in YAML
   - Optional: Spezifische Version mit `langfuse_label`
   
2. **Lokaler Fallback** (wenn Langfuse fehlschlägt)
   - Datei aus `fallback_file` in YAML
   - Pfad: `prompts/fallback/*.txt`

## ⚙️ YAML Struktur

```yaml
prompts:
  prompt-key-name:                    # Eindeutiger Key für Code-Referenz
    langfuse_name: 'langfuse-prompt'  # Name in Langfuse
    langfuse_label: 'production'      # Optional: Version/Label
    fallback_file: 'prompt.txt'       # Lokale Fallback-Datei
    llm_config:                       # LLM-Parameter
      temperature: 0.7                # Kreativität (0.0-1.0)
      max_tokens: 1500                # Maximale Antwortlänge
      response_format: 'json'         # 'json' oder 'text'
    description: 'Was macht dieser Prompt?'
```

## 🔧 Neuen Prompt hinzufügen

**1. Eintrag in `prompts.yaml` erstellen:**

```yaml
prompts:
  mein-neuer-prompt:
    langfuse_name: 'mein-neuer-prompt'
    langfuse_label: 'production'
    fallback_file: 'mein-neuer-prompt.txt'
    llm_config:
      temperature: 0.5
      max_tokens: 2000
      response_format: 'json'
    description: 'Beschreibung des Prompts'
```

**2. Fallback-Datei erstellen** (`prompts/fallback/mein-neuer-prompt.txt`):

```
SYSTEM INSTRUCTION:
Du bist ein hilfreicher Assistent...

---

Benutzerfrage: {{userQuestion}}
Kontext: {{context}}
```

**3. Im Code verwenden:**

```typescript
// In PromptsService eine neue Methode erstellen
async executeMyNewPrompt(input: MyInput) {
  const promptKey = 'mein-neuer-prompt';
  const { system, user, config } = await this.loadPromptTemplate(promptKey);
  
  // Compile template with variables
  const userPrompt = this.compileTemplate(user, {
    userQuestion: input.question,
    context: input.context,
  });
  
  // Call LLM with config from YAML
  const { data } = await openRouterService.generateJSON(userPrompt, {
    systemInstruction: system,
    temperature: config.llm_config.temperature,
    maxOutputTokens: config.llm_config.max_tokens,
    responseFormat: config.llm_config.response_format,
  });
  
  return data;
}
```

## 📝 Prompt-Variablen

Verwende `{{variableName}}` in deinen Prompts:

**Beispiel:**
```
USER PROMPT:
Beantworte die Frage: {{userQuestion}}
Basierend auf diesen Daten: {{sqlResult}}
```

**Im Code:**
```typescript
const userPrompt = this.compileTemplate(template.user, {
  userQuestion: 'Wer war Torschützenkönig 2010?',
  sqlResult: JSON.stringify(results),
});
```

## 🎨 LLM-Parameter

### temperature
- **0.0-0.3**: Sehr präzise, deterministische Antworten (SQL, Daten)
- **0.4-0.7**: Ausgewogen (Chat, Formatierung)
- **0.8-1.0**: Kreativ, variantenreich (Quiz-Fragen)

### max_tokens
- SQL-Generation: 2000
- Chat-Antworten: 1500
- Quiz-Generierung: 10000 (viele Fragen)

### response_format
- `'json'`: Strukturierte JSON-Antwort
- `'text'`: Freier Text

## 🔄 Änderungen anwenden

1. YAML bearbeiten
2. Server neustarten (automatisch bei Replit)
3. Fertig! Keine Code-Änderungen nötig ✅

## 🌐 Langfuse Integration

**Prompts in Langfuse verwalten:**

1. Gehe zu [Langfuse Dashboard](https://cloud.langfuse.com)
2. Erstelle neuen Prompt mit dem Namen aus `langfuse_name`
3. Setze Label auf `production` (oder eigenes Label)
4. System lädt automatisch neueste Version

**Format in Langfuse:**
```
SYSTEM INSTRUCTION:
Your system prompt here...

---

Your user prompt here with {{variables}}
```

## 📋 Aktuelle Prompts

| Key | Beschreibung | Temperatur |
|-----|--------------|------------|
| `chat-sql-generator` | SQL aus Fragen generieren | 0.1 |
| `chat-answer-formatter` | SQL-Ergebnisse formatieren | 0.7 |
| `quiz-question-generator` | Quiz-Fragen erstellen | 0.8 |
| `quiz-answer-generator` | Falsche Antworten generieren | 0.6 |

## 🚨 Troubleshooting

**Fehler: "Prompt configuration not found"**
- Prüfe ob Key in `prompts.yaml` existiert
- Achte auf exakte Schreibweise (case-sensitive)

**Fehler: "Failed to load prompt from both sources"**
- Prüfe ob Fallback-Datei existiert
- Prüfe Dateiformat (muss `---` Separator haben)

**Prompt wird nicht aus Langfuse geladen**
- Prüfe Langfuse-Keys in `.env`
- Prüfe ob Prompt-Name in Langfuse existiert
- Prüfe Console-Logs für Details
