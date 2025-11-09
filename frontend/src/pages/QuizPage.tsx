import React, { useState } from 'react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Alert } from '../components/ui/Alert';
import { QuizSetup } from '../components/quiz/QuizSetup';
import { QuizQuestion } from '../components/quiz/QuizQuestion';
import { QuizOption } from '../components/quiz/QuizOption';
import { Leaderboard } from '../components/quiz/Leaderboard';
import { QuizHistory } from '../components/quiz/QuizHistory';
import { useQuizGame } from '../hooks/useQuizGame';
import { quizService } from '../services/quizService';
import { Trophy } from 'lucide-react';
import type { QuizGameState } from '../types/api';
import styles from './QuizPage.module.css';

type QuizScreen = 'start' | 'setup' | 'game';

export const QuizPage: React.FC = () => {
  const [screen, setScreen] = useState<QuizScreen>('start');
  const [gameHistory, setGameHistory] = useState<QuizGameState[]>([]);
  const {
    gameState,
    currentQuestion,
    leaderboard,
    isLoading,
    error,
    currentPlayer,
    selectedAnswer,
    answerResult,
    createGame,
    submitAnswer,
    nextRound,
    loadLeaderboard,
    reset,
  } = useQuizGame();

  const handleSetupSubmit = async (data: {
    topic?: string;
    difficulty: 'easy' | 'medium' | 'hard';
    numRounds: number;
    playerNames: string[];
  }) => {
    try {
      await createGame({
        topic: data.topic,
        difficulty: data.difficulty,
        num_rounds: data.numRounds,
        player_names: data.playerNames,
      });
      setScreen('game');
    } catch (error) {
      // Error is already set in the hook, just log it
      console.error('Failed to create game:', error);
    }
  };

  const handleAnswerSelect = async (answer: string) => {
    if (selectedAnswer || isLoading) return;

    try {
      await submitAnswer(answer);
    } catch (error) {
      console.error('Failed to submit answer:', error);
    }
  };

  const handleNextRound = async () => {
    try {
      const result = await nextRound();
      if (result?.status === 'completed') {
        await loadLeaderboard();
      }
    } catch (error) {
      console.error('Failed to advance round:', error);
    }
  };

  // Load leaderboard and game history on mount
  React.useEffect(() => {
    loadLeaderboard();
    loadGameHistory();
  }, []);

  const loadGameHistory = async () => {
    try {
      const result = await quizService.getGameHistory({ limit: 10 });
      setGameHistory(result.games);
    } catch (error) {
      console.error('Failed to load game history:', error);
    }
  };

  const handleSelectGame = async (gameId: string) => {
    try {
      const game = await quizService.getGameState(gameId);
      if (game.status === 'completed') {
        // For completed games, show leaderboard
        const leaderboardData = await quizService.getLeaderboard(gameId);
        // You could navigate to a game detail view here
        console.log('Show completed game:', gameId, leaderboardData);
      } else {
        // For in-progress games, potentially resume them
        // This would require additional state management
        console.log('Resume game:', gameId);
      }
    } catch (error) {
      console.error('Failed to load game:', error);
    }
  };

  const handleErrorClose = () => {
    reset();
  };

  const handleRetry = () => {
    reset();
    setScreen('start');
  };

  if (screen === 'setup') {
    return (
      <div className={styles.quizPage}>
        {error && (
          <Alert
            variant="error"
            title="Quiz Erstellung fehlgeschlagen"
            message={error}
            onClose={handleErrorClose}
          />
        )}
        <QuizSetup onSubmit={handleSetupSubmit} isLoading={isLoading} />
      </div>
    );
  }

  if (screen === 'game' && currentQuestion && gameState) {
    const allOptions = currentQuestion.alternatives
      ? [currentQuestion.correct_answer, ...currentQuestion.alternatives]
      : [currentQuestion.correct_answer];
    const shuffledOptions = [...allOptions].sort(() => Math.random() - 0.5);

    const isCorrect = (option: string): boolean =>
      answerResult ? option === answerResult.correctAnswer : false;
    const isSelected = (option: string): boolean => selectedAnswer === option;
    const isIncorrect = (option: string): boolean =>
      answerResult ? selectedAnswer === option && !answerResult.correct : false;

    const canProceed = answerResult !== null && currentPlayer === gameState.players[gameState.players.length - 1];

    return (
      <div className={styles.quizPage}>
        {error && (
          <Alert
            variant="error"
            title="Fehler"
            message={error}
            onClose={handleErrorClose}
          />
        )}
        <Card variant="elevated" padding="md">
          <QuizQuestion
            question={currentQuestion.question_text}
            roundNumber={currentQuestion.round_number || gameState.current_round}
            totalRounds={gameState.num_rounds}
            currentPlayer={currentPlayer}
          />

          <div className={styles.options}>
            {shuffledOptions.map((option, index) => (
              <QuizOption
                key={option}
                option={option}
                label={option}
                index={index}
                selected={isSelected(option)}
                correct={isCorrect(option)}
                incorrect={isIncorrect(option)}
                disabled={answerResult !== null}
                onClick={() => handleAnswerSelect(option)}
              />
            ))}
          </div>

          {answerResult && (
            <div className={`${styles.result} ${styles[answerResult.correct ? 'result--correct' : 'result--incorrect']}`}>
              <div className={styles.resultText}>
                {answerResult.correct ? (
                  <>✓ Richtig! (+{answerResult.pointsEarned} Punkte)</>
                ) : (
                  <>✗ Falsch</>
                )}
              </div>
              <div className={styles.explanation}>
                Richtige Antwort: {answerResult.correctAnswer}
              </div>
            </div>
          )}

          {canProceed && (
            <Button
              variant="primary"
              size="lg"
              onClick={handleNextRound}
              className={styles.nextButton}
            >
              {gameState.current_round >= gameState.num_rounds ? 'Fertig' : 'Nächste Runde'}
            </Button>
          )}

          {leaderboard.length > 0 && (
            <Leaderboard entries={leaderboard} />
          )}
        </Card>
      </div>
    );
  }

  // Start screen
  return (
    <div className={styles.quizPage}>
      <Card variant="elevated" padding="lg">
        <div className={styles.startContent}>
          <h1 className={styles.startTitle}>FSV Mainz 05 Quiz</h1>
          <p className={styles.startDescription}>
            Teste dein Wissen über 120 Jahre Vereinsgeschichte - von 1905 bis heute
          </p>
          
          <Button
            variant="primary"
            size="lg"
            onClick={() => setScreen('setup')}
            className={styles.startButton}
          >
            Neues Quiz starten
          </Button>
        </div>
      </Card>

      {gameHistory.length > 0 && (
        <Card variant="elevated" padding="md">
          <QuizHistory games={gameHistory} onSelectGame={handleSelectGame} />
        </Card>
      )}

      {leaderboard.length > 0 && (
        <Card variant="elevated" padding="md">
          <h2 className={styles.sectionTitle}>
            <Trophy size={24} />
            Leaderboard
          </h2>
          <Leaderboard entries={leaderboard} />
        </Card>
      )}
    </div>
  );
};



