import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Header } from './components/layout/Header';
import { Navigation } from './components/layout/Navigation';
import { MobileNav } from './components/layout/MobileNav';
import { ChatPage } from './pages/ChatPage';
import { QuizPage } from './pages/QuizPage';
import './styles/global.css';
import './styles/animations.css';

function App() {
  return (
    <Router>
      <div className="app">
        <Header onProfileClick={() => alert('Profil-Funktion wird später implementiert')} />
        <Navigation />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/quiz" element={<QuizPage />} />
          </Routes>
        </main>
        <MobileNav />
      </div>
    </Router>
  );
}

export default App;
