# Execution Flow Documentation

This document explains what happens internally when a user performs actions in the system.

---

## 1. LOGIN FLOW

### Frontend
- **File**: `frontend/src/pages/Login.jsx`
- **Function**: `handleDemoUser(username)` or form submit
- **Action**: Calls `api.login(username)` from `frontend/src/api.js`

### API Call
- **Endpoint**: `POST /users/login`
- **File**: `frontend/src/api.js`

### Backend
- **File**: `backend/api/server.py`
- **Function**: `login(request: LoginRequest)`
- **Line**: Around line 140

### Logic
- **File**: `backend/security/user.py`
- **Function**: `UserManager.get_user_by_username()` and `UserManager.create_user()`

### Flow Details:
```
1. User enters username (or clicks demo button)
2. API sends POST to /users/login with username
3. Server checks if user exists in UserManager
4. If new user: generates new User with:
   - username
   - user_id (random 16 hex chars)
   - keypair (public/private keys)
5. User is logged in (stored in session)
6. Returns user object with user_id and public_key
```

### Output
- User session created
- Frontend stores user in localStorage

---

## 2. COMMIT FLOW

### Frontend
- **File**: `frontend/src/pages/Repository.jsx`
- **Function**: `handleCommit(e)`
- **Action**: Collects file content, message, calls `api.createCommit()`

### API Call
- **Endpoint**: `POST /repos/{repo_id}/commits`
- **File**: `frontend/src/api.js`

### Backend
- **File**: `backend/api/server.py`
- **Function**: `create_commit(repo_id, request: CommitRequest)`

### Step-by-Step Flow:

#### Step 1: User Request
```
Input: { repo_id, user_id, message, files: {filename: content} }
```

#### Step 2: CRDT Authorization Check
- **File**: `backend/api/server.py` - `create_commit()` function
- **Log**: `"[CRDT] Checking authorization for {username}"`
- **Logic**: Calls `repo.is_authorized(user_id, public_key)`
- **File**: `backend/crdt/lww_set.py`
- **Function**: `CRDTState.is_authorized()`
- **Logic**: Checks if public_key exists in LWWSet

**If NOT authorized**:
- Returns rejection immediately with `"validation_step": "authorization"`

#### Step 3: Merkle DAG Commit Creation
- **File**: `backend/api/server.py` - `create_commit()` function
- **Log**: `"[MERKLE] Creating commit hash"`
- **Logic**:
  1. For each file: create Blob → compute CID (SHA-256)
  2. Create Tree with TreeEntry for each file
  3. Create Commit with:
     - tree_cid (from Tree)
     - parent_cids (previous commit)
     - author (username)
     - message
     - timestamp

- **Files used**:
  - `backend/storage/merkle.py` - CID, Blob, Tree, Commit classes

**Log**: `"[MERKLE] Linking to previous commit: {parent_cid}"`

#### Step 4: SMPP Signing
- **File**: `backend/api/server.py` - `create_commit()` function
- **Log**: `"[SMPP] Signing commit"`
- **Logic**:
  1. Create SMPPRecord with:
     - repo_id
     - commit_cid
     - crdt_state_cid
     - timestamp
  2. Sign using user's keypair: `user.keypair.sign(record_bytes)`

- **Files used**:
  - `backend/security/smpp.py` - SMPPRecord class
  - `backend/security/crypto.py` - KeyPair.sign()

#### Step 5: SMPP Validation
- **File**: `backend/api/server.py` - `create_commit()` function
- **Log**: `"[SMPP] Verifying signature"`
- **Logic**: Call `user.keypair.verify(record_bytes, signature)`

**Log**: `"[SMPP] Validation: VALID"` or `"[SMPP] Validation: REJECTED"`

#### Step 6: Store Commit
- **File**: `backend/api/server.py` - `create_commit()` function
- **Logic**: Save commit to `repo.commits` dict with:
  - cid, author, author_id, message, timestamp, parent_cids, signature

### Output
```json
{
  "status": "accepted",
  "cid": "...",
  "smpp_valid": true,
  "logs": ["[USER]", "[CRDT]", "[MERKLE]", "[SMPP]"]
}
```

