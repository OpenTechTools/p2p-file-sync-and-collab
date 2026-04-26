# Frontend

## Structure

```
frontend/
├── src/
│   ├── api.js           # API client for backend calls
│   ├── App.jsx          # Main app component with routing
│   ├── App.css          # All styles (Tailwind)
│   ├── index.css        # Tailwind imports
│   └── pages/
│       ├── Login.jsx        # Login screen with demo users
│       ├── Dashboard.jsx    # Repository list, peers, sync
│       └── Repository.jsx   # Commit history, collaborators, SMPP
├── index.html
└── package.json
```

## How to Run

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Start the backend (FastAPI):**
   ```bash
   cd ..
   pip install fastapi uvicorn
   python -m backend.api.server
   ```
   Backend runs on http://localhost:8000

3. **Start the frontend:**
   ```bash
   cd frontend
   npm run dev
   ```
   Frontend runs on http://localhost:5173

## How It Connects to Backend

The frontend uses `src/api.js` to communicate with the FastAPI backend:

### User Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/users/login` | POST | Login with username |
| `/users/me` | GET | Get current user |
| `/users` | GET | List all users |

### Repository Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/repos` | GET | List all repositories |
| `/repos` | POST | Create new repository |
| `/repos/{id}` | GET | Get repository details |
| `/repos/{id}/collaborators` | GET | List collaborators |
| `/repos/{id}/collaborators` | POST | Add collaborator |

### Commit Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/repos/{id}/commits` | GET | Get commit history |
| `/repos/{id}/commits` | POST | Create commit (SMPP signed) |
| `/repos/{id}/commits/{cid}/files` | GET | Get files in commit |

### Peer Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/peers` | GET | List simulated peers |
| `/repos/{id}/sync` | POST | Sync with peers |

## Features

### Login Page
- Username input for custom login
- Demo user buttons: Deepanshu, Priya, Mohit, Tanya
- Session persistence via localStorage

### Dashboard
- View/create repositories
- See simulated network peers (Peer A, B, C)
- Sync button shows peer activity logs
- Current user displayed in header

### Repository View
- Commit history with author names
- Create commits with file content
- SMPP validation status displayed
- Collaborators list (managed by CRDT)
- Add/remove collaborators dropdown

## User Flow

1. **Login**: Enter username or click demo button
2. **Dashboard**: See repos, peers, create new repo
3. **Repository**: View commits, create commits, manage collaborators
4. **Collaborate**: Add other users to enable them to commit

## Tech Stack

- **React 18** with Vite
- **Tailwind CSS** for styling
- **Fetch API** for backend communication

## API Response Examples

### Login Response
```json
{
  "username": "Deepanshu",
  "user_id": "abc123...",
  "public_key": "def456..."
}
```

### Commit Response (Accepted)
```json
{
  "status": "accepted",
  "cid": "abc123...",
  "message": "Add feature",
  "smpp_valid": true,
  "validation_step": "all"
}
```

### Commit Response (Rejected)
```json
{
  "status": "rejected",
  "reason": "Not authorized",
  "smpp_valid": false,
  "validation_step": "authorization"
}
```