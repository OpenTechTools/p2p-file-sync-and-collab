# Decentralized P2P File Versioning System

A peer-to-peer version control system with multi-user collaboration support, featuring the Signed Merkle Pointer Protocol (SMPP) for secure commit validation.

---

## 1. PROJECT OVERVIEW

### What the System Does
This system implements a **decentralized version control system** similar to Git, but without a central server. Multiple users can collaborate on repositories, with all data stored in a distributed manner.

### Key Idea: Decentralized Version Control
Traditional version control (like Git) uses a central server. This system removes the central server:
- Every user is a **peer** in the network
- Data is stored using **Merkle DAG** (content-addressable)
- No single point of failure
- Users can work offline

### Main Contribution: SMPP Protocol
The **Signed Merkle Pointer Protocol (SMPP)** is our key innovation:
- Every commit is **digitally signed** by the author
- Before accepting a commit, the system **validates** the signature
- Only authorized users (managed by CRDT) can commit
- This prevents unauthorized modifications

---

## 2. ARCHITECTURE

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                       │
│  Login → Dashboard → Repository View                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  Users   │  │  Repos   │  │  Peers   │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
│         │            │            │                         │
│         ▼            ▼            ▼                         │
│  ┌──────────────────────────────────────┐                  │
│  │         SMPP Validation              │                  │
│  │  (Signature + CRDT Authorization)    │                  │
│  └──────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Merkle DAG   │    │    CRDT      │    │  Kademlia    │
│   Storage    │    │  (LWW Set)   │    │    DHT       │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Component Details

#### 2.1 Merkle DAG (storage/)
- **Blob**: Raw file content (chunked)
- **Tree**: Directory structure (lists of entries)
- **Commit**: Version snapshot with parent references
- **CID**: Content Identifier (SHA-256 hash)
- Files are deduplicated by content

#### 2.2 CRDT - Conflict-free Replicated Data Type (crdt/)
- **LWW Set**: Last-Writer-Wins Set
- Used for **authorization management**
- Each repository has a set of authorized users
- When users merge, conflicts resolve automatically (latest wins)

#### 2.3 SMPP Protocol (security/)
- **Record**: Contains repo_id, commit_cid, crdt_state_cid, timestamp, signature
- **Signing**: User signs the record with their private key
- **Validation**: Server verifies signature and checks CRDT authorization

#### 2.4 Simulated Kademlia / Peers (api/server.py)
- For demo, peers are simulated
- Shows network activity logs
- Demonstrates sync concept

---

## 3. BACKEND EXPLANATION

### Folder Structure

```
backend/
├── api/           # FastAPI server
├── cli/           # Command-line interface
├── crdt/          # CRDT implementation
├── network/       # Kademlia DHT (stub)
├── security/      # Crypto, SMPP, Users
├── storage/       # Merkle DAG
└── transport/     # Reliable UDP (stub)
```

### Detailed Explanation

#### 3.1 network/ - Kademlia DHT
| File | Purpose |
|------|---------|
| `dht.py` | Node ID generation, k-buckets, routing table |
| `protocol.py` | DHT message types (PING, FIND_NODE, etc.) |

**Simple Explanation**: This module handles peer discovery. In our demo, it's a stub - we use simulated peers instead.

#### 3.2 transport/ - Reliable UDP
| File | Purpose |
|------|---------|
| `rudp.py` | Selective Repeat ARQ for reliable transmission |

**Simple Explanation**: Handles data transmission. In our demo, we use regular HTTP instead.

#### 3.3 storage/ - Merkle DAG
| File | Purpose |
|------|---------|
| `merkle.py` | CID, Blob, Tree, Commit classes |
| `store.py` | High-level object storage interface |

**Simple Explanation**: Stores files and versions. Each file gets a unique ID based on content (like Git).

#### 3.4 crdt/ - Conflict Resolution
| File | Purpose |
|------|---------|
| `lww_set.py` | LWW Element, LWW Set, CRDT State, CRDT Manager |