---

## 3. SYNC FLOW

### Frontend
- **File**: `frontend/src/pages/Dashboard.jsx`
- **Function**: `handleSync()`
- **Action**: Calls `api.sync(repoId, userId)`

### API Call
- **Endpoint**: `POST /repos/{repo_id}/sync`

### Backend
- **File**: `backend/api/server.py`
- **Function**: `sync_with_peers(repo_id, request)`

### Step-by-Step Flow:

#### Step 1: Get Peers
- **File**: `backend/api/server.py`
- **Logic**: Access `state.peers` (simulated peers list)
- **Peers defined in**: `ServerState._create_simulated_peers()`
- **File**: `backend/api/server.py` (ServerState class)

#### Step 2: Peer Activity Simulation
For each online peer (Peer A, Peer B):
- **Log**: `"[SYNC] Fetching from {peer_name}"`
- **Log**: `"[SYNC] Validating via SMPP..."`
- **Log**: `"[SYNC] CRDT merge complete"`

These are simulated activities - no actual network calls.

#### Step 3: Return Activity Logs
- **File**: `backend/api/server.py`
- Returns list of peer activities with timestamps

### Output
```json
{
  "status": "synced",
  "logs": [
    {"peer": "Peer A", "action": "[SYNC] Fetching from Peer A", "timestamp": ...},
    {"peer": "Peer A", "action": "[SYNC] Validating via SMPP...", "timestamp": ...},
    {"peer": "Peer A", "action": "[SYNC] CRDT merge complete", "timestamp": ...},
    {"peer": "Peer B", "action": "..."}
  ]
}
```

---

## 4. ADD COLLABORATOR FLOW

### Frontend
- **File**: `frontend/src/pages/Repository.jsx`
- **Function**: `handleAddCollaborator(targetUserId)`

### API Call
- **Endpoint**: `POST /repos/{repo_id}/collaborators`

### Backend
- **File**: `backend/api/server.py`
- **Function**: `add_collaborator(repo_id, request)`

### Logic:
1. Check if requester is authorized (via CRDT)
2. Get target user from UserManager
3. Call `repo.add_collaborator(user_id, public_key)`
4. **CRDT**: Adds public_key to LWWSet with timestamp

- **File**: `backend/crdt/lww_set.py`
- **Function**: `CRDTState.authorize(public_key)`

---

## COMPONENT USAGE SUMMARY

### CRDT (Conflict-free Replicated Data Type)
**Where used**:
- Authorization checking in commit flow
- Adding collaborators
- File: `backend/crdt/lww_set.py`

**Purpose**: Manage authorized users per repository

### SMPP (Signed Merkle Pointer Protocol)
**Where used**:
- Creating SMPP record before commit
- Signing record with user's keypair
- Verifying signature
- Files: `backend/security/smpp.py`, `backend/api/server.py`

**Purpose**: Ensure commit authenticity and prevent tampering

### Merkle DAG
**Where used**:
- Creating Blob from file content
- Creating Tree from entries
- Creating Commit with parent references
- Computing CIDs (content hashes)
- File: `backend/storage/merkle.py`

**Purpose**: Content-addressable version storage

### Simulated Peers
**Where used**:
- Sync with peers endpoint
- Display in Dashboard
- File: `backend/api/server.py` (ServerState class)

**Purpose**: Demonstrate P2P sync concept (not real networking)

---

## KEY FILES REFERENCE

| Component | File | Key Functions |
|-----------|------|---------------|
| Login | `backend/security/user.py` | `create_user()`, `login()` |
| Authorization | `backend/crdt/lww_set.py` | `is_authorized()`, `authorize()` |
| Commit Storage | `backend/storage/merkle.py` | `Commit()`, `CID.from_data()` |
| Signing | `backend/security/crypto.py` | `KeyPair.sign()`, `verify()` |
| SMPP | `backend/security/smpp.py` | `SMPPRecord.to_bytes()` |
| API | `backend/api/server.py` | `create_commit()`, `sync_with_peers()` |
| Frontend | `frontend/src/pages/Repository.jsx` | `handleCommit()`, `handleSync()` |