import { vi } from 'vitest';

/**
 * Mock responses for OpenRouter API
 */
export const mockOpenRouterResponses = {
  sqlGeneration: {
    sql: 'SELECT p.name, COUNT(*) as goals FROM public.goals g JOIN public.players p ON g.player_id = p.player_id WHERE g.team_id = 1 GROUP BY p.player_id, p.name ORDER BY goals DESC LIMIT 1;',
    confidence: 0.95,
    reasoning: 'Using JOIN between players and goals tables to calculate top scorer statistics',
    needsClarification: null,
  },
  answerFormatting: {
    answer: 'Der Rekordtorschütze von Mainz 05 ist Bopp mit 100 Toren in seiner Karriere.',
    highlights: [
      '100 Tore in allen Wettbewerben',
      'Aktiv von 1920 bis 1935',
      'Vereinslegende und bis heute unerreicht',
    ],
    suggestedVisualization: 'stat' as const,
    followUpQuestions: [
      'Wer ist der beste Torschütze in der Bundesliga?',
      'Wie viele Tore hat der zweitbeste Torschütze?',
    ],
  },
  questionGeneration: {
    questions: [
      {
        questionText: 'Wer ist der Rekordtorschütze von FSV Mainz 05?',
        category: 'top_scorers',
        difficulty: 'easy' as const,
        sqlQueryNeeded:
          'SELECT p.name FROM public.players p JOIN public.goals g ON p.player_id = g.player_id WHERE g.team_id = 1 GROUP BY p.player_id, p.name ORDER BY COUNT(*) DESC LIMIT 1;',
        expectedAnswerType: 'string' as const,
        hint: undefined,
      },
      {
        questionText: 'Wie viele Bundesliga-Tore erzielte Mainz 05 in der Saison 2015-16?',
        category: 'seasons',
        difficulty: 'medium' as const,
        sqlQueryNeeded:
          "SELECT COUNT(*) FROM public.goals g JOIN public.matches m ON g.match_id = m.match_id JOIN public.season_competitions sc ON m.season_competition_id = sc.season_competition_id JOIN public.seasons s ON sc.season_id = s.season_id WHERE s.label = '2015-16' AND g.team_id = 1;",
        expectedAnswerType: 'number' as const,
        hint: undefined,
      },
    ],
  },
  answerGeneration: {
    correctAnswer: 'Bopp',
    incorrectAnswers: ['Szalai', 'Noveski', 'Quaison'],
    explanation:
      'Bopp ist mit 100 Toren der erfolgreichste Torschütze in der Geschichte von Mainz 05.',
    evidenceScore: 0.98,
  },
};

/**
 * Create a mock OpenRouter service
 */
export const createMockOpenRouterService = () => {
  return {
    generateJSON: vi.fn().mockImplementation(async (prompt: string, _options?: any) => {
      // Determine which response to return based on prompt content
      if (prompt.includes('SQL')) {
        return {
          data: mockOpenRouterResponses.sqlGeneration,
          usage: { promptTokens: 100, completionTokens: 50, totalTokens: 150 },
        };
      } else if (prompt.includes('Formuliere')) {
        return {
          data: mockOpenRouterResponses.answerFormatting,
          usage: { promptTokens: 200, completionTokens: 100, totalTokens: 300 },
        };
      } else if (prompt.includes('Quiz-Fragen')) {
        return {
          data: mockOpenRouterResponses.questionGeneration,
          usage: { promptTokens: 300, completionTokens: 200, totalTokens: 500 },
        };
      } else if (prompt.includes('Multiple-Choice')) {
        return {
          data: mockOpenRouterResponses.answerGeneration,
          usage: { promptTokens: 150, completionTokens: 80, totalTokens: 230 },
        };
      }

      // Default fallback
      return {
        data: { status: 'ok' },
        usage: { promptTokens: 10, completionTokens: 5, totalTokens: 15 },
      };
    }),
    generateWithStreaming: vi.fn(),
    healthCheck: vi.fn().mockResolvedValue(true),
  };
};
