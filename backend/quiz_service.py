"""
Quiz game service for managing game state, rounds, and scoring
"""
import uuid
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import psycopg2
from .quiz_generator import QuizGenerator
from .models import QuizGameCreate, QuizAnswer, QuizQuestion
from .config import Config


class QuizService:
    """Service for managing quiz games"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.quiz_generator = QuizGenerator(config)
        self.pg_dsn = self.config.build_psycopg2_dsn()
    
    def create_game(self, game_request: QuizGameCreate) -> str:
        """Create a new quiz game"""
        game_id = str(uuid.uuid4())
        
        with psycopg2.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Create game
                cur.execute("""
                    INSERT INTO public.quiz_games (
                        game_id, topic, difficulty, num_rounds,
                        status, current_round
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    game_id,
                    game_request.topic,
                    game_request.difficulty,
                    game_request.num_rounds,
                    "pending",
                    0
                ))
                
                # Generate questions for all rounds
                for round_num in range(1, game_request.num_rounds + 1):
                    question = self.quiz_generator.generate_question(
                        topic=game_request.topic,
                        difficulty=game_request.difficulty
                    )
                    
                    # Save question
                    question_id = self.quiz_generator.save_question(question)
                    
                    # Create round
                    cur.execute("""
                        INSERT INTO public.quiz_rounds (
                            game_id, question_id, round_number
                        )
                        VALUES (%s, %s, %s)
                    """, (game_id, question_id, round_num))
                
                conn.commit()
        
        return game_id
    
    def start_game(self, game_id: str) -> Dict[str, Any]:
        """Start a game (change status to in_progress)"""
        with psycopg2.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE public.quiz_games
                    SET status = 'in_progress', current_round = 1
                    WHERE game_id = %s AND status = 'pending'
                    RETURNING game_id, topic, difficulty, num_rounds, current_round, status
                """, (game_id,))
                
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Game {game_id} not found or cannot be started")
                
                conn.commit()
                
                return {
                    "game_id": row[0],
                    "topic": row[1],
                    "difficulty": row[2],
                    "num_rounds": row[3],
                    "current_round": row[4],
                    "status": row[5]
                }
    
    def get_game_state(self, game_id: str) -> Dict[str, Any]:
        """Get current game state"""
        with psycopg2.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT game_id, topic, difficulty, num_rounds,
                           current_round, status, created_at
                    FROM public.quiz_games
                    WHERE game_id = %s
                """, (game_id,))
                
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Game {game_id} not found")
                
                return {
                    "game_id": row[0],
                    "topic": row[1],
                    "difficulty": row[2],
                    "num_rounds": row[3],
                    "current_round": row[4],
                    "status": row[5],
                    "created_at": row[6].isoformat() if row[6] else None
                }
    
    def get_current_question(self, game_id: str) -> Dict[str, Any]:
        """Get the current question for the game"""
        with psycopg2.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Get current round
                cur.execute("""
                    SELECT current_round, status
                    FROM public.quiz_games
                    WHERE game_id = %s
                """, (game_id,))
                
                game_row = cur.fetchone()
                if not game_row:
                    raise ValueError(f"Game {game_id} not found")
                
                current_round_num = game_row[0]
                
                if game_row[1] == "completed":
                    raise ValueError("Game is already completed")
                
                # Get question for current round
                cur.execute("""
                    SELECT r.round_id, q.question_id, q.question_text,
                           q.correct_answer, q.alternatives, q.explanation,
                           q.difficulty, q.topic
                    FROM public.quiz_rounds r
                    JOIN public.quiz_questions q ON r.question_id = q.question_id
                    WHERE r.game_id = %s AND r.round_number = %s
                """, (game_id, current_round_num))
                
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"No question found for round {current_round_num}")
                
                alternatives = json.loads(row[4]) if isinstance(row[4], str) else row[4]
                
                # Shuffle alternatives (keep correct answer separate)
                import random
                all_options = [row[3]] + alternatives  # correct + alternatives
                random.shuffle(all_options)
                
                return {
                    "round_id": str(row[0]),
                    "question_id": str(row[1]),
                    "question_text": row[2],
                    "options": all_options,
                    "explanation": row[5],
                    "difficulty": row[6],
                    "topic": row[7],
                    "round_number": current_round_num
                }
    
    def submit_answer(
        self,
        game_id: str,
        round_id: str,
        answer: QuizAnswer
    ) -> Dict[str, Any]:
        """Submit an answer for a round"""
        with psycopg2.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Get correct answer
                cur.execute("""
                    SELECT q.correct_answer, g.difficulty
                    FROM public.quiz_rounds r
                    JOIN public.quiz_questions q ON r.question_id = q.question_id
                    JOIN public.quiz_games g ON r.game_id = g.game_id
                    WHERE r.round_id = %s
                """, (round_id,))
                
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Round {round_id} not found")
                
                correct_answer = row[0]
                difficulty = row[1]
                
                is_correct = answer.answer.strip().lower() == correct_answer.strip().lower()
                
                # Calculate points
                points = self._calculate_points(is_correct, answer.time_taken, difficulty)
                
                # Save answer
                cur.execute("""
                    INSERT INTO public.quiz_answers (
                        round_id, player_name, answer, is_correct,
                        time_taken, points_earned
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (round_id, player_name) DO UPDATE
                    SET answer = EXCLUDED.answer,
                        is_correct = EXCLUDED.is_correct,
                        time_taken = EXCLUDED.time_taken,
                        points_earned = EXCLUDED.points_earned,
                        submitted_at = CURRENT_TIMESTAMP
                """, (
                    round_id,
                    answer.player_name,
                    answer.answer,
                    is_correct,
                    answer.time_taken,
                    points
                ))
                
                conn.commit()
                
                return {
                    "correct": is_correct,
                    "correct_answer": correct_answer,
                    "points_earned": points
                }
    
    def _calculate_points(
        self,
        is_correct: bool,
        time_taken: float,
        difficulty: str
    ) -> int:
        """Calculate points based on correctness, time, and difficulty"""
        if not is_correct:
            return 0
        
        # Base points by difficulty
        base_points = {
            "easy": 50,
            "medium": 100,
            "hard": 150
        }.get(difficulty, 100)
        
        # Time bonus (max 50 points, decreases with time)
        # Fastest answer (0-5 seconds) gets full bonus
        # Slower answers get reduced bonus
        max_time = 30.0  # 30 seconds for full points
        time_bonus = max(0, int(50 * (1 - min(time_taken / max_time, 1.0))))
        
        return base_points + time_bonus
    
    def get_leaderboard(self, game_id: str) -> List[Dict[str, Any]]:
        """Get leaderboard for a game"""
        with psycopg2.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        a.player_name,
                        COUNT(*) FILTER (WHERE a.is_correct) as correct_answers,
                        SUM(a.points_earned) as total_points,
                        AVG(a.time_taken) FILTER (WHERE a.is_correct) as avg_time
                    FROM public.quiz_answers a
                    JOIN public.quiz_rounds r ON a.round_id = r.round_id
                    WHERE r.game_id = %s
                    GROUP BY a.player_name
                    ORDER BY total_points DESC, avg_time ASC
                """, (game_id,))
                
                leaderboard = []
                for row in cur.fetchall():
                    leaderboard.append({
                        "player_name": row[0],
                        "correct_answers": row[1],
                        "total_points": int(row[2]) if row[2] else 0,
                        "avg_time": float(row[3]) if row[3] else None
                    })
        
        return leaderboard
    
    def advance_round(self, game_id: str) -> Dict[str, Any]:
        """Advance to next round"""
        with psycopg2.connect(self.pg_dsn) as conn:
            with conn.cursor() as cur:
                # Get current round and total rounds
                cur.execute("""
                    SELECT current_round, num_rounds, status
                    FROM public.quiz_games
                    WHERE game_id = %s
                """, (game_id,))
                
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Game {game_id} not found")
                
                current_round = row[0]
                num_rounds = row[1]
                status = row[2]
                
                if status == "completed":
                    raise ValueError("Game is already completed")
                
                if current_round >= num_rounds:
                    # Game is complete
                    cur.execute("""
                        UPDATE public.quiz_games
                        SET status = 'completed',
                            completed_at = CURRENT_TIMESTAMP
                        WHERE game_id = %s
                    """, (game_id,))
                    
                    conn.commit()
                    
                    return {
                        "status": "completed",
                        "current_round": current_round,
                        "message": "Game completed!"
                    }
                else:
                    # Advance to next round
                    cur.execute("""
                        UPDATE public.quiz_games
                        SET current_round = current_round + 1
                        WHERE game_id = %s
                    """, (game_id,))
                    
                    conn.commit()
                    
                    return {
                        "status": "in_progress",
                        "current_round": current_round + 1,
                        "message": f"Round {current_round + 1} started"
                    }




