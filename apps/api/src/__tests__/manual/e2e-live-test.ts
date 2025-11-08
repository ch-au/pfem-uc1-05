#!/usr/bin/env tsx

/**
 * Manual E2E Test with Real Services
 *
 * Tests the complete pipeline with:
 * - Real Gemini API calls
 * - Real PostgreSQL database
 * - Real Langfuse tracing
 *
 * Run: tsx src/__tests__/manual/e2e-live-test.ts
 */

import { ChatService } from '../../services/chat/chat.service.js';
import { QuizService } from '../../services/quiz/quiz.service.js';
import { PostgresService } from '../../services/database/postgres.service.js';
import { langfuseService } from '../../services/ai/langfuse.service.js';
import { geminiService } from '../../services/ai/gemini.service.js';

// Colors for console output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  green: '\x1b[32m',
  blue: '\x1b[34m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
};

function log(color: string, label: string, message: string) {
  console.log(`${color}${colors.bright}[${label}]${colors.reset} ${message}`);
}

function section(title: string) {
  console.log(`\n${'='.repeat(80)}`);
  console.log(`${colors.bright}${colors.cyan}${title}${colors.reset}`);
  console.log(`${'='.repeat(80)}\n`);
}

async function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function testChatFlow() {
  section('🤖 CHAT FLOW TEST');

  const chatService = new ChatService();

  try {
    // Step 1: Create session
    log(colors.blue, 'STEP 1', 'Creating chat session...');
    const session = await chatService.createSession();
    log(colors.green, 'SUCCESS', `Session created: ${session.session_id}`);

    // Step 2: Send message
    log(colors.blue, 'STEP 2', 'Sending message: "Wer ist der Rekordtorschütze von Mainz 05?"');
    const startTime = Date.now();

    const response = await chatService.processMessage({
      session_id: session.session_id,
      content: 'Wer ist der Rekordtorschütze von Mainz 05?',
    });

    const duration = Date.now() - startTime;

    log(colors.green, 'SUCCESS', `Response received in ${duration}ms`);

    // Step 3: Display results
    section('📊 CHAT RESULTS');

    console.log(`${colors.bright}Message ID:${colors.reset} ${response.message_id}`);
    console.log(`${colors.bright}Role:${colors.reset} ${response.role}`);
    console.log(`${colors.bright}Content:${colors.reset}\n${response.content}\n`);

    if (response.metadata) {
      console.log(`${colors.bright}Metadata:${colors.reset}`);
      console.log(`  SQL Query: ${response.metadata.sql_query?.substring(0, 100)}...`);
      console.log(`  Execution Time: ${response.metadata.sql_execution_time_ms}ms`);
      console.log(`  Result Count: ${response.metadata.sql_result_count} rows`);
      console.log(`  Confidence: ${response.metadata.confidence_score}`);
      console.log(`  Visualization: ${response.metadata.visualization_type || 'none'}`);

      if (response.metadata.highlights) {
        console.log(`\n  ${colors.yellow}Highlights:${colors.reset}`);
        response.metadata.highlights.forEach((h: string) => {
          console.log(`    • ${h}`);
        });
      }

      if (response.metadata.follow_up_questions) {
        console.log(`\n  ${colors.cyan}Follow-up Questions:${colors.reset}`);
        response.metadata.follow_up_questions.forEach((q: string) => {
          console.log(`    ? ${q}`);
        });
      }
    }

    if (response.langfuse_trace_id) {
      console.log(`\n${colors.magenta}${colors.bright}Langfuse Trace:${colors.reset}`);
      console.log(`  Trace ID: ${response.langfuse_trace_id}`);
      console.log(`  View at: https://cloud.langfuse.com/traces/${response.langfuse_trace_id}`);
    }

    // Step 4: Verify in database
    log(colors.blue, 'STEP 4', 'Verifying message in database...');
    const history = await chatService.getHistory(session.session_id);
    log(colors.green, 'SUCCESS', `Found ${history.length} messages in history`);

    // Step 5: Cleanup
    log(colors.blue, 'STEP 5', 'Cleaning up session...');
    await chatService.deleteSession(session.session_id);
    log(colors.green, 'SUCCESS', 'Session deleted');

    return {
      success: true,
      traceId: response.langfuse_trace_id,
      duration,
      messageCount: history.length,
    };
  } catch (error) {
    log(colors.red, 'ERROR', `Chat flow failed: ${error}`);
    console.error(error);
    return { success: false, error };
  }
}

