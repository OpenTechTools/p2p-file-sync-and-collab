# Frontend Module

The frontend is a React-based web application providing the user interface for the P2P decentralized versioning system. It connects to the backend API and enables users to manage repositories, create commits, and synchronize with peers.

---

## Architecture Overview

```
frontend/
├── src/
│   ├── App.jsx            # Main app component with routing
│   ├── App.css            # All component styles (CSS variables, components)
│   ├── api.js            # API client for backend communication
│   ├── index.css         # Tailwind import and base styles
│   ├── main.jsx          # React entry point
│   ├── pages/
│   │   ├── Login.jsx         # User login page
│   │   ├── Dashboard.jsx     # Main dashboard
│   │   └── Repository.jsx    # Repository detail page
│   └── assets/
│       └── *.svg, *.png   # Static assets
├── public/
│   ├── favicon.svg       # Favicon
│   └── icons.svg         # UI icons
├── package.json        # Dependencies and scripts
├── vite.config.js      # Vite bundler configuration
├── index.html        # HTML entry point
└── README.md         # This file
```

### Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19.2.5 | UI framework |
| React DOM | 19.2.5 | DOM rendering |
| Vite | 8.0.10 | Build tool and dev server |
| Tailwind CSS | 4.2.4 | Utility CSS framework |
| ESLint | 10.2.1 | Code linting |

### Design System (CSS Variables)

The application uses a comprehensive design system defined in CSS variables (`App.css`, lines 4-41):

| Variable | Value | Usage |
|----------|-------|-------|
| `--bg-primary` | #fafbfc | Page background |
| `--bg-card` | #ffffff | Card backgrounds |
| `--text-primary` | #111827 | Primary text |
| `--accent-primary` | #6366f1 | Primary accent color |
| `--success-text` | #059669 | Success messages |
| `--error-text` | #dc2626 | Error messages |
| `--font-sans` | Inter | Primary font |
| `--font-mono` | JetBrains Mono | Code/monospace font |

---

## App Component (`App.jsx`)

The root component manages application state and page navigation (client-side routing).

### State Management (lines 8-10)

```javascript
const [currentPage, setCurrentPage] = useState('login');
const [selectedRepo, setSelectedRepo] = useState(null);
const [currentUser, setCurrentUser] = useState(null);
```

| State | Type | Purpose |
|-------|------|--------|
| currentPage | string | Current view ('login', 'dashboard', 'repository') |
| selectedRepo | string \| null | Currently selected repository ID |
| currentUser | object \| null | Logged-in user object |

### Initialization (lines 12-18)

```javascript
useEffect(() => {
  const user = JSON.parse(localStorage.getItem('currentUser'));
  if (user) {
    setCurrentUser(user);
    setCurrentPage('dashboard');
  }
}, []);
```

**Process:**
1. On mount, check localStorage for saved user session
2. If user exists, restore session (auto-login)
3. Navigate to dashboard

### User Session Persistence

| Action | Storage | Data |
|--------|---------|------|
| Login | `localStorage.setItem('currentUser', JSON.stringify(user))` | User object |
| Logout | `localStorage.removeItem('currentUser')` | Removes user |

### Event Handlers

| Handler | Lines | Function |
|---------|-------|----------|
| `handleLogin` | 20-24 | Save user, navigate to dashboard |
| `handleLogout` | 26-31 | Clear user, navigate to login |
| `handleSelectRepo` | 33-36 | Select repo, navigate to repository page |
| `handleBack` | 38-41 | Clear selection, return to dashboard |

### Page Rendering (lines 43-78)

```javascript
if (!currentUser) {
  return <Login onLogin={handleLogin} />;
}
return (
  <div className="app">
    <header>...</header>
    <main>
      {currentPage === 'dashboard' && <Dashboard />}
      {currentPage === 'repository' && <Repository />}
    </main>
  </div>
);
```

**Rendering Logic:**
- No user → Show Login page
- Has user → Show header with user badge + Logout button
- `currentPage === 'dashboard'` → Render Dashboard
- `currentPage === 'repository'` → Render Repository

---

## API Client (`api.js`)

Centralized API client for all backend communication.

### Configuration (line 1)

```javascript
const API_URL = 'http://localhost:8000';
```

All API calls route through this base URL.

### Request Helper (lines 3-20)

```javascript
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
```

