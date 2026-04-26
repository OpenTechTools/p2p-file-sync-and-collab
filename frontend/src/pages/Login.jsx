import { useState } from 'react';
import { api } from '../api';

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const user = await api.login(username.trim());
      onLogin(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDemoUser = async (demoUsername) => {
    setLoading(true);
    setError(null);
    try {
      const user = await api.login(demoUsername);
      onLogin(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <h1>P2P Version Control</h1>
          <p>Decentralized file versioning system</p>
        </div>

        {error && <div className="error">{error}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label className="label">Username</label>
            <input
              type="text"
              className="input"
              placeholder="Enter username..."
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading}
            />
          </div>
          <button 
            type="submit" 
            className="btn btn-primary"
            disabled={loading || !username.trim()}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className="demo-users">
          <p>Or try a demo user:</p>
          <div className="demo-buttons">
            <button 
              className="btn btn-secondary btn-sm"
              onClick={() => handleDemoUser('Deepanshu')}
              disabled={loading}
            >
              Deepanshu
            </button>
            <button 
              className="btn btn-secondary btn-sm"
              onClick={() => handleDemoUser('Priya')}
              disabled={loading}
            >
              Priya
            </button>
            <button 
              className="btn btn-secondary btn-sm"
              onClick={() => handleDemoUser('Mohit')}
              disabled={loading}
            >
              Mohit
            </button>
            <button 
              className="btn btn-secondary btn-sm"
              onClick={() => handleDemoUser('Tanya')}
              disabled={loading}
            >
              Tanya
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Login;