async function testQuizFlow() {
  section('🎮 QUIZ FLOW TEST');

  const quizService = new QuizService();
  const postgresService = new PostgresService();

  try {
    // Step 1: Create game
    log(colors.blue, 'STEP 1', 'Creating quiz game (2 rounds, easy difficulty)...');
    const startTime = Date.now();

    const game = await quizService.createGame({
      difficulty: 'easy',
      num_rounds: 2,
      game_mode: 'classic',
      player_names: ['TestPlayer1', 'TestPlayer2'],
    });

    const createDuration = Date.now() - startTime;
    log(colors.green, 'SUCCESS', `Game created in ${createDuration}ms: ${game.game_id}`);

    // Step 2: Verify questions were generated
    log(colors.blue, 'STEP 2', 'Verifying questions in database...');
    const questions = await postgresService.queryMany<{
      question_text: string;
      difficulty: string;
      sql_query: string;
      langfuse_trace_id: string | null;
    }>(
      `SELECT q.question_text, q.difficulty, q.sql_query, q.langfuse_trace_id
       FROM public.quiz_questions q
       JOIN public.quiz_rounds r ON q.question_id = r.question_id
       WHERE r.game_id = $1
       ORDER BY r.round_number`,
      [game.game_id]
    );

    log(colors.green, 'SUCCESS', `Found ${questions.length} questions`);

    // Step 3: Display questions
    section('📊 QUIZ QUESTIONS');

    questions.forEach((q, idx) => {
      console.log(`${colors.bright}Question ${idx + 1}:${colors.reset}`);
      console.log(`  Text: ${q.question_text}`);
      console.log(`  Difficulty: ${q.difficulty}`);
      console.log(`  SQL: ${q.sql_query.substring(0, 80)}...`);
      if (q.langfuse_trace_id) {
        console.log(`  ${colors.magenta}Trace: ${q.langfuse_trace_id}${colors.reset}`);
      }
      console.log('');
    });

    // Step 4: Start game
    log(colors.blue, 'STEP 4', 'Starting game...');
    await quizService.startGame(game.game_id);
    log(colors.green, 'SUCCESS', 'Game started');

    // Step 5: Get first question
    log(colors.blue, 'STEP 5', 'Getting first question...');
    const question = await quizService.getCurrentQuestion(game.game_id);

    console.log(`\n${colors.bright}Current Question:${colors.reset}`);
    console.log(`  ${question.question_text}`);
    console.log(`  Alternatives: ${question.alternatives.join(', ')}`);

    // Step 6: Submit answers for both players
    log(colors.blue, 'STEP 6', 'Submitting answers...');

    // Get correct answer from DB
    const questionData = await postgresService.queryOne<{ correct_answer: string }>(
      'SELECT correct_answer FROM public.quiz_questions WHERE question_id = $1',
      [question.question_id]
    );

    if (!questionData) {
      throw new Error('Question not found in database');
    }

    // Player 1: Correct answer (fast)
    const answer1 = await quizService.submitAnswer(game.game_id, 1, {
      player_name: 'TestPlayer1',
      answer: questionData.correct_answer,
      time_taken: 3.5,
    });

    log(
      answer1.is_correct ? colors.green : colors.red,
      'PLAYER1',
      `${answer1.is_correct ? 'Correct' : 'Wrong'}! Points: ${answer1.points_earned}`
    );

    // Player 2: Wrong answer
    const answer2 = await quizService.submitAnswer(game.game_id, 1, {
      player_name: 'TestPlayer2',
      answer: 'Wrong Answer',
      time_taken: 8.0,
    });

    log(
      answer2.is_correct ? colors.green : colors.red,
      'PLAYER2',
      `${answer2.is_correct ? 'Correct' : 'Wrong'}! Points: ${answer2.points_earned}`
    );

    console.log(`\n${colors.bright}Correct Answer:${colors.reset} ${answer1.correct_answer}`);
    if (answer1.explanation) {
      console.log(`${colors.bright}Explanation:${colors.reset} ${answer1.explanation}`);
    }

    // Step 7: Get leaderboard
    log(colors.blue, 'STEP 7', 'Getting leaderboard...');
    const leaderboard = await quizService.getLeaderboard(game.game_id);

    section('🏆 LEADERBOARD');
    console.log(`${colors.bright}Game ID:${colors.reset} ${leaderboard.game_id}\n`);

    leaderboard.leaderboard.forEach((entry, idx) => {
      const medal = idx === 0 ? '🥇' : idx === 1 ? '🥈' : '🥉';
      console.log(`${medal} ${colors.bright}${entry.player_name}${colors.reset}`);
      console.log(`   Score: ${entry.score} points`);
      console.log(`   Correct: ${entry.correct_answers}/${entry.total_questions}`);
      console.log(`   Avg Time: ${entry.average_time.toFixed(1)}s\n`);
    });

    // Step 8: Cleanup
    log(colors.blue, 'STEP 8', 'Cleaning up game...');
    await postgresService.query('DELETE FROM public.quiz_games WHERE game_id = $1', [game.game_id]);
    log(colors.green, 'SUCCESS', 'Game deleted');

    return {
      success: true,
      gameId: game.game_id,
      questionCount: questions.length,
      traceIds: questions.map((q) => q.langfuse_trace_id).filter(Boolean),
      createDuration,
      leaderboard: leaderboard.leaderboard,
    };
  } catch (error) {
    log(colors.red, 'ERROR', `Quiz flow failed: ${error}`);
    console.error(error);
    return { success: false, error };
  }
}