**Process:**
1. Build full URL from endpoint
2. Set Content-Type header to JSON
3. Stringify body if provided
4. Send fetch request
5. Parse JSON response
6. Throw error if response not ok
7. Return parsed data

### API Methods

| Method | Endpoint | Type | Description |
|--------|----------|------|-------------|
| `getInfo` | `/` | GET | Get API info |
| `login` | `/users/login` | POST | Login user |
| `logout` | `/users/logout` | POST | Logout user |
| `getCurrentUser` | `/users/me` | GET | Get current user |
| `listUsers` | `/users` | GET | List all users |
| `listRepos` | `/repos` | GET | List repositories |
| `createRepo` | `/repos` | POST | Create repository |
| `getRepo` | `/repos/{repoId}` | GET | Get repository |
| `getCollaborators` | `/repos/{repoId}/collaborators` | GET | List collaborators |
| `addCollaborator` | `/repos/{repoId}/collaborators` | POST | Add collaborator |
| `removeCollaborator` | `/repos/{repoId}/collaborators/{userId}` | DELETE | Remove collaborator |
| `getCommits` | `/repos/{repoId}/commits` | GET | Get commits |
| `createCommit` | `/repos/{repoId}/commits` | POST | Create commit |
| `getCommitFiles` | `/repos/{repoId}/commits/{commitCid}/files` | GET | Get commit files |
| `getPeers` | `/peers` | GET | Get peers |
| `sync` | `/repos/{repoId}/sync` | POST | Sync with peers |
| `getNodeId` | `/node-id` | GET | Get node ID |

---

## Login Page (`pages/Login.jsx`)

User authentication page with demo user support.

### State (lines 5-7)

```javascript
const [username, setUsername] = useState('');
const [loading, setLoading] = useState(false);
const [error, setError] = useState(null);
```

### Manual Login (lines 9-24)

```javascript
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
```

**Process:**
1. Prevent form default submission
2. Validate username (non-empty)
3. Call API to login/create user
4. On success, call `onLogin` callback
5. On error, display error message

### Demo User Login (lines 26-37)

```javascript
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
```

Allows instant login with predefined demo users.

### Demo Users

| User | Username |
|------|----------|
| Button 1 | Deepanshu |
| Button 2 | Priya |
| Button 3 | Mohit |
| Button 4 | Tanya |

### UI Components

- **Login header** - Title and subtitle
- **Username input** - Text field with placeholder
- **Login button** - Primary CTA button
- **Demo buttons** - Row of demo user quick-login buttons
- **Error display** - Red error message when login fails

---

## Dashboard Page (`pages/Dashboard.jsx`)

Main dashboard showing repositories, peers, and sync functionality.

### State (lines 5-13)

```javascript
const [repos, setRepos] = useState([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);
const [newRepoName, setNewRepoName] = useState('');
const [creating, setCreating] = useState(false);
const [nodeId, setNodeId] = useState('');
const [syncing, setSyncing] = useState(false);
const [syncLogs, setSyncLogs] = useState([]);
const [peers, setPeers] = useState([]);
```

### Data Loading (lines 15-48)

```javascript
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
```

**Data Load Strategy:**
1. `loadRepos()` - Fetches all repositories
2. `loadNodeId()` - Fetches current node ID
3. `loadPeers()` - Fetches peer list

### Create Repository (lines 50-66)

```javascript
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
```

**Process:**
1. Prevent form default
2. Validate repo name
3. Call API to create repository
4. Clear input and reload repos
5. Handle errors

### Sync with Peers (lines 68-81)

```javascript
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
```

**Sync Flow:**
1. Click "Sync with Peers" button
2. Call sync API
3. Display activity logs from peer interactions
4. Show sync progress

### UI Sections

| Section | Lines | Content |
|---------|-------|---------|
| Dashboard header | 88-103 | Title, node ID, sync button |
| Error display | 105 | Error messages |
| Sync logs | 107-120 | Peer activity log display |
| Peers card | 122-134 | Network peer status list |
| Create repo card | 136-154 | Repository creation form |
| Repos grid | 156-179 | Repository cards grid |

### Repository Card

```javascript
<div className="card repo-card" onClick={() => onSelectRepo(repo.id)}>
  <h3>{repo.id}</h3>
  <p className="repo-head">HEAD: <code>{repo.head?.substring(0, 12)}</code></p>
  <p className="repo-collab">Collaborators: {repo.collaborators?.length}</p>
  <button className="btn btn-secondary">View →</button>
</div>
```