**Simple Explanation**: Manages who can commit. Uses timestamps to resolve conflicts automatically.

#### 3.5 security/ - Security
| File | Purpose |
|------|---------|
| `crypto.py` | KeyPair generation, signing, verification |
| `smpp.py` | SMPP record, validator, store |
| `user.py` | User management, sessions |

**Simple Explanation**: Handles authentication and commit validation.

#### 3.6 api/ - Server
| File | Purpose |
|------|---------|
| `server.py` | FastAPI endpoints for all operations |
| `repo.py` | Repository and NodeAPI classes |

**Simple Explanation**: The HTTP API that frontend connects to.

#### 3.7 cli/ - Command Line
| File | Purpose |
|------|---------|
| `main.py` | CLI commands (init, commit, log) |

**Simple Explanation**: Alternative interface for terminal users.

---

## 4. FRONTEND EXPLANATION

### Structure

```
frontend/src/
├── api.js           # API client functions
├── App.jsx          # Main component with routing
├── App.css          # Styles
├── index.css        # Tailwind imports
└── pages/
    ├── Login.jsx      # Login screen
    ├── Dashboard.jsx  # Repository list & peers
    └── Repository.jsx # Commit history & files
```

### Pages Explanation

#### 4.1 Login.jsx
- Shows login form
- Demo user buttons (Deepanshu, Priya, Mohit, Tanya)
- Stores user in localStorage

#### 4.2 Dashboard.jsx
- Shows all repositories
- Create new repository
- View simulated peers (Peer A, B, C)
- Sync button shows peer activity logs

#### 4.3 Repository.jsx
- Shows commit history with author names
- Create new commits (file + message)
- SMPP validation status shown
- Collaborators list (CRDT managed)
- Add/remove collaborators

### User Flow
1. User logs in
2. User creates/selects repository
3. User views commits or creates new ones
4. Commit is signed and validated via SMPP
5. User can add collaborators

---

## 5. MULTI-USER SYSTEM

### 5.1 How Login Works
1. User enters username (or clicks demo button)
2. Backend creates/retrieves user with keypair
3. User ID stored in localStorage
4. All API calls include user_id

### 5.2 Collaborator Management (CRDT)
1. Repository creator is automatically authorized
2. Owner can add other users via dropdown
3. CRDT stores authorized public keys
4. When user tries to commit, system checks CRDT

### 5.3 Authorization Enforcement
```
Request → Check CRDT → If authorized → Accept commit
                     → If not authorized → Reject with reason
```

---

## 6. SMPP (SIGNED MERKLE POINTER PROTOCOL)

### 6.1 Protocol Overview
SMPP ensures only authorized users can commit, and all commits are verifiable.

### 6.2 Record Structure
```json
{
  "repo_id": "my-repo",
  "commit_cid": "abc123...",
  "crdt_state_cid": "def456...",
  "timestamp": 1234567890.123,
  "signature": "sig_bytes_here"
}
```

### 6.3 Signing Process
1. User creates commit (content)
2. System creates SMPP record
3. User signs record with their private key
4. Signature attached to record
5. Record stored with commit

### 6.4 Validation Steps (on server)
When receiving a commit, server performs:

| Step | Check | Purpose |
|------|-------|---------|
| 1 | Verify signature | Ensure commit was made by the claimed user |
| 2 | Fetch CRDT state | Get current authorized users list |
| 3 | Check authorization | Is user in CRDT authorized list? |
| 4 | Check timestamp | Anti-replay protection |

### 6.5 How SMPP Prevents Unauthorized Updates
1. **No signature**: Rejected at step 1
2. **Wrong signature**: Rejected at step 1
3. **Not in CRDT**: Rejected at step 3
4. **Replay attack**: Rejected at step 4 (timestamp check)

---

## 7. DATA FLOW

