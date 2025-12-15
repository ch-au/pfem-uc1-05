import { useState } from 'react';
import { quizService } from '../services/quizService';
import { useQuizStore } from '../store/quizStore';
import type { QuizGameCreate, QuizAnswer } from '../types/api';

export interface PlayerRoundResult {
  playerName: string;
  answer: string;
  correct: boolean;
  pointsEarned: number;
}

export type GamePhase = 'question' | 'handoff' | 'results';

export const useQuizGame = () => {
  const {
    gameId,
    gameState,
    currentQuestion,
    leaderboard,
    isLoading,
    error,
    statusMessage,
    generationProgress,
    setGameId,
    setGameState,
    setCurrentQuestion,
    setLeaderboard,
    setLoading,
    setError,
    setStatusMessage,
    setGenerationProgress,
    reset,
  } = useQuizStore();

  const [currentPlayerIndex, setCurrentPlayerIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [answerResult, setAnswerResult] = useState<{
    correct: boolean;
    correctAnswer: string;
    pointsEarned: number;
    explanation?: string;
  } | null>(null);
  
  const [gamePhase, setGamePhase] = useState<GamePhase>('question');
  const [roundResults, setRoundResults] = useState<PlayerRoundResult[]>([]);
  const [correctAnswerForRound, setCorrectAnswerForRound] = useState<string>('');
  const [explanationForRound, setExplanationForRound] = useState<string | undefined>(undefined);

  const createGame = async (gameRequest: QuizGameCreate) => {
    try {
      setLoading(true);
      setError(null);
      setStatusMessage('Quiz wird erstellt...');
      setGenerationProgress(null);
      const newGameId = await quizService.createGame(gameRequest);
      setGameId(newGameId);
      
      // Wait for questions to finish generating
      await waitForQuestionGeneration(newGameId, (msg) => {
        setStatusMessage(msg);
      });
      
      // Start the game
      setStatusMessage('Starte Quiz...');
      const state = await quizService.startGame(newGameId);
      setGameState(state);
      
      // Load first question
      setStatusMessage('Frage laden...');
      const question = await quizService.getCurrentQuestion(newGameId);
      setCurrentQuestion(question);
      setStatusMessage(null);
      setGenerationProgress(null);
      
      setCurrentPlayerIndex(0);
      return newGameId;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create game');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const waitForQuestionGeneration = async (
    gameId: string,
    onProgress?: (message: string) => void,
    maxWaitTime = 180000
  ) => {
    const startTime = Date.now();
    const pollInterval = 1000; // Check every 1 second

    while (Date.now() - startTime < maxWaitTime) {
      try {
        const progress = await quizService.getGenerationProgress(gameId);
        setGenerationProgress(progress?.progress ?? null);
        
        if (progress.status === 'completed') {
          onProgress?.('Quiz wird fertiggestellt...');
          return; // Generation completed successfully
        }
        
        if (progress.status === 'failed') {
          const errorMsg = progress.progress?.error_message || 'Unknown error';
          throw new Error(`Question generation failed: ${errorMsg}`);
        }

        // Update progress message based on current round status (handle undefined gracefully)
        const activeRound = progress.progress?.current_round ?? 0;
        const currentStatus = progress.progress?.current_status ?? 'pending';
        const completed = progress.progress?.completed_rounds ?? 0;
        const total = progress.progress?.total_rounds ?? 1;
        if (currentStatus === 'sql_generated') {
          onProgress?.(`Fragen werden generiert (Runde ${activeRound}/${total})... (${completed} fertig)`);
        } else if (currentStatus === 'answer_verified') {
          onProgress?.(`Antworten werden geprüft (Runde ${activeRound}/${total})... (${completed} fertig)`);
        } else {
          onProgress?.(`Quiz wird vorbereitet... (${completed}/${total} Runden fertig)`);
        }
        
        // Still generating, wait before checking again
        await new Promise(resolve => setTimeout(resolve, pollInterval));
      } catch (err) {
        // If we get a 404, generation jobs might not be created yet, keep waiting
        if ((err as any)?.response?.status !== 404) {
          setGenerationProgress(null);
          throw err;
        }
        onProgress?.('Quiz wird vorbereitet...');
        await new Promise(resolve => setTimeout(resolve, pollInterval));
      }
    }

    throw new Error('Question generation took too long');
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

    const playerNames = gameState?.players || [];
    
    if (playerNames.length === 0) {
      setError('Dieses Quiz hat keine Spieler. Bitte starte ein neues Quiz.');
      return;
    }

    const startTime = Date.now();
    setSelectedAnswer(answer);
    setLoading(true);

    try {
      const currentPlayer = playerNames[currentPlayerIndex] || playerNames[0];

      const answerData: QuizAnswer = {
        player_name: currentPlayer,
        answer,
        time_taken: (Date.now() - startTime) / 1000,
      };

      const result = await quizService.submitAnswer(
        gameId,
        answerData
      );

      const playerResult: PlayerRoundResult = {
        playerName: currentPlayer,
        answer,
        correct: result.correct,
        pointsEarned: result.points_earned,
      };
      
      setRoundResults(prev => [...prev, playerResult]);
      setCorrectAnswerForRound(result.correct_answer);
      setExplanationForRound(result.explanation);

      const nextPlayerIndex = currentPlayerIndex + 1;
      const isMultiPlayer = playerNames.length > 1;
      
      if (nextPlayerIndex >= playerNames.length) {
        setCurrentPlayerIndex(0);
        try {
          const board = await quizService.getLeaderboard(gameId);
          setLeaderboard(board.leaderboard);
        } catch {
          // best-effort
        }
        setGamePhase('results');
      } else {
        setCurrentPlayerIndex(nextPlayerIndex);
        if (isMultiPlayer) {
          setGamePhase('handoff');
        }
      }

      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit answer');
      throw err;
    } finally {
      setLoading(false);
    }
  };
  
  const confirmHandoff = () => {
    setSelectedAnswer(null);
    setGamePhase('question');
  };

  const nextRound = async () => {
    if (!gameId) return;

    try {
      setLoading(true);
      setError(null);
      const result = await quizService.nextRound(gameId);

      setGameState(result);
      setRoundResults([]);
      setCorrectAnswerForRound('');
      setExplanationForRound(undefined);
      setSelectedAnswer(null);

      if (result.status === 'completed') {
        const leaderboardData = await quizService.getLeaderboard(gameId);
        setLeaderboard(leaderboardData.leaderboard);
      } else {
        await loadQuestion();
        const leaderboardData = await quizService.getLeaderboard(gameId);
        setLeaderboard(leaderboardData.leaderboard);
        setGamePhase('question');
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
      const data = await quizService.getLeaderboard(gameId);
      setLeaderboard(data.leaderboard);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load leaderboard');
    }
  };

  const loadGame = async (existingGameId: string) => {
    try {
      setLoading(true);
      setError(null);
      setStatusMessage('Lade Quiz...');
      setGenerationProgress(null);
      
      setGameId(existingGameId);
      
      let state = await quizService.getGameState(existingGameId);
      
      if (state.status === 'pending') {
        state = await quizService.startGame(existingGameId);
        setGameState(state);
        const question = await quizService.getCurrentQuestion(existingGameId);
        setCurrentQuestion(question);
        setLeaderboard([]);
      } else if (state.status === 'in_progress') {
        setGameState(state);
        const question = await quizService.getCurrentQuestion(existingGameId);
        setCurrentQuestion(question);
        try {
          const data = await quizService.getLeaderboard(existingGameId);
          setLeaderboard(data.leaderboard);
        } catch {
          setLeaderboard([]);
        }
      } else {
        setGameState(state);
        const data = await quizService.getLeaderboard(existingGameId);
        setLeaderboard(data.leaderboard);
        setCurrentQuestion(null);
      }
      
      setCurrentPlayerIndex(0);
      setSelectedAnswer(null);
      setAnswerResult(null);
      setStatusMessage(null);
      setGamePhase('question');
      setRoundResults([]);
      
      return state;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load game');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const passToNextPlayer = () => {
    setSelectedAnswer(null);
    setAnswerResult(null);
  };

  return {
    gameId,
    gameState,
    currentQuestion,
    leaderboard,
    isLoading,
    error,
    statusMessage,
    generationProgress,
    currentPlayerIndex,
    selectedAnswer,
    answerResult,
    currentPlayer: gameState?.players?.[currentPlayerIndex] || gameState?.players?.[0] || '',
    gamePhase,
    roundResults,
    correctAnswerForRound,
    explanationForRound,
    createGame,
    loadGame,
    loadQuestion,
    submitAnswer,
    nextRound,
    loadLeaderboard,
    reset,
    passToNextPlayer,
    confirmHandoff,
  };
};