**Displays:**
- Repository ID (title)
- HEAD commit CID (truncated to 12 chars)
- Collaborator count
- "View" button to navigate

### Peer Status Display

```javascript
<div className="peer-item">
  <span className={`peer-status ${peer.online ? 'online' : 'offline'}`}></span>
  <span className="peer-name">{peer.name}</span>
  <span className="peer-addr">{peer.address}</span>
</div>
```

**Shows:**
- Online/offline indicator (green/gray dot)
- Peer name
- IP address

---

## Repository Page (`pages/Repository.jsx`)

Detailed repository view with commit history, collaborator management, and commit creation.

### State (lines 5-21)

```javascript
const [commits, setCommits] = useState([]);
const [selectedCommit, setSelectedCommit] = useState(null);
const [commitFiles, setCommitFiles] = useState([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);
const [success, setSuccess] = useState(null);
const [validationLogs, setValidationLogs] = useState([]);
const [collaborators, setCollaborators] = useState([]);
const [availableUsers, setAvailableUsers] = useState([]);
const [message, setMessage] = useState('');
const [fileContent, setFileContent] = useState('');
const [fileName, setFileName] = useState('');
const [committing, setCommitting] = useState(false);
```

### Data Loading (lines 23-56)

```javascript
useEffect(() => {
  loadCommits();
  loadCollaborators();
  loadAvailableUsers();
}, [repoId]);
```

**On repoId change:**
1. `loadCommits()` - Fetch commit history
2. `loadCollaborators()` - Fetch authorized users
3. `loadAvailableUsers()` - Fetch all users for add-collab

### Load Commits (lines 29-38)

```javascript
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
```

### Load Collaborators (lines 40-47)

```javascript
const loadCollaborators = async () => {
  try {
    const data = await api.getCollaborators(repoId);
    setCollaborators(data);
  } catch (err) {
    console.error('Failed to load collaborators');
  }
};
```

### Add Collaborator (lines 68-77)

```javascript
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
```

**Process:**
1. Call API to add collaborator
2. Reload collaborators list
3. Show success message (auto-dismiss after 3s)

### Create Commit (lines 79-113)

```javascript
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
```

**Commit Creation Flow:**
1. Validate message and filename
2. Create files object with filename → content
3. Call API to create commit
4. Store validation logs for display
5. If accepted: show success, clear form, reload commits
6. If rejected: show error with reason and step

### UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Repository: {repoId}         {commitCount} commits       │
├─────────────────────────────────────────────────────────────┤
│  Validation Logs Card (when present)                        │
├───────────────────────────┬───────────────────────────────┤
│  Left Panel (Commits)       │  Right Panel (Details)       │
│  ┌─────────────────────┐   │   ┌───────────────────────┐  │
│  │ Commit History      │   │   │ New Commit Form       │  │
│  │ - commit item       │   │   │ (SMPP Signed)          │  │
│  │ - commit item       │   │   └───────────────────────┘  │
│  │ - ...               │   │   ┌───────────────────────┐  │
│  └─────────────────────┘   │   │ Files in Commit       │  │
│  ┌─────────────────────┐   │   └───────────────────────┘  │
│  │ Collaborators      │   │                             │
│  │ (CRDT)             │   │                             │
│  └─────────────────────┘   │                             │
└───────────────────────────┴───────────────────────────────┘
```

### Commit Item

```javascript
<div className="commit-item" onClick={() => handleSelectCommit(commit)}>
  <div className="commit-header">
    <code className="commit-cid">{commit.cid.substring(0, 8)}</code>
    <span className="commit-author">{commit.author}</span>
  </div>
  <p className="commit-message">{commit.message}</p>
  <span className="commit-time">
    {new Date(commit.timestamp * 1000).toLocaleString()}
  </span>
</div>
```

**Displays:**
- Commit CID (truncated to 8 chars)
- Author username
- Commit message
- Formatted timestamp

### Collaborator Item

```javascript
<div className="collaborator-item">
  <span className="collab-avatar">{collab.username[0].toUpperCase()}</span>
  <span className="collab-name">{collab.username}</span>
  {collab.user_id === currentUser.user_id && (
    <span className="collab-you">(you)</span>
  )}
