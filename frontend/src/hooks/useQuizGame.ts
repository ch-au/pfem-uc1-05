import { useState } from 'react';
import { quizService } from '../services/quizService';
import { useQuizStore } from '../store/quizStore';
import type { QuizGameCreate, QuizAnswer } from '../types/api';

export const useQuizGame = () => {
  const {
    gameId,
    gameState,
    currentQuestion,
    leaderboard,
    isLoading,
    error,
    setGameId,
    setGameState,
    setCurrentQuestion,
    setLeaderboard,
    setLoading,
    setError,
    reset,
  } = useQuizStore();

  const [currentPlayerIndex, setCurrentPlayerIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [answerResult, setAnswerResult] = useState<{
    correct: boolean;
    correctAnswer: string;
    pointsEarned: number;
  } | null>(null);

  const createGame = async (gameRequest: QuizGameCreate) => {
    try {
      setLoading(true);
      setError(null);
      const newGameId = await quizService.createGame(gameRequest);
      setGameId(newGameId);
      
      // Start the game
      const state = await quizService.startGame(newGameId);
      setGameState(state);
      
      // Load first question
      const question = await quizService.getCurrentQuestion(newGameId);
      setCurrentQuestion(question);
      
      setCurrentPlayerIndex(0);
      return newGameId;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create game');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const loadQuestion = async () => {
    if (!gameId) return;

    try {
      setLoading(true);
      setError(null);
      const question = await quizService.getCurrentQuestion(gameId);
      setCurrentQuestion(question);
      setSelectedAnswer(null);
      setAnswerResult(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load question');
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async (answer: string) => {
    if (!gameId || !currentQuestion || isLoading) return;

    const startTime = Date.now();
    setSelectedAnswer(answer);
    setLoading(true);

    try {
      const playerNames = gameState?.players || [];
      const currentPlayer = playerNames[currentPlayerIndex] || playerNames[0];

      const answerData: QuizAnswer = {
        player_name: currentPlayer,
        answer,
        time_taken: (Date.now() - startTime) / 1000,
      };

      const result = await quizService.submitAnswer(
        gameId,
        currentQuestion.round_id!,
        answerData
      );

      setAnswerResult({
        correct: result.correct,
        correctAnswer: result.correct_answer,
        pointsEarned: result.points_earned,
      });

      // Move to next player or show next round button
      const nextPlayerIndex = currentPlayerIndex + 1;
      if (nextPlayerIndex >= playerNames.length) {
        setCurrentPlayerIndex(0);
      } else {
        setCurrentPlayerIndex(nextPlayerIndex);
      }

      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit answer');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const nextRound = async () => {
    if (!gameId) return;

    try {
      setLoading(true);
      setError(null);
      const result = await quizService.nextRound(gameId);

      if (result.status === 'completed') {
        // Load leaderboard
        const leaderboardData = await quizService.getLeaderboard(gameId);
        setLeaderboard(leaderboardData.leaderboard);
      } else {
        // Load next question
        await loadQuestion();
      }

      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to advance round');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const loadLeaderboard = async () => {
    if (!gameId) return;

    try {
      setLoading(true);
      setError(null);
      const data = await quizService.getLeaderboard(gameId);
      setLeaderboard(data.leaderboard);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load leaderboard');
    } finally {
      setLoading(false);
    }
  };

  return {
    gameId,
    gameState,
    currentQuestion,
    leaderboard,
    isLoading,
    error,
    currentPlayerIndex,
    selectedAnswer,
    answerResult,
    currentPlayer: gameState?.players[currentPlayerIndex] || gameState?.players[0],
    createGame,
    loadQuestion,
    submitAnswer,
    nextRound,
    loadLeaderboard,
    reset,
  };
};

