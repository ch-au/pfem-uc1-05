from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import os
from pathlib import Path
import io
import csv
import logging
from datetime import date, datetime
from decimal import Decimal
from .final_agent import FinalSQLAgent as FSVSQLAgent
from .chatbot_service import ChatbotService
from .quiz_service import QuizService
from .models import QuizGameCreate, QuizAnswer

# Setup logging
logger = logging.getLogger("app")
if not logger.handlers:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def serialize_for_json(obj):
    """Convert non-JSON serializable objects to strings"""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    elif isinstance(obj, (bytes, bytearray)):
        return obj.decode('utf-8', errors='ignore')
    elif obj is None:
        return None
    else:
        return obj

app = FastAPI(title="FSV Mainz 05 SQL Query Assistant")

# Setup static files and templates
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent.parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# Serve React build if available (production)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")
    app.mount("/vite.svg", StaticFiles(directory=frontend_dist), name="frontend-vite-svg")

# Initialize services
sql_agent = None
chatbot_service = None
quiz_service = None

class QueryRequest(BaseModel):
    query: str

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global sql_agent, chatbot_service, quiz_service
    try:
        sql_agent = FSVSQLAgent()
        logger.info("SQL Agent initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize SQL Agent: {e}")
        sql_agent = None
    
    try:
        chatbot_service = ChatbotService()
        logger.info("Chatbot Service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Chatbot Service: {e}")
        chatbot_service = None
    
    try:
        quiz_service = QuizService()
        logger.info("Quiz Service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Quiz Service: {e}")
        quiz_service = None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Serve React build if available (production), otherwise fallback to old template
    react_index = frontend_dist / "index.html"
    if react_index.exists():
        return FileResponse(react_index)
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/query")
async def query_data(request: QueryRequest):
    """Process natural language query"""
    if sql_agent is None:
        raise HTTPException(
            status_code=503, 
            detail="SQL Agent not initialized. Please check your API keys and database connection."
        )
    
    try:
        result = sql_agent.query(request.query)
        logger.info("Query processed: success=%s sql_len=%s", result.get("success"), len(result.get("sql", "")))
        # Serialize dates and other non-JSON types
        serialized_result = serialize_for_json(result)
        return JSONResponse(content=serialized_result)
    except Exception as e:
        logger.error(f"Query error: {e}")
        return JSONResponse(
            content={"error": f"Query processing failed: {str(e)}"}, 
            status_code=500
        )

@app.post("/query_csv")
async def query_data_csv(request: QueryRequest):
    """Process natural language query and return CSV (header + rows)."""
    if sql_agent is None:
        raise HTTPException(
            status_code=503,
            detail="SQL Agent not initialized. Please check your API keys and database connection.")

    try:
        result = sql_agent.query(request.query)
        output = io.StringIO()
        writer = csv.writer(output)

        if not result.get("success"):
            writer.writerow(["error"])
            writer.writerow([result.get("error", "Query processing failed")])
        else:
            columns = result.get("columns") or []
            rows = result.get("rows") or []
            writer.writerow(columns)
            for row in rows:
                # Convert dates and other types to strings for CSV
                csv_row = []
                for v in row:
                    if v is None:
                        csv_row.append("")
                    elif isinstance(v, (date, datetime)):
                        csv_row.append(v.isoformat())
                    elif isinstance(v, Decimal):
                        csv_row.append(str(float(v)))
                    elif isinstance(v, (bytes, bytearray)):
                        csv_row.append(v.decode('utf-8', errors='ignore'))
                    else:
                        csv_row.append(str(v))
                writer.writerow(csv_row)

        output.seek(0)
        headers = {
            "Content-Disposition": "attachment; filename=results.csv"
        }
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
    except Exception as e:
        logger.error(f"Query CSV error: {e}")
        raise HTTPException(status_code=500, detail=f"Query CSV failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    status = {
        "status": "healthy",
        "agent_initialized": sql_agent is not None
    }
    
    if sql_agent:
        status["database_connected"] = sql_agent.test_connection()
    
    return status