### Complete Flow Example

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. LOGIN                                                        │
│ User: "Deepanshu"                                               │
│ Backend: Creates user if new, generates keypair                 │
│ Returns: user_id, public_key                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. CREATE REPOSITORY                                           │
│ POST /repos { repo_id: "project", user_id: "..." }             │
│ Backend: Creates RepoState, adds creator to CRDT               │
│ Returns: head commit CID                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. CREATE COMMIT                                                │
│ POST /repos/project/commits {                                  │
│   user_id: "...",                                               │
│   message: "Add feature",                                       │
│   files: { "main.py": "print('hello')" }                       │
│ }                                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. SMPP VALIDATION                                              │
│                                                                  │
│ a) CRDT Authorization Check                                     │
│    - Is user's public_key in CRDT authorized set?               │
│    - If NO → REJECT: "Not authorized"                           │
│                                                                  │
│ b) Create SMPP Record                                           │
│    - repo_id, commit_cid, crdt_state_cid, timestamp             │
│                                                                  │
│ c) Sign with user's private key                                 │
│                                                                  │
│ d) Verify signature                                             │
│    - If INVALID → REJECT: "Invalid signature"                   │
│                                                                  │
│ e) Store commit with author info                                │
│    - If ALL PASS → ACCEPT                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. VIEW HISTORY / SYNC                                          │
│ GET /repos/project/commits                                      │
│ Shows: CID, author, message, timestamp, parent_cids            │
│                                                                  │
│ POST /repos/project/sync                                        │
│ Returns simulated peer activity logs                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. DEMO INSTRUCTIONS

### 8.1 Running the Backend
```bash
# Install dependencies
pip install fastapi uvicorn

# Run server (Terminal 1)
python -m backend.api.server

# Server runs at: http://localhost:8000
# API docs at: http://localhost:8000/docs
```

### 8.2 Running the Frontend
```bash
# Install dependencies
cd frontend
npm install

# Run dev server (Terminal 2)
npm run dev

# Frontend runs at: http://localhost:5173
```

### 8.3 Example Demo Flow

1. **Open browser** to http://localhost:5173

2. **Login** as "Deepanshu" (click demo button)

3. **Create repository**:
   - Enter name: "my-project"
   - Click "Create"

4. **Create first commit**:
   - File name: "hello.py"
   - Content: "print('Hello World')"
   - Message: "Initial commit"
   - Click "Sign & Commit"
   - See: "Commit accepted! SMPP: Valid"

5. **Add collaborator**:
   - (In this session, you're Deepanshu)
   - Other users can be added by logging in as different user

6. **View history**:
   - See commits with author names
   - Click commit to see details

7. **Sync**:
   - Click "Sync with Peers" button
   - See simulated peer activity logs

---

## 9. LIMITATIONS

### Current Limitations

| Limitation | Description |
|------------|-------------|
| Simulated Networking | Peers are simulated, not real P2P |
| Single Server | Uses centralized API (FastAPI) |
| In-Memory State | Server state resets on restart |
| Simple Crypto | Using HMAC instead of proper digital signatures |

### Future Work

| Feature | Description |
|---------|-------------|
| Real Kademlia DHT | Implement actual peer discovery |
| True RUDP | Implement Selective Repeat ARQ |
| IPFS Integration | Use IPFS for storage |
| Blockchain | Store commit hashes on blockchain |
| Real Signatures | Use Ed25519 or ECDSA |

---

## 10. CONCLUSION

This project demonstrates the core concepts of:
- **Decentralized version control** using Merkle DAG
- **Collaborative authorization** using CRDT (LWW Set)
- **Secure commits** using SMPP protocol
- **Content-addressable storage** similar to IPFS

The system shows how these technologies work together to create a secure, decentralized version control system. While the current implementation is a demo (with simulated networking), the core concepts are production-ready.

### Key Takeaways

1. **Merkle DAG** provides content-addressable, deduplicated storage
2. **CRDT** enables conflict-free collaborative authorization
3. **SMPP** ensures commits are signed and validated
4. **Simulated peers** demonstrate the P2P concept

---

*Documentation generated for educational purposes - Decentralized P2P File Versioning System*