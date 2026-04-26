import { useState, useEffect } from 'react';
import { api } from '../api';

function Dashboard({ onSelectRepo, currentUser }) {
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newRepoName, setNewRepoName] = useState('');
  const [creating, setCreating] = useState(false);
  const [nodeId, setNodeId] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [syncLogs, setSyncLogs] = useState([]);
  const [peers, setPeers] = useState([]);

  useEffect(() => {
    loadRepos();
    loadNodeId();
    loadPeers();
  }, []);

  const loadRepos = async () => {
    try {
      const data = await api.listRepos();
      setRepos(data);
    } catch (err) {
      setError('Failed to load repositories');
    } finally {
      setLoading(false);
    }
  };

  const loadNodeId = async () => {
    try {
      const data = await api.getNodeId();
      setNodeId(data.node_id);
    } catch (err) {
      console.error('Failed to load node ID');
    }
  };

  const loadPeers = async () => {
    try {
      const data = await api.getPeers();
      setPeers(data);
    } catch (err) {
      console.error('Failed to load peers');
    }
  };

  const handleCreateRepo = async (e) => {
    e.preventDefault();
    if (!newRepoName.trim()) return;
    
    setCreating(true);
    setError(null);
    
    try {
      await api.createRepo(newRepoName.trim(), currentUser.user_id);
      setNewRepoName('');
      loadRepos();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    setSyncLogs([]);
    try {
      const result = await api.sync('demo-repo', currentUser.user_id);
      if (result.logs) {
        setSyncLogs(result.logs);
      }
    } catch (err) {
      setError('Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div>
          <h2>Dashboard</h2>
          <p className="node-id">Node ID: <code>{nodeId}</code></p>
        </div>
        <div className="header-actions">
          <button 
            className="btn btn-success" 
            onClick={handleSync}
            disabled={syncing}
          >
            {syncing ? 'Syncing...' : '🔄 Sync with Peers'}
          </button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      {/* Peer Activity Logs */}
      {syncLogs.length > 0 && (
        <div className="card sync-logs-card">
          <h3>Peer Activity Log</h3>
          <div className="sync-logs">
            {syncLogs.map((log, idx) => (
              <div key={idx} className="sync-log-item">
                <span className="log-peer">{log.peer}</span>
                <span className="log-action">{log.action}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Peers Status */}
      <div className="card peers-card">
        <h3>Network Peers</h3>
        <div className="peers-list">
          {peers.map(peer => (
            <div key={peer.id} className="peer-item">
              <span className={`peer-status ${peer.online ? 'online' : 'offline'}`}></span>
              <span className="peer-name">{peer.name}</span>
              <span className="peer-addr">{peer.address}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card create-repo-card">
        <h3>Create New Repository</h3>
        <form onSubmit={handleCreateRepo} className="create-form">
          <input
            type="text"
            className="input"
            placeholder="Repository name"
            value={newRepoName}
            onChange={(e) => setNewRepoName(e.target.value)}
          />
          <button 
            type="submit" 
            className="btn btn-primary"
            disabled={creating || !newRepoName.trim()}
          >
            {creating ? 'Creating...' : 'Create'}
          </button>
        </form>
      </div>

      <div className="repos-grid">
        {repos.length === 0 ? (
          <div className="empty-state">
            <p>No repositories yet. Create one to get started!</p>
          </div>
        ) : (
          repos.map((repo) => (
            <div 
              key={repo.id} 
              className="card repo-card"
              onClick={() => onSelectRepo(repo.id)}
            >
              <h3>{repo.id}</h3>
              <p className="repo-head">
                HEAD: <code>{repo.head?.substring(0, 12) || 'None'}</code>
              </p>
              <p className="repo-collab">
                Collaborators: {repo.collaborators?.length || 0}
              </p>
              <button className="btn btn-secondary">View →</button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default Dashboard;