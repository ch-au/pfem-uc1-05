import React, { useState } from 'react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Alert } from '../components/ui/Alert';
import { QuizSetup } from '../components/quiz/QuizSetup';
import { QuizQuestion } from '../components/quiz/QuizQuestion';
import { QuizOption } from '../components/quiz/QuizOption';
import { Leaderboard } from '../components/quiz/Leaderboard';
import { PlayerHandoff } from '../components/quiz/PlayerHandoff';
import { RoundResults } from '../components/quiz/RoundResults';
import { useQuizGame } from '../hooks/useQuizGame';
import { quizService } from '../services/quizService';
import { Trophy, Trash2, Home } from 'lucide-react';
import type { QuizGameState, QuizLeaderboardEntry } from '../types/api';
import styles from './QuizPage.module.css';

type QuizScreen = 'start' | 'setup' | 'game';

export const QuizPage: React.FC = () => {
  const [screen, setScreen] = useState<QuizScreen>('start');
  const [gameHistory, setGameHistory] = useState<QuizGameState[]>([]);
  const [globalLeaderboard, setGlobalLeaderboard] = useState<QuizLeaderboardEntry[]>([]);
  const [isLoadingLeaderboard, setIsLoadingLeaderboard] = useState(false);
  const statusLabels: Record<string, string> = {
    pending: 'Wartet',
    sql_generated: 'Fragen werden generiert',
    answer_verified: 'Antworten werden geprüft',
    round_created: 'Runde erstellt',
    running: 'Läuft',
    queued: 'Wartet',
    succeeded: 'Fertig',
  };
  const {
    gameState,
    currentQuestion,
    leaderboard,
    isLoading,
    error,
    statusMessage,
    generationProgress,
    currentPlayer,
    currentPlayerIndex,
    selectedAnswer,
    createGame,
    loadGame,
    submitAnswer,
    nextRound,
    loadLeaderboard,
    reset,
    gamePhase,
    roundResults,
    correctAnswerForRound,
    explanationForRound,
    confirmHandoff,
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
      await loadGameHistory();
      await loadGlobalLeaderboard();
      setScreen('game');
    } catch (error: any) {
      // Check if this was a topic rejection
      if (error?.code === 'TOPIC_REJECTED') {
        console.log('Topic rejected:', error.message);
        // Error is already set in the hook with the rejection reason
      } else {
        console.error('Failed to create game:', error);
      }
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
      await loadLeaderboard();
    } catch (error) {
      console.error('Failed to advance round:', error);
    }
  };

  const validGames = gameHistory.filter((game) => game.players && game.players.length > 0);
  const activeGames = validGames.filter(
    (game) => game.status === 'in_progress' || game.status === 'pending'
  );
  const completedGames = validGames.filter((game) => game.status === 'completed').slice(0, 5);

  // Load game history on mount
  React.useEffect(() => {
    loadGameHistory();
    loadGlobalLeaderboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadGameHistory = async () => {
    try {
      const result = await quizService.getGameHistory({ limit: 10 });
      setGameHistory(result.games || []);
    } catch (error) {
      console.error('Failed to load game history:', error);
    }
  };

  const loadGlobalLeaderboard = async () => {
    try {
      setIsLoadingLeaderboard(true);
      const result = await quizService.getGlobalLeaderboard(10);
      setGlobalLeaderboard(result || []);
    } catch (error) {
      console.error('Failed to load leaderboard:', error);
    } finally {
      setIsLoadingLeaderboard(false);
    }
  };

  const handleSelectGame = async (gameId: string) => {
    try {
      const game = await loadGame(gameId);
      await loadGameHistory();
      
      if (!game.players || game.players.length === 0) {
        alert(`Dieses Quiz wurde mit einer älteren Version erstellt und hat keine Spieler.\n\nBitte starte ein neues Quiz.`);
        return;
      }
      
      setScreen('game');
    } catch (error: any) {
      console.error('Failed to load game:', error);
      
      const is404Error = error?.response?.status === 404 || 
                          error?.message?.includes('404') ||
                          error?.message?.includes('Question not found');
      
      if (is404Error) {
        alert(`Dieses Quiz kann nicht geladen werden, da die Fragen noch generiert werden oder ein Fehler aufgetreten ist.\n\nBitte starte ein neues Quiz.`);
      } else {
        const errorMessage = error instanceof Error ? error.message : 'Unbekannter Fehler';
        alert(`Fehler beim Laden des Quiz: ${errorMessage}`);
      }
    }
  };

  const handleDeleteGame = async (gameId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Dieses Quiz wirklich löschen?')) return;
    
    try {
      await quizService.deleteGame(gameId);
      await loadGameHistory();
      await loadGlobalLeaderboard();
    } catch (error) {
      console.error('Failed to delete game:', error);
      alert('Fehler beim Löschen des Quiz');
    }
  };

  const handleErrorClose = () => {
    reset();
  };

  if (screen === 'setup') {
    return (
      <div className={styles.quizPage}>
        {statusMessage && !generationProgress && (
          <Alert
            variant="info"
            title="Quiz wird vorbereitet"
            message={statusMessage}
          />
        )}
        {generationProgress && (
          <div className={styles.statusInline} style={{ marginBottom: '1rem' }}>
            <div className={styles.spinner} aria-hidden />
            <div>
              <div className={styles.statusTitle}>Quiz wird vorbereitet</div>
              <div className={styles.statusText}>
                Runde {generationProgress.completed_rounds}/{generationProgress.total_rounds}
              </div>
              {generationProgress.current_status && (
                <div className={styles.progressStatus}>
                  {statusLabels[generationProgress.current_status] ?? generationProgress.current_status}
                </div>
              )}
            </div>
          </div>
        )}
        {error && (
          <Alert
            variant={error.includes('nicht verarbeitet') || error.includes('nicht erlaubt') || error.includes('historisch') ? 'warning' : 'error'}
            title={error.includes('nicht verarbeitet') || error.includes('nicht erlaubt') || error.includes('historisch') ? 'Thema nicht erlaubt' : 'Quiz Erstellung fehlgeschlagen'}
            message={error}
            onClose={handleErrorClose}
          />
        )}
        <QuizSetup onSubmit={handleSetupSubmit} isLoading={isLoading} />
      </div>
    );
  }

  if (screen === 'game') {
    if (!gameState) {
      return (
        <div className={styles.quizPage}>
          <Card variant="elevated" padding="lg">
            <div className={styles.startContent}>
              <h1 className={styles.startTitle}>Lade Quiz...</h1>
              {statusMessage && <p className={styles.statusText}>{statusMessage}</p>}
            </div>
          </Card>
        </div>
      );
    }

    if (gameState.status === 'completed') {
      return (
        <div className={styles.quizPage}>
          <div className={styles.layout}>
            <div className={styles.mainColumn}>
              <Card variant="elevated" padding="lg">
                <div className={styles.startContent}>
                  <h1 className={styles.startTitle}>Quiz abgeschlossen</h1>
                  <p className={styles.startDescription}>
                    {gameState.topic || 'Dein Quiz'} ist beendet. Hier sind die Ergebnisse.
                  </p>
                  <Button
                    variant="primary"
                    size="lg"
                    onClick={() => {
                      setScreen('start');
                      reset();
                    }}
                    className={styles.startButton}
                  >
                    Neues Quiz starten
                  </Button>
                </div>
              </Card>

              <Card variant="elevated" padding="md">
                <h2 className={styles.sectionTitle}>
                  <Trophy size={24} />
                  Endstand
                </h2>
                {leaderboard.length > 0 ? (
                  <Leaderboard entries={leaderboard} />
                ) : (
                  <p className={styles.statusText}>Keine Ergebnisse verfügbar.</p>
                )}
              </Card>
            </div>
          </div>
        </div>
      );
    }

    if (!currentQuestion) {
      return (
        <div className={styles.quizPage}>
          <Card variant="elevated" padding="lg">
            <div className={styles.startContent}>
              <h1 className={styles.startTitle}>Lade Frage...</h1>
              {statusMessage && <p className={styles.statusText}>{statusMessage}</p>}
            </div>
          </Card>
        </div>
      );
    }

    const allOptions = (currentQuestion.alternatives || []).filter(
      (option) => option && option.trim().length > 0
    );

    const isSelected = (option: string): boolean => selectedAnswer === option;

    const handlePauseGame = () => {
      if (confirm('Quiz pausieren und zum Hauptmenü zurückkehren? Du kannst später weiterspielen.')) {
        setScreen('start');
        reset();
      }
    };

    if (gamePhase === 'handoff') {
      return (
        <div className={styles.quizPage}>
          <PlayerHandoff
            nextPlayer={currentPlayer}
            roundNumber={gameState.current_round}
            totalRounds={gameState.num_rounds}
            onReady={confirmHandoff}
          />
        </div>
      );
    }

    if (gamePhase === 'results') {
      return (
        <div className={styles.quizPage}>
          <div className={styles.layout}>
            <div className={styles.mainColumn}>
              <RoundResults
                roundNumber={gameState.current_round}
                totalRounds={gameState.num_rounds}
                correctAnswer={correctAnswerForRound}
                explanation={explanationForRound}
                playerResults={roundResults}
                onNextRound={handleNextRound}
                isLastRound={gameState.current_round >= gameState.num_rounds}
              />
            </div>
            <aside className={styles.sidebar}>
              <Card variant="elevated" padding="md">
                <h2 className={styles.sectionTitle}>
                  <Trophy size={24} />
                  Aktuelle Punkte
                </h2>
                {leaderboard.length > 0 ? (
                  <Leaderboard entries={leaderboard} />
                ) : (
                  <p className={styles.statusText}>Leaderboard wird aufgebaut...</p>
                )}
              </Card>
            </aside>
          </div>
        </div>
      );
    }

    return (
      <div className={styles.quizPage}>
        <div className={styles.gameControls}>
          <Button
            variant="secondary"
            size="sm"
            onClick={handlePauseGame}
            className={styles.controlButton}
          >
            <Home size={18} />
            <span>Beenden</span>
          </Button>
          
          <div className={styles.gameInfo}>
            <span className={styles.gameTopic}>{gameState.topic || 'Quiz'}</span>
            <span className={styles.gameProgress}>
              Runde {gameState.current_round} von {gameState.num_rounds}
            </span>
          </div>

          <div className={styles.controlPlaceholder} />
        </div>

        {error && (
          <Alert
            variant="error"
            title="Fehler"
            message={error}
            onClose={handleErrorClose}
          />
        )}

        <div className={styles.layout}>
          <div className={styles.mainColumn}>
            <Card variant="elevated" padding="md">
              <QuizQuestion
                question={currentQuestion.question_text}
                roundNumber={currentQuestion.round_number || gameState.current_round}
                totalRounds={gameState.num_rounds}
                currentPlayer={currentPlayer}
                players={gameState.players}
                currentPlayerIndex={currentPlayerIndex}
              />

              <div className={styles.options}>
                {allOptions.length === 0 && (
                  <p className={styles.statusText}>Antworten werden geladen...</p>
                )}
                {allOptions.map((option, index) => (
                  <QuizOption
                    key={option}
                    option={option}
                    label={option}
                    index={index}
                    selected={isSelected(option)}
                    correct={false}
                    incorrect={false}
                    disabled={selectedAnswer !== null || isLoading}
                    onClick={() => handleAnswerSelect(option)}
                  />
                ))}
              </div>
            </Card>
          </div>

          <aside className={styles.sidebar}>
            {(statusMessage || generationProgress) && (
              <div className={styles.statusInline}>
                <div className={styles.spinner} aria-hidden />
                <div>
                  <div className={styles.statusTitle}>Quiz wird vorbereitet</div>
                  {statusMessage && <div className={styles.statusText}>{statusMessage}</div>}
                  {generationProgress && (
                    <div className={styles.progressRow}>
                      <span>
                        Runde {generationProgress.completed_rounds}/{generationProgress.total_rounds}
                      </span>
                      {generationProgress.current_status && (
                        <span className={styles.progressStatus}>
                          {statusLabels[generationProgress.current_status] ?? generationProgress.current_status}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            <Card variant="elevated" padding="md">
              <h2 className={styles.sectionTitle}>
                <Trophy size={24} />
                Aktuelle Punkte
              </h2>
              {leaderboard.length > 0 ? (
                <Leaderboard entries={leaderboard} />
              ) : (
                <p className={styles.statusText}>Leaderboard wird aufgebaut...</p>
              )}
            </Card>
          </aside>
        </div>
      </div>
    );
  }

  // Start screen
  return (
    <div className={styles.quizPage}>
      <div className={styles.layout}>
        <div className={styles.mainColumn}>
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

          <div className={styles.historyGrid}>
            <Card variant="elevated" padding="md">
              <h2 className={styles.sectionTitle}>
                Laufende Spiele
              </h2>
              {activeGames.length > 0 ? (
                <div className={styles.gameList}>
                  {activeGames.map((game) => (
                    <div
                      key={game.game_id}
                      className={styles.gameListItem}
                      onClick={() => handleSelectGame(game.game_id)}
                    >
                      <div>
                        <div className={styles.gameTitle}>{game.topic || 'Quiz'}</div>
                        <div className={styles.gameMeta}>
                          Runde {game.current_round}/{game.num_rounds} • {game.players.length} Spieler
                        </div>
                      </div>
                      <div className={styles.gameActions}>
                        <span className={styles.badge}>
                          {game.status === 'pending' ? 'Wartet' : 'Läuft'}
                        </span>
                        <button
                          className={styles.deleteButton}
                          onClick={(e) => handleDeleteGame(game.game_id, e)}
                          title="Quiz löschen"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className={styles.statusText}>Keine aktiven Spiele. Starte ein neues Quiz!</p>
              )}
            </Card>

            <Card variant="elevated" padding="md">
              <h2 className={styles.sectionTitle}>
                Kürzlich abgeschlossen
              </h2>
              {completedGames.length > 0 ? (
                <div className={styles.gameList}>
                  {completedGames.map((game) => (
                    <div
                      key={game.game_id}
                      className={styles.gameListItem}
                      onClick={() => handleSelectGame(game.game_id)}
                    >
                      <div>
                        <div className={styles.gameTitle}>{game.topic || 'Quiz'}</div>
                        <div className={styles.gameMeta}>
                          {game.num_rounds} Runden • {game.players.length} Spieler
                        </div>
                      </div>
                      <div className={styles.gameActions}>
                        <span className={styles.badge}>Beendet</span>
                        <button
                          className={styles.deleteButton}
                          onClick={(e) => handleDeleteGame(game.game_id, e)}
                          title="Quiz löschen"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className={styles.statusText}>Noch keine abgeschlossenen Spiele.</p>
              )}
            </Card>
          </div>
        </div>

        <aside className={styles.sidebar}>
          <Card variant="elevated" padding="md">
            <h2 className={styles.sectionTitle}>
              <Trophy size={24} />
              Globales Leaderboard
            </h2>
            {isLoadingLeaderboard && <p className={styles.statusText}>Lade Leaderboard...</p>}
            {!isLoadingLeaderboard && globalLeaderboard.length === 0 && (
              <p className={styles.statusText}>Noch keine Ergebnisse vorhanden.</p>
            )}
            {globalLeaderboard.length > 0 && (
              <Leaderboard entries={globalLeaderboard} />
            )}
          </Card>
        </aside>
      </div>
    </div>
  );
};

