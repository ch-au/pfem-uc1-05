import { create } from 'zustand';
import type {
  QuizGameState,
  QuizQuestion,
  QuizLeaderboardEntry,
  QuizGenerationProgressResponse,
} from '../types/api';

interface QuizStore {
  gameId: string | null;
  gameState: QuizGameState | null;
  currentQuestion: QuizQuestion | null;
  leaderboard: QuizLeaderboardEntry[];
  isLoading: boolean;
  error: string | null;
  statusMessage: string | null;
  // Progress of background generation job for new quizzes
  generationProgress: QuizGenerationProgressResponse['progress'] | null;
  setGameId: (gameId: string | null) => void;
  setGameState: (gameState: QuizGameState | null) => void;
  setCurrentQuestion: (question: QuizQuestion | null) => void;
  setLeaderboard: (leaderboard: QuizLeaderboardEntry[]) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  setStatusMessage: (message: string | null) => void;
  setGenerationProgress: (progress: QuizGenerationProgressResponse['progress'] | null) => void;
  reset: () => void;
}

export const useQuizStore = create<QuizStore>((set) => ({
  gameId: null,
  gameState: null,
  currentQuestion: null,
  leaderboard: [],
  isLoading: false,
  error: null,
  statusMessage: null,
  generationProgress: null,
  setGameId: (gameId) => set({ gameId }),
  setGameState: (gameState) => set({ gameState }),
  setCurrentQuestion: (currentQuestion) => set({ currentQuestion }),
  setLeaderboard: (leaderboard) => set({ leaderboard }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  setStatusMessage: (statusMessage) => set({ statusMessage }),
  setGenerationProgress: (generationProgress) => set({ generationProgress }),
  reset: () =>
    set({
      gameId: null,
      gameState: null,
      currentQuestion: null,
      leaderboard: [],
      isLoading: false,
      error: null,
      statusMessage: null,
      generationProgress: null,
    }),
}));

