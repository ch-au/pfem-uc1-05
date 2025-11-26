# Testing Guide

## Prerequisites

1. **Initialize Database Schema**
   ```bash
   python database/init_quiz_schema.py
   ```

2. **Set Environment Variables** (in `.env` file)
   ```
   DB_URL=your_postgres_url
   OPENAI_API_KEY=your_openai_key
   LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
   LANGFUSE_SECRET_KEY=your_langfuse_secret_key
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the Server**
   ```bash
   python app.py
   # or
   uvicorn app:app --reload
   ```

## Quick Test Script

Run the automated test script:
```bash
python test_api.py
```

This will test all endpoints automatically.

## Manual Testing

### 1. Health Check
```bash
curl http://localhost:8000/health
```

### 2. Chatbot Mode

#### Create a chat session:
```bash
curl -X POST http://localhost:8000/chat/session \
  -H "Content-Type: application/json" \
  -d '{"metadata": {}}'
```

Response: `{"session_id": "..."}`

#### Send a message (data query):
```bash
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "YOUR_SESSION_ID",
    "message": "Wer ist der Top-Torschütze von Mainz 05?"
  }'
```

#### Send a general question:
```bash
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "YOUR_SESSION_ID",
    "message": "Erzähle mir etwas über die Geschichte von Mainz 05."
  }'
```

#### Get chat history:
```bash
curl http://localhost:8000/chat/history/YOUR_SESSION_ID
```

### 3. Quiz Mode

#### Create a quiz game:
```bash
curl -X POST http://localhost:8000/quiz/game \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Spieler",
    "difficulty": "medium",
    "num_rounds": 5,
    "player_names": ["Alice", "Bob"]
  }'
```

Response: `{"game_id": "...", "message": "Game created successfully"}`

#### Start the game:
```bash
curl -X POST http://localhost:8000/quiz/game/YOUR_GAME_ID/start
```

#### Get current question:
```bash
curl http://localhost:8000/quiz/game/YOUR_GAME_ID/question
```

Response includes:
- `question_text`: The question
- `options`: Array of 4 options (correct + 3 alternatives, shuffled)
- `round_id`: ID for submitting answers
- `round_number`: Current round number

#### Submit an answer:
```bash
curl -X POST http://localhost:8000/quiz/game/YOUR_GAME_ID/answer \
  -H "Content-Type: application/json" \
  -d '{
    "round_id": "YOUR_ROUND_ID",
    "answer": {
      "player_name": "Alice",
      "answer": "Selected Answer Text",
      "time_taken": 5.5
    }
  }'
```

Response: `{"correct": true/false, "correct_answer": "...", "points_earned": 100}`

#### Get leaderboard:
```bash
curl http://localhost:8000/quiz/game/YOUR_GAME_ID/leaderboard
```

#### Advance to next round:
```bash
curl -X POST http://localhost:8000/quiz/game/YOUR_GAME_ID/next
```

#### Get game state:
```bash
curl http://localhost:8000/quiz/game/YOUR_GAME_ID
```

## Testing with Python (Interactive)

```python
import requests

BASE_URL = "http://localhost:8000"

# Chat test
session_resp = requests.post(f"{BASE_URL}/chat/session", json={})
session_id = session_resp.json()["session_id"]

message_resp = requests.post(
    f"{BASE_URL}/chat/message",
    json={
        "session_id": session_id,
        "message": "Wer ist der Top-Torschütze?"
    }
)
print(message_resp.json())

# Quiz test
game_resp = requests.post(
    f"{BASE_URL}/quiz/game",
    json={
        "topic": "Spieler",
        "difficulty": "medium",
        "num_rounds": 3,
        "player_names": ["Player1", "Player2"]
    }
)
game_id = game_resp.json()["game_id"]

start_resp = requests.post(f"{BASE_URL}/quiz/game/{game_id}/start")
question_resp = requests.get(f"{BASE_URL}/quiz/game/{game_id}/question")
print(question_resp.json())
```

## Using FastAPI Interactive Docs

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

You can test all endpoints interactively in the browser!

## Common Issues

1. **"Chatbot service not initialized"**
   - Check that Langfuse API keys are set in `.env`
   - Check server logs for initialization errors

2. **"Quiz service not initialized"**
   - Ensure database schema is initialized: `python database/init_quiz_schema.py`
   - Check database connection in `.env`

3. **"Game not found"**
   - Make sure you're using the correct `game_id` from the create response

4. **Database errors**
   - Verify Postgres is running and accessible
   - Check `DB_URL` in `.env` is correct
   - Run schema initialization script

## Expected Behavior

- **Chat**: Answers data questions with SQL queries, general questions with LLM
- **Quiz**: Generates questions dynamically (may take a few seconds per question)
- **Scoring**: Fast answers get bonus points, correct answers get base points
- **Leaderboard**: Updates after each round


