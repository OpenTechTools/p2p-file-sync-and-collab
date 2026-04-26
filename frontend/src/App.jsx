import { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import Repository from './pages/Repository';
import Login from './pages/Login';
import './App.css';

function App() {
  const [currentPage, setCurrentPage] = useState('login');
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);

  useEffect(() => {
    const user = JSON.parse(localStorage.getItem('currentUser'));
    if (user) {
      setCurrentUser(user);
      setCurrentPage('dashboard');
    }
  }, []);

  const handleLogin = (user) => {
    setCurrentUser(user);
    localStorage.setItem('currentUser', JSON.stringify(user));
    setCurrentPage('dashboard');
  };

  const handleLogout = () => {
    setCurrentUser(null);
    setSelectedRepo(null);
    localStorage.removeItem('currentUser');
    setCurrentPage('login');
  };

  const handleSelectRepo = (repoId) => {
    setSelectedRepo(repoId);
    setCurrentPage('repository');
  };

  const handleBack = () => {
    setSelectedRepo(null);
    setCurrentPage('dashboard');
  };

  if (!currentUser) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <h1 onClick={handleBack} style={{ cursor: 'pointer' }}>
            P2P Version Control
          </h1>
        </div>
        <div className="header-right">
          <span className="user-badge">{currentUser.username}</span>
          <button className="btn-secondary btn-sm" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      <main className="main">
        {currentPage === 'dashboard' && (
          <Dashboard 
            onSelectRepo={handleSelectRepo} 
            currentUser={currentUser}
          />
        )}
        {currentPage === 'repository' && selectedRepo && (
          <Repository 
            repoId={selectedRepo} 
            currentUser={currentUser}
          />
        )}
      </main>
    </div>
  );
}

export default App;