import { create } from 'zustand';
import type {
  QuizGameState,
  QuizQuestion,
  QuizLeaderboardEntry,
} from '../types/api';

interface QuizStore {
  gameId: string | null;
  gameState: QuizGameState | null;
  currentQuestion: QuizQuestion | null;
  leaderboard: QuizLeaderboardEntry[];
  isLoading: boolean;
  error: string | null;
  setGameId: (gameId: string | null) => void;
  setGameState: (gameState: QuizGameState | null) => void;
  setCurrentQuestion: (question: QuizQuestion | null) => void;
  setLeaderboard: (leaderboard: QuizLeaderboardEntry[]) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useQuizStore = create<QuizStore>((set) => ({
  gameId: null,
  gameState: null,
  currentQuestion: null,
  leaderboard: [],
  isLoading: false,
  error: null,
  setGameId: (gameId) => set({ gameId }),
  setGameState: (gameState) => set({ gameState }),
  setCurrentQuestion: (currentQuestion) => set({ currentQuestion }),
  setLeaderboard: (leaderboard) => set({ leaderboard }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  reset: () =>
    set({
      gameId: null,
      gameState: null,
      currentQuestion: null,
      leaderboard: [],
      isLoading: false,
      error: null,
    }),
}));