async function testSystemHealth() {
  section('🏥 SYSTEM HEALTH CHECK');

  const postgresService = new PostgresService();

  try {
    // Database
    log(colors.blue, 'CHECK', 'PostgreSQL connection...');
    const dbHealth = await postgresService.healthCheck();
    log(dbHealth ? colors.green : colors.red, 'DB', dbHealth ? 'Connected' : 'Failed');

    // Gemini
    log(colors.blue, 'CHECK', 'Gemini API...');
    const geminiHealth = await geminiService.healthCheck();
    log(geminiHealth ? colors.green : colors.red, 'GEMINI', geminiHealth ? 'OK' : 'Failed');

    // Langfuse
    log(colors.blue, 'CHECK', 'Langfuse...');
    const langfuseActive = langfuseService.isActive();
    log(langfuseActive ? colors.green : colors.yellow, 'LANGFUSE', langfuseActive ? 'Enabled' : 'Disabled (using local prompts)');

    // Database schema
    log(colors.blue, 'CHECK', 'Quiz categories...');
    const categories = await postgresService.queryMany(
      'SELECT name FROM public.quiz_categories ORDER BY name'
    );
    log(colors.green, 'SCHEMA', `Found ${categories.length} quiz categories`);

    await postgresService.close();

    return {
      database: dbHealth,
      gemini: geminiHealth,
      langfuse: langfuseActive,
      categoryCount: categories.length,
    };
  } catch (error) {
    log(colors.red, 'ERROR', `Health check failed: ${error}`);
    return { success: false, error };
  }
}

