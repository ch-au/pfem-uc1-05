import { postgresService } from '../services/database/postgres.service.js';
import { quizService } from '../services/quiz/quiz.service.js';

type PendingGame = {
  game_id: string;
  num_rounds: number;
  difficulty: 'easy' | 'medium' | 'hard';
  category_name: string;
  topic: string | null;
  player_count: number;
};

const log = (...args: any[]) => console.log('[quiz-worker]', ...args);

async function fetchPendingGames(): Promise<PendingGame[]> {
  return await postgresService.queryMany<PendingGame>(
    `SELECT g.game_id, g.num_rounds, g.difficulty,
            COALESCE(c.name, 'statistics') as category_name,
            g.topic,
            COALESCE(jsonb_array_length(g.player_names::jsonb), 1) as player_count
     FROM public.quiz_games g
     LEFT JOIN public.quiz_categories c ON g.category_id = c.category_id
     WHERE EXISTS (
       SELECT 1 FROM quiz_generation_jobs j
       WHERE j.game_id = g.game_id
         AND j.status <> 'round_created'
     )
     AND g.status = 'pending'
     ORDER BY g.created_at ASC`
  );
}

async function processGame(game: PendingGame): Promise<void> {
  const category = game.topic ?? game.category_name;
  log(`Processing game ${game.game_id} (${game.num_rounds} rounds, ${game.difficulty}, ${category}, ${game.player_count} players)`);
  await quizService.generateQuestionsForGame(
    game.game_id,
    {
      category: category,
      difficulty: game.difficulty,
      numRounds: game.num_rounds,
      numberOfPlayers: game.player_count,
    },
    { ensureJobs: false }
  );
  log(`Completed game ${game.game_id}`);
}

async function run(): Promise<void> {
  try {
    const pending = await fetchPendingGames();
    if (pending.length === 0) {
      log('No pending quiz generation jobs found');
      await postgresService.close();
      return;
    }

    for (const game of pending) {
      try {
        await processGame(game);
      } catch (err) {
        log(`Failed processing game ${game.game_id}:`, err);
      }
    }
  } catch (err) {
    console.error('[quiz-worker] fatal error:', err);
  } finally {
    await postgresService.close();
  }
}

run();
