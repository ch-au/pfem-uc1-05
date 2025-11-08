import React, { useState } from 'react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { QuizCard } from '../components/quiz/QuizCard';
import { QuizSetup } from '../components/quiz/QuizSetup';
import { QuizQuestion } from '../components/quiz/QuizQuestion';
import { QuizOption } from '../components/quiz/QuizOption';
import { Leaderboard } from '../components/quiz/Leaderboard';
import { useQuizGame } from '../hooks/useQuizGame';
import { Trophy } from 'lucide-react';
import styles from './QuizPage.module.css';

type QuizScreen = 'start' | 'setup' | 'game';

export const QuizPage: React.FC = () => {
  const [screen, setScreen] = useState<QuizScreen>('start');
  const {
    gameState,
    currentQuestion,
    leaderboard,
    isLoading,
    currentPlayer,
    selectedAnswer,
    answerResult,
    createGame,
    submitAnswer,
    nextRound,
    loadLeaderboard,
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

  const handlePackClick = (packType: string) => {
    setScreen('setup');
    // Could pre-fill topic based on packType
  };

  if (screen === 'setup') {
    return (
      <div className={styles.quizPage}>
        <QuizSetup onSubmit={handleSetupSubmit} isLoading={isLoading} />
      </div>
    );
  }

  if (screen === 'game' && currentQuestion && gameState) {
    const allOptions = currentQuestion.alternatives
      ? [currentQuestion.correct_answer, ...currentQuestion.alternatives]
      : [currentQuestion.correct_answer];
    const shuffledOptions = [...allOptions].sort(() => Math.random() - 0.5);

    const isCorrect = (option: string) =>
      answerResult ? option === answerResult.correctAnswer : false;
    const isSelected = (option: string) => selectedAnswer === option;
    const isIncorrect = (option: string) =>
      answerResult && selectedAnswer === option && !answerResult.correct;

    const canProceed = answerResult !== null && currentPlayer === gameState.players[gameState.players.length - 1];

    return (
      <div className={styles.quizPage}>
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
                disabled={!!answerResult}
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
      <QuizCard
        variant="featured"
        title="Top-Scorer der Hinrunde - für Mainz 05 in Saison Bundesliga?"
        subtitle="Personalisierte Empfehlung basierend auf deinen Interessen"
        metadata={[
          { label: 'Historische Statistiken', value: '' },
        ]}
        questionCount={50}
        onClick={() => setScreen('setup')}
      />

      <Card variant="elevated" padding="md">
        <h2 className={styles.sectionTitle}>Precomputed Packs</h2>
        <div className={styles.packsGrid}>
          <QuizCard
            title="Historische Momente"
            questionCount={50}
            onClick={() => handlePackClick('historische-momente')}
          />
          <QuizCard
            title="Spieler-Statistiken"
            questionCount={50}
            onClick={() => handlePackClick('spieler-statistiken')}
          />
        </div>
      </Card>

      <Card variant="elevated" padding="md">
        <h2 className={styles.sectionTitle}>Challenges & Wettbewerbe</h2>
        <div className={styles.challenges}>
          <Card variant="interactive" padding="md" className={styles.challengeCard}>
            <div className={styles.challengeHeader}>
              <div className={styles.challengeIcon}>
                <Trophy size={18} />
              </div>
              <div className={styles.challengeTitle}>Wöchentliches Leaderboard</div>
              <div className={styles.challengeCount}>50 Fragen</div>
            </div>
          </Card>
          <Card variant="interactive" padding="md" className={styles.challengeCard}>
            <div className={styles.challengeHeader}>
              <div className={styles.challengeIcon}>
                <Trophy size={18} />
              </div>
              <div className={styles.challengeTitle}>Stadionwissen</div>
              <div className={styles.challengeCount}>50 Fragen</div>
            </div>
          </Card>
        </div>
      </Card>
    </div>
  );
};



