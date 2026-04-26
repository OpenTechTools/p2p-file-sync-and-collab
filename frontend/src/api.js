const API_URL = 'http://localhost:8000';

async function request(endpoint, options = {}) {
  const url = `${API_URL}${endpoint}`;
  const config = {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  };
  
  if (options.body) {
    config.body = JSON.stringify(options.body);
  }
  
  const response = await fetch(url, config);
  const data = await response.json().catch(() => ({ detail: 'Request failed' }));
  if (!response.ok) {
    throw new Error(data.detail || 'Request failed');
  }
  return data;
}

export const api = {
  // Root
  getInfo: () => request('/'),
  
  // Users
  login: (username) => request('/users/login', {
    method: 'POST',
    body: { username },
  }),
  
  logout: () => request('/users/logout', { method: 'POST' }),
  
  getCurrentUser: () => request('/users/me'),
  
  listUsers: () => request('/users'),
  
  // Repos
  listRepos: () => request('/repos'),
  
  createRepo: (repoId, userId) => request('/repos', {
    method: 'POST',
    body: { repo_id: repoId, user_id: userId },
  }),
  
  getRepo: (repoId) => request(`/repos/${repoId}`),
  
  // Collaborators
  getCollaborators: (repoId) => request(`/repos/${repoId}/collaborators`),
  
  addCollaborator: (repoId, userId, targetUserId) => request(`/repos/${repoId}/collaborators`, {
    method: 'POST',
    body: { repo_id: repoId, user_id: userId, target_user_id: targetUserId },
  }),
  
  removeCollaborator: (repoId, userId) => request(`/repos/${repoId}/collaborators/${userId}`, {
    method: 'DELETE',
  }),
  
  // Commits
  getCommits: (repoId, limit = 10) => request(`/repos/${repoId}/commits?limit=${limit}`),
  
  createCommit: (repoId, userId, message, files) => request(`/repos/${repoId}/commits`, {
    method: 'POST',
    body: { repo_id: repoId, user_id: userId, message, files },
  }),
  
  getCommitFiles: (repoId, commitCid) => request(`/repos/${repoId}/commits/${commitCid}/files`),
  
  // Peers
  getPeers: () => request('/peers'),
  
  sync: (repoId, userId) => request(`/repos/${repoId}/sync`, {
    method: 'POST',
    body: { repo_id: repoId, user_id: userId },
  }),
  
  // Node
  getNodeId: () => request('/node-id'),
};