import { useState, useEffect } from 'react';
import { api } from '../api';

function Repository({ repoId, currentUser }) {
  const [commits, setCommits] = useState([]);
  const [selectedCommit, setSelectedCommit] = useState(null);
  const [commitFiles, setCommitFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [validationLogs, setValidationLogs] = useState([]);
  
  // Collaborators
  const [collaborators, setCollaborators] = useState([]);
  const [availableUsers, setAvailableUsers] = useState([]);
  
  // New commit form
  const [message, setMessage] = useState('');
  const [fileContent, setFileContent] = useState('');
  const [fileName, setFileName] = useState('');
  const [committing, setCommitting] = useState(false);

  useEffect(() => {
    loadCommits();
    loadCollaborators();
    loadAvailableUsers();
  }, [repoId]);

  const loadCommits = async () => {
    try {
      const data = await api.getCommits(repoId);
      setCommits(data);
    } catch (err) {
      setError('Failed to load commits');
    } finally {
      setLoading(false);
    }
  };

  const loadCollaborators = async () => {
    try {
      const data = await api.getCollaborators(repoId);
      setCollaborators(data);
    } catch (err) {
      console.error('Failed to load collaborators');
    }
  };

  const loadAvailableUsers = async () => {
    try {
      const data = await api.listUsers();
      setAvailableUsers(data);
    } catch (err) {
      console.error('Failed to load users');
    }
  };

  const handleSelectCommit = async (commit) => {
    setSelectedCommit(commit);
    try {
      const data = await api.getCommitFiles(repoId, commit.cid);
      setCommitFiles(data.files);
    } catch (err) {
      setCommitFiles([]);
    }
  };

  const handleAddCollaborator = async (targetUserId) => {
    try {
      await api.addCollaborator(repoId, currentUser.user_id, targetUserId);
      loadCollaborators();
      setSuccess('Collaborator added!');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCommit = async (e) => {
    e.preventDefault();
    if (!message.trim() || !fileName.trim()) return;

    setCommitting(true);
    setError(null);
    setSuccess(null);
    setValidationLogs([]);

    try {
      const files = {};
      files[fileName] = fileContent;
      
      const result = await api.createCommit(repoId, currentUser.user_id, message, files);
      
      // Store validation logs for display
      if (result.logs) {
        setValidationLogs(result.logs);
      }
      
      if (result.status === 'accepted') {
        setSuccess(`Commit accepted! CID: ${result.cid.substring(0, 12)} (SMPP: Valid)`);
        setMessage('');
        setFileContent('');
        setFileName('');
        loadCommits();
      } else {
        setError(`Commit rejected: ${result.reason} (Step: ${result.validation_step})`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setCommitting(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  const authorizedCollaboratorIds = collaborators.map(c => c.user_id);
  const unauthorizedUsers = availableUsers.filter(u => !authorizedCollaboratorIds.includes(u.user_id));

  return (
    <div className="repository">
      <div className="repo-header">
        <h2>Repository: {repoId}</h2>
        <p className="commit-count">{commits.length} commits</p>
      </div>

      {error && <div className="error">{error}</div>}
      {success && <div className="success">{success}</div>}

      {/* Validation Logs Display */}
      {validationLogs.length > 0 && (
        <div className="card validation-logs-card">
          <h3>Validation Logs</h3>
          <div className="validation-logs">
            {validationLogs.map((log, idx) => (
              <div key={idx} className="validation-log-item">{log}</div>
            ))}
          </div>
        </div>
      )}

      <div className="repo-layout">
        {/* Left: Commits */}
        <div className="commits-panel">
          <div className="card">
            <h3>Commit History</h3>
            {commits.length === 0 ? (
              <p className="empty">No commits yet</p>
            ) : (
              <div className="commits-list">
                {commits.map((commit) => (
                  <div
                    key={commit.cid}
                    className={`commit-item ${selectedCommit?.cid === commit.cid ? 'selected' : ''}`}
                    onClick={() => handleSelectCommit(commit)}
                  >
                    <div className="commit-header">
                      <code className="commit-cid">{commit.cid.substring(0, 8)}</code>
                      <span className="commit-author">{commit.author}</span>
                    </div>
                    <p className="commit-message">{commit.message}</p>
                    <span className="commit-time">
                      {new Date(commit.timestamp * 1000).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Collaborators */}
          <div className="card collaborators-card">
            <h3>Collaborators (CRDT)</h3>
            <div className="collaborators-list">
              {collaborators.map(collab => (
                <div key={collab.user_id} className="collaborator-item">
                  <span className="collab-avatar">{collab.username[0].toUpperCase()}</span>
                  <span className="collab-name">{collab.username}</span>
                  {collab.user_id === currentUser.user_id && (
                    <span className="collab-you">(you)</span>
                  )}
                </div>
              ))}
            </div>
            
            {unauthorizedUsers.length > 0 && (
              <div className="add-collaborator">
                <p>Add collaborator:</p>
                <select 
                  className="input"
                  onChange={(e) => {
                    if (e.target.value) handleAddCollaborator(e.target.value);
                    e.target.value = '';
                  }}
                >
                  <option value="">Select user...</option>
                  {unauthorizedUsers.map(user => (
                    <option key={user.user_id} value={user.user_id}>
                      {user.username}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {/* Right: Details */}
        <div className="details-panel">
          <div className="card commit-form-card">
            <h3>New Commit (SMPP Signed)</h3>
            <form onSubmit={handleCommit}>
              <div className="form-group">
                <label className="label">File Name</label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g., hello.py"
                  value={fileName}
                  onChange={(e) => setFileName(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="label">File Content</label>
                <textarea
                  className="input textarea"
                  placeholder="Enter file content..."
                  value={fileContent}
                  onChange={(e) => setFileContent(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="label">Commit Message</label>
                <input
                  type="text"
                  className="input"
                  placeholder="Describe your changes..."
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                />
              </div>
              <button 
                type="submit" 
                className="btn btn-primary"
                disabled={committing || !message.trim() || !fileName.trim()}
              >
                {committing ? 'Signing & Committing...' : 'Sign & Commit'}
              </button>
            </form>
          </div>

          <div className="card">
            <h3>Files in Commit</h3>
            {selectedCommit ? (
              <div className="files-info">
                <p>Commit by: <strong>{selectedCommit.author}</strong></p>
                <p className="smpp-status">✓ SMPP Validated</p>
              </div>
            ) : (
              <p className="empty">Select a commit to view details</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Repository;