async function main() {
  console.log(`\n${colors.bright}${colors.cyan}${'*'.repeat(80)}${colors.reset}`);
  console.log(`${colors.bright}${colors.cyan}         FSV MAINZ 05 - MANUAL E2E TEST WITH LIVE SERVICES${colors.reset}`);
  console.log(`${colors.bright}${colors.cyan}${'*'.repeat(80)}${colors.reset}\n`);

  console.log(`${colors.yellow}This test will:`);
  console.log(`  • Make real API calls to Gemini (costs money!)`);
  console.log(`  • Write to your PostgreSQL database`);
  console.log(`  • Send traces to Langfuse`);
  console.log(`  • Take ~30-60 seconds to complete${colors.reset}\n`);

  // Health check first
  const healthResult = await testSystemHealth();

  if (!healthResult.database || !healthResult.gemini) {
    log(colors.red, 'ABORT', 'System health check failed. Cannot proceed.');
    process.exit(1);
  }

  await sleep(1000);

  // Run chat flow
  const chatResult = await testChatFlow();
  await sleep(2000);

  // Run quiz flow
  const quizResult = await testQuizFlow();
  await sleep(1000);

  // Shutdown Langfuse
  log(colors.blue, 'SHUTDOWN', 'Flushing Langfuse traces...');
  await langfuseService.shutdown();
  log(colors.green, 'SUCCESS', 'Langfuse shutdown complete');

  // Final summary
  section('📝 TEST SUMMARY');

  console.log(`${colors.bright}System Health:${colors.reset}`);
  console.log(`  Database: ${healthResult.database ? '✅' : '❌'}`);
  console.log(`  Gemini API: ${healthResult.gemini ? '✅' : '❌'}`);
  console.log(`  Langfuse: ${healthResult.langfuse ? '✅' : '⚠️  (using local prompts)'}`);
  console.log(`  Quiz Categories: ${healthResult.categoryCount}\n`);

  console.log(`${colors.bright}Chat Flow:${colors.reset}`);
  if (chatResult.success) {
    console.log(`  Status: ${colors.green}✅ Passed${colors.reset}`);
    console.log(`  Duration: ${chatResult.duration}ms`);
    console.log(`  Messages: ${chatResult.messageCount}`);
    if (chatResult.traceId) {
      console.log(`  ${colors.magenta}Trace: https://cloud.langfuse.com/traces/${chatResult.traceId}${colors.reset}`);
    }
  } else {
    console.log(`  Status: ${colors.red}❌ Failed${colors.reset}`);
  }

  console.log(`\n${colors.bright}Quiz Flow:${colors.reset}`);
  if (quizResult.success) {
    console.log(`  Status: ${colors.green}✅ Passed${colors.reset}`);
    console.log(`  Game Creation: ${quizResult.createDuration}ms`);
    console.log(`  Questions: ${quizResult.questionCount}`);
    console.log(`  Players: ${quizResult.leaderboard?.length || 0}`);
    if (quizResult.traceIds && quizResult.traceIds.length > 0) {
      console.log(`  ${colors.magenta}Traces:${colors.reset}`);
      quizResult.traceIds.forEach((id, idx) => {
        console.log(`    ${idx + 1}. https://cloud.langfuse.com/traces/${id}`);
      });
    }
  } else {
    console.log(`  Status: ${colors.red}❌ Failed${colors.reset}`);
  }

  console.log(`\n${colors.bright}${colors.green}Overall: ${chatResult.success && quizResult.success ? '✅ ALL TESTS PASSED' : '❌ SOME TESTS FAILED'}${colors.reset}\n`);

  if (healthResult.langfuse) {
    console.log(`${colors.cyan}${colors.bright}View all traces in Langfuse Dashboard:${colors.reset}`);
    console.log(`${colors.cyan}https://cloud.langfuse.com${colors.reset}\n`);
  }

  process.exit(chatResult.success && quizResult.success ? 0 : 1);
}

// Run
main().catch((error) => {
  console.error(`${colors.red}${colors.bright}Fatal error:${colors.reset}`, error);
  process.exit(1);
});