@app.get("/schema")
async def get_schema():
    """Get database schema information"""
    if sql_agent is None:
        raise HTTPException(status_code=503, detail="SQL Agent not initialized")
    
    return {"schema": sql_agent.get_schema_info()}


# ==================== Chat Endpoints ====================

class ChatMessageRequest(BaseModel):
    session_id: str
    message: str

class ChatSessionRequest(BaseModel):
    metadata: dict = {}

@app.post("/chat/session")
async def create_chat_session(request: ChatSessionRequest):
    """Create a new chat session"""
    if chatbot_service is None:
        raise HTTPException(status_code=503, detail="Chatbot service not initialized")
    
    try:
        session_id = chatbot_service.create_session(request.metadata)
        return {"session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to create chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """Get chat history for a session"""
    if chatbot_service is None:
        raise HTTPException(status_code=503, detail="Chatbot service not initialized")
    
    try:
        messages = chatbot_service.get_session_history(session_id)
        return {
            "session_id": session_id,
            "messages": [msg.model_dump() for msg in messages]
        }
    except Exception as e:
        logger.error(f"Failed to get chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/message")
async def send_chat_message(request: ChatMessageRequest):
    """Send a message and get a response"""
    if chatbot_service is None:
        raise HTTPException(status_code=503, detail="Chatbot service not initialized")
    
    try:
        response = chatbot_service.process_message(
            session_id=request.session_id,
            user_message=request.message
        )
        return response.model_dump()
    except Exception as e:
        logger.error(f"Failed to process message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Quiz Endpoints ====================

@app.post("/quiz/game")
async def create_quiz_game(game_request: QuizGameCreate):
    """Create a new quiz game"""
    if quiz_service is None:
        raise HTTPException(status_code=503, detail="Quiz service not initialized")
    
    try:
        game_id = quiz_service.create_game(game_request)
        return {"game_id": game_id, "message": "Game created successfully"}
    except Exception as e:
        logger.error(f"Failed to create game: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/quiz/game/{game_id}/start")
async def start_quiz_game(game_id: str):
    """Start a quiz game"""
    if quiz_service is None:
        raise HTTPException(status_code=503, detail="Quiz service not initialized")
    
    try:
        game_state = quiz_service.start_game(game_id)
        return game_state
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start game: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quiz/game/{game_id}")
async def get_quiz_game_state(game_id: str):
    """Get current game state"""
    if quiz_service is None:
        raise HTTPException(status_code=503, detail="Quiz service not initialized")
    
    try:
        game_state = quiz_service.get_game_state(game_id)
        return game_state
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get game state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quiz/game/{game_id}/question")
async def get_current_question(game_id: str):
    """Get the current question for a game"""
    if quiz_service is None:
        raise HTTPException(status_code=503, detail="Quiz service not initialized")
    
    try:
        question = quiz_service.get_current_question(game_id)
        return question
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get question: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class QuizAnswerRequest(BaseModel):
    round_id: str
    answer: QuizAnswer

@app.post("/quiz/game/{game_id}/answer")
async def submit_quiz_answer(game_id: str, answer_request: QuizAnswerRequest):
    """Submit an answer for a round"""
    if quiz_service is None:
        raise HTTPException(status_code=503, detail="Quiz service not initialized")
    
    try:
        result = quiz_service.submit_answer(
            game_id=game_id,
            round_id=answer_request.round_id,
            answer=answer_request.answer
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to submit answer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quiz/game/{game_id}/leaderboard")
async def get_quiz_leaderboard(game_id: str):
    """Get leaderboard for a game"""
    if quiz_service is None:
        raise HTTPException(status_code=503, detail="Quiz service not initialized")
    
    try:
        leaderboard = quiz_service.get_leaderboard(game_id)
        return {"game_id": game_id, "leaderboard": leaderboard}
    except Exception as e:
        logger.error(f"Failed to get leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/quiz/game/{game_id}/next")
async def advance_quiz_round(game_id: str):
    """Advance to next round"""
    if quiz_service is None:
        raise HTTPException(status_code=503, detail="Quiz service not initialized")
    
    try:
        result = quiz_service.advance_round(game_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to advance round: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)