</div>
```

**Shows:**
- Avatar (first letter of username, circular)
- Username
- "(you)" badge if current user

### Add Collaborator Dropdown

```javascript
<select onChange={(e) => {
  if (e.target.value) handleAddCollaborator(e.target.value);
  e.target.value = '';
}}>
  <option value="">Select user...</option>
  {unauthorizedUsers.map(user => (
    <option key={user.user_id} value={user.user_id}>
      {user.username}
    </option>
  ))}
</select>
```

Filters out already-authorized users.

### New Commit Form

| Field | Type | Purpose |
|-------|------|---------|
| File Name | text input | Name of file to create/modify |
| File Content | textarea | Content of the file |
| Commit Message | text input | Commit description |
| Sign & Commit | button | Submit commit |

---

## Styles (`App.css`)

The application uses a centralized CSS file with CSS custom properties and component classes.

### Design Tokens (lines 4-41)

**Colors:**
```css
--bg-primary: #fafbfc;
--text-primary: #111827;
--accent-primary: #6366f1;
--success-text: #059669;
--error-text: #dc2626;
```

**Shadows:**
```css
--shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
--shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
--shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
```

**Typography:**
```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
```

### Component Classes

| Class | Lines | Purpose |
|-------|-------|---------|
| `.btn` | 96-109 | Base button styles |
| `.btn-primary` | 116-126 | Primary action button |
| `.btn-secondary` | 128-138 | Secondary button |
| `.btn-success` | 140-149 | Success/positive button |
| `.btn-sm` | 151-154 | Small button variant |
| `.card` | 159-178 | Card container |
| `.input` | 183-202 | Form input styles |
| `.textarea` | 204-210 | Textarea specific |
| `.label` | 212-219 | Form label |
| `.error` | 235-243 | Error message box |
| `.success` | 245-253 | Success message box |
| `.header` | 63-85 | Page header |
| `.login-page` | 566-573 | Login page wrapper |
| `.login-card` | 575-582 | Login card container |
| `.dashboard` | 88-182 | Dashboard container |
| `.repo-layout` | 382-387 | Repository 2-column layout |
| `.repo--card` | 310-349 | Repository card |
| `.commit-item` | 401-418 | Commit list item |
| `.collaborator-item` | 761-768 | Collaborator badge |
| `.peer-item` | 669-703 | Peer status item |
| `.sync-logs` | 718-739 | Sync activity logs |

### Button States

**Primary Button:**
- Default: `--accent-primary` background
- Hover: `--accent-hover` with lift effect
- Disabled: 50% opacity

**Success Button:**
- Default: Gradient `#10b981` to `#059669`
- Hover: Lift effect

### Layout

**Header (lines 63-73):**
- Fixed position, sticky top
- Flex layout: logo left, user badge + logout right
- White background with bottom border

**Main (lines 87-91):**
- Max-width 1400px, centered
- Padding 40px 48px

**Repository Layout (lines 382-387):**
- CSS Grid: `1fr 1.2fr` columns
- Gap 28px
- Align items to top

### Responsive Breakpoints (lines 535-561)

```css
@media (max-width: 900px) {
  .repo-layout { grid-template-columns: 1fr; }
  .header { padding: 16px 24px; }
  .main { padding: 24px; }
}
```

Mobile breakpoint at 900px.

---

## User Flow

### 1. Login Flow

```
┌──────────────────────────────────────────┐
│              Login Page                   │
│  ┌────────────────────────────────────┐   │
│  │ Username: [____________]           │   │
│  │ [        Login        ]            │   │
│  └────────────────────────────────────┘   │
│                                          │
│  Or try demo:                            │
│  [Deepanshu] [Priya] [Mohit] [Tanya]     │
└──────────────────────────────────────────┘
                    │
                    ▼
           API: POST /users/login
                    │
                    ▼
┌──────────────────────────────────────────┐
│           Dashboard                       │
│  ┌────────────────┬─────────────────┐     │
│  │ Node ID: abc123│ [Sync Peers]    │     │
│  └────────────────┴─────────────────┘     │
│                                          │
│  [Peers: ● Peer A  ● Peer B  ○ Peer C]    │
│                                          │
│  Create New Repository:                  │
│  [_________________] [Create]             │
│                                          │
│  ┌─────────┐  ┌─────────┐               │
│  │ my-repo │  │test-repo│  ...           │
│  │ HEAD: a │  │ HEAD: b │               │
│  └─────────┘  └─────────┘               │
└──────────────────────────────────────────┘
```

### 2. Create Commit Flow

```
┌──────────────────────────────────────────────────────────┐
│              Repository: my-repo                       │
├────────────────────────────┬───────────────────────────┤
│  Commit History           │  New Commit (SMPP Signed)   │
│  ┌────────────────────┐   │  ┌─────────────────��─────┐  │
│  │ abc123 "Init"     │   │  │ File: [________]     │  │
│  │ Deepanshu 12:00    │   │  │ Content:             │  │
│  └────────────────────┘   │  │ [________________]    │  │
│  ┌────────────────────┐   │  │ Message:             │  │
│  │ def456 "Update"   │◀──│  │ [________________]    │  │
│  │ Deepanshu 12:30    │   │  │ [  Sign & Commit  ]   │  │
│  └────────────────────┘   │  └───────────────────────┘  │
│                          │                             │
│  Collaborators (CRDT)    │  Files in Commit           │
│  ┌────────────────────┐   │  ┌───────────────────────┐  │
│  │ (D) Deepanshu (you)│   │  │ Commit: Init         │  │
│  │ (P) Priya         │   │  │ ✓ SMPP Validated     │  │
│  └────────────────────┘   │  └───────────────────────┘  │
└──────────────────────────┴───────────────────────────────┘
```

### 3. Add Collaborator Flow

```
1. View repository collaborators
2. Select "Add collaborator" dropdown
3. Choose user (not already authorized)
4. API: POST /repos/{repoId}/collaborators
5. CRDT state updates
6. New collaborator appears in list
```

---

## Data Flow

### Component to API

```
Component (React)
    │
    ▼ calls
api.js function (e.g., api.createCommit(...))
    │
    ▼ fetch()
Backend API (FastAPI)
    │
    ▼ returns JSON
api.js parses response
    │
    ▼ returns data
Component updates state (useState)
    │
    ▼ triggers re-render
React re-renders UI
```

### State Management Pattern

```javascript
// 1. Set loading state
setLoading(true);
setError(null);

// 2. Call API
try {
  const data = await api.someMethod();
  // 3. Update state on success
  setData(data);
} catch (err) {
  // 4. Handle errors
  setError(err.message);
} finally {
  // 5. Clear loading state
  setLoading(false);
}
```

---

## Build and Development

### Scripts (`package.json`)

| Command | Description |
|--------|-------------|
| `npm run dev` | Start Vite dev server |
| `npm run build` | Build for production |
| `npm run lint` | Run ESLint |
| `npm run preview` | Preview production build |

### Development Server

```bash
npm run dev
# Runs on http://localhost:5173
```

### Production Build

```bash
npm run build
# Output in dist/ folder
```

---

## Security Considerations

1. **User Sessions** - Stored in localStorage (client-side only)
2. **API Authentication** - Backend handles auth via user_id
3. **No Passwords** - Username-based auth (demo system)
4. **XSS Protection** - React escapes content by default

### Production Recommendations

- Use HttpOnly cookies for session storage
- Implement proper authentication
- Add CSRF protection
- Use HTTPS for all API calls

---

## Key Features

1. **User Authentication** - Login with demo users
2. **Repository Management** - Create, view, select repositories
3. **Collaborator Management** - CRDT-authorized users
4. **Commit Creation** - SMPP-signed commits
5. **Commit History** - View all commits
6. **Peer Sync** - Simulated P2P synchronization
7. **Validation Logs** - Display CRDT/SMPP validation steps
8. **Responsive Design** - Mobile-friendly layout

---

## System Integration

The frontend connects to the backend API:

```
┌─────────────────────────────────────┐
│         React Frontend               │
│    (http://localhost:5173)        │
└──────────────┬────────────────────┘
               │ HTTP/REST API
               ▼
┌─────────────────────────────────────┐
│         FastAPI Backend             │
│    (http://localhost:8000)        │
└──────────────┬────────────────────┘
               │
    ┌─────────┼─────────┐
    │         │         │
    ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌───────┐
│ DHT   │ │ RUDP  │ │ CRDT  │
│ Node  │ │ Peer  │ │ LWW   │
└───────┘ └───────┘ └───────┘
```