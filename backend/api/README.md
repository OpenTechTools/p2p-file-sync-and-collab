# API Module

## Purpose

The API module provides high-level API for repository operations and P2P node management in the decentralized versioning system. It serves as the bridge between the user-facing interfaces and the underlying decentralized infrastructure.

---

## Architecture Overview

```
backend/api/
├── __init__.py      # Exports Repository and NodeAPI
├── repo.py          # Core repository and node interfaces
├── server.py        # FastAPI HTTP server
└── README.md        # This file
```

The API module integrates all subsystems:
- **DHT (Distributed Hash Table)** - Peer discovery and network routing
- **Transport (RUDP)** - Reliable P2P data transfer
- **Storage (Merkle DAG)** - Content-addressed data storage
- **CRDT** - Conflict-free replicated data types for collaboration
- **Security** - Cryptographic keys and SMPP validation

---

## Package Exports (`__init__.py`)

```python
from .repo import Repository, NodeAPI

__all__ = ['Repository', 'NodeAPI']
```

This module exports two main classes:
1. **Repository** - Represents a single versioned repository
2. **NodeAPI** - High-level API for P2P node operations

---

## Repository Class (`repo.py`, lines 18-145)

The `Repository` class is the main interface for decentralized version control. It manages commits, files, and integrates with all underlying subsystems.

### Constructor

```python
def __init__(
    self,
    repo_id: str,
    node: DHTNode,
    object_store: ObjectStore,
    crdt_manager: CRDTManager,
    smpp_store: SMPPStore,
    key_pair: KeyPair
):
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| repo_id | str | Unique identifier for this repository |
| node | DHTNode | DHT node for peer communication |
| object_store | ObjectStore | Storage for blobs, trees, commits |
| crdt_manager | CRDTManager | Manages CRDT state for collaboration |
| smpp_store | SMPPStore | Stores SMPP records for validation |
| key_pair | KeyPair | User's cryptographic keypair |

### Internal State

| Field | Type | Description |
|-------|------|-------------|
| repo_id | str | Repository identifier |
| node | DHTNode | DHT node reference |
| object_store | ObjectStore | Content-addressed storage |
| crdt_manager | CRDTManager | CRDT state manager |
| smpp_store | SMPPStore | SMPP record storage |
| key_pair | KeyPair | User's cryptographic keys |
| head | Optional[CID] | Current HEAD commit |

### Initialization

```python
def init(self) -> CID:
    """Initialize empty repository."""
```

When called, it performs:

1. **Create empty tree** - A tree with no entries represents the initial state
2. **Store in Merkle DAG** - The empty tree is content-addressed and stored
3. **Create initial commit** - A commit with:
   - Tree CID pointing to empty tree
   - No parent commits
   - Author set to first 8 chars of public key
   - Message: "Initial commit"
4. **Set HEAD** - The initial commit becomes the repository head
5. **Authorize owner** - The creator's public key is added to CRDT authorized keys

**Returns:** CID of the initial commit

### Commit Creation

```python
def commit(self, message: str, changed_files: Dict[str, bytes]) -> CID:
    """Create a new commit with file changes."""
```

This is the core version control operation. It performs:

1. **Process changed files** - For each (filename, content) pair:
   - Create a **Blob** object from the content
   - Store the blob in the object store, receiving a CID
   - Create a **TreeEntry** with filename, blob CID, and type 'blob'

2. **Create tree** - Assemble entries into a **Tree** object:
   - Tree represents a directory structure
   - Each entry maps filename to content CID

3. **Store tree** - Content-address the tree and store it

4. **Get parent CIDs** - If HEAD exists, use it as parent; otherwise empty list

5. **Create commit** - Build a **Commit** object with:
   - Tree CID (points to new file structure)
   - Parent CIDs (previous HEAD or empty)
   - Author (derived from public key)
   - Message (commit message)
   - Timestamp (current time)

6. **Store commit** - Content-address and persist the commit

7. **Update HEAD** - Point to new commit

8. **Create SMPP record** - Generate **SMPP (Signed Merkle Patricia Proof)** record:
   - Contains: repo_id, commit_cid, crdt_state_cid, timestamp
   - Signed with user's private key
   - Stored in SMPP store for validation

9. **Return commit CID**

**Returns:** CID of newly created commit

### Retrieve Commit

```python
def get_commit(self, cid: CID) -> Optional[Commit]:
    """Retrieve a commit by CID."""
```

Simply retrieves a commit from the object store by its CID.

**Returns:** Commit object or None if not found

### Get File Content

```python
def get_file(self, commit_cid: CID, filename: str) -> Optional[bytes]:
    """Get file content at specific commit."""
```

To retrieve a file at a specific commit:

1. **Fetch commit** - Get commit object by CID
2. **Fetch tree** - Get tree object referenced by commit's tree_cid
3. **Find entry** - Search tree entries for matching filename
4. **Fetch blob** - If found, get blob by its CID
5. **Return content** - Return blob data as bytes

**Returns:** File content or None if not found

### Get History

```python
def get_history(self, limit: int = 10) -> List[Commit]:
    """Get commit history."""
```

Traverses commit history by following parent links:

1. Start at HEAD
2. Fetch commit, add to history list
3. Move to first parent
4. Repeat until limit reached or no more parents

**Returns:** List of commits (newest first), up to limit

### Get HEAD

```python
def get_head(self) -> Optional[CID]:
    """Get current head commit CID."""
```

**Returns:** Current HEAD commit CID or None

---

## NodeAPI Class (`repo.py`, lines 147-196)

The `NodeAPI` class provides a high-level interface for P2P node operations. It manages the entire lifecycle of a decentralized node including repository management, network joining, and subsystem initialization.

### Constructor

```python
def __init__(self, data_dir: str = "./data"):
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| data_dir | str | Directory for all node data |

### Internal State

| Field | Type | Description |
|-------|------|-------------|
| data_dir | str | Data directory path |
| node | DHTNode | DHT node for peer discovery |
| dht | MerkleDAG | Merkle DAG for content addressing |
| object_store | ObjectStore | Object storage layer |
| crdt_manager | CRDTManager | CRDT state management |
| smpp_store | SMPPStore | SMPP record storage |
| key_pair | KeyPair | Node's cryptographic keys |
| repositories | Dict[str, Repository] | Managed repositories |

### Initialization Process

When created, `NodeAPI`:

1. **Creates data directory** - Ensures data_dir exists
2. **Initializes DHT node** - Creates new DHT node for peer discovery
3. **Creates Merkle DAG** - Object storage at `data_dir/objects`
4. **Creates object store** - Wraps Merkle DAG
5. **Creates CRDT manager** - State management at `data_dir/crdt`
6. **Creates SMPP store** - SMPP records at `data_dir/smpp`
7. **Generates keypair** - Creates new cryptographic keypair for this node
8. **Initializes empty repo dict** - Ready for repository management

### Create Repository

```python
def create_repository(self, repo_id: str) -> Repository:
    """Create a new repository."""
```

Creates a new repository and registers it:

1. **Instantiate Repository** with:
   - repo_id
   - node reference
   - object_store
   - crdt_manager
   - smpp_store
   - key_pair

2. **Auto-authorize** - Owner's public key is authorized in CRDT

3. **Register** - Add to repositories dictionary

4. **Return** - The created Repository instance

### Get Repository

```python
def get_repository(self, repo_id: str) -> Optional[Repository]:
    """Get existing repository."""
```

Looks up repository by ID in the internal dictionary.

**Returns:** Repository or None

### Join Network

```python
def join_network(self, bootstrap_nodes: List[tuple]) -> None:
    """Join P2P network via bootstrap nodes."""
```

Connects to P2P network using bootstrap nodes:

1. **For each bootstrap node** (address, port):
   - Create Peer with generated NodeID
   - Add to DHT routing table bucket

This enables the node to discover other peers in the network.

### Start/Stop

```python
def start(self) -> None:
    """Start the node."""
    pass

def stop(self) -> None:
    """Stop the node."""
    pass
```

Placeholder lifecycle methods for node startup/shutdown.

---

## Server Module (`server.py`)

The server module implements a FastAPI HTTP server that provides REST API endpoints for the decentralized versioning system. It's designed for web clients and supports multi-user collaboration.

### Server Initialization (lines 22-30)

```python
app = FastAPI(title="P2P Versioning API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Creates FastAPI app with CORS enabled for cross-origin requests.

### ServerState Class (lines 36-56)

Manages global server state including:

| Field | Type | Description |
|-------|------|-------------|
| user_manager | UserManager | Manages users and authentication |
| crdt_manager | CRDTManager | Global CRDT state management |
| repositories | Dict[str, RepoState] | Active repositories |
| peers | List[Dict] | Simulated peer nodes |

### RepoState Class (lines 59-82)

Per-repository state with CRDT integration:

| Field | Type | Description |
|-------|------|-------------|
| repo_id | str | Repository identifier |
| head | Optional[CID] | Current HEAD commit |
| commits | Dict[str, Dict] | Commit storage |
| crdt_state | CRDTState | CRDT authorization state |

**Methods:**
- `is_authorized()` - Check if user can access
- `add_collaborator()` - Add authorized user
- `remove_collaborator()` - Remove authorization
- `get_collaborators()` - List authorized users

---

## API Endpoints

### Root Endpoint

```
GET /
```

Returns API version and features.

### User Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /users | List all users |
| POST | /users/login | Login by username |
| GET | /users/me | Get current user |
| POST | /users/logout | Logout current user |

### Repository Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /repos | List all repositories |
| POST | /repos | Create new repository |
| GET | /repos/{repo_id} | Get repository details |
| GET | /repos/{repo_id}/collaborators | List collaborators |
| POST | /repos/{repo_id}/collaborators | Add collaborator |
| DELETE | /repos/{repo_id}/collaborators/{user_id} | Remove collaborator |

### Commit Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /repos/{repo_id}/commits | Get commit history |
| POST | /repos/{repo_id}/commits | Create new commit |
| GET | /repos/{repo_id}/commits/{commit_cid}/files | Get files in commit |

### Sync Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /peers | Get simulated peers |
| POST | /repos/{repo_id}/sync | Sync with peers |

### Node Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /node-id | Get current node ID |

---

## Commit Creation Flow

When a client creates a commit via POST `/repos/{repo_id}/commits`, the server performs:

### Step 1: Authorization Check (lines 352-368)

```
[CRDT] Checking authorization for {username}
[CRDT] Result: ALLOWED/DENIED
```

Uses CRDT to verify the user is authorized to commit to this repository.

### Step 2: Merkle DAG Creation (lines 370-386)

```
[MERKLE] Creating commit hash
[MERKLE] Linking to previous commit: {cid}...
```

1. Creates Blob objects for each file
2. Creates Tree with file entries
3. Creates Commit with tree CID and parent(s)

### Step 3: SMPP Signing (lines 396-411)

```
[SMPP] Signing commit
```

1. Creates SMPPRecord with:
   - repo_id
   - commit_cid
   - crdt_state_cid
   - timestamp

2. Signs record with user's private key

### Step 4: Signature Verification (lines 413-429)

```
[SMPP] Verifying signature
[SMPP] Validation: VALID/REJECTED
```

Verifies the signature using the user's public key.

### Step 5: Store Commit (lines 431-450)

```
[USER] {username} requested commit: {message}
```

Stores commit in repository and updates HEAD.

---

## How Components Work Together

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Server                          │
│                   (backend/api/server.py)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
   User Manager    Repository    CRDT Manager
   (security)      (repo.py)     (crdt)
        │              │              │
        └──────────────┼──────────────┘
                       │
                       ▼
              ┌────────────────┐
              │   Repository   │
              │   (repo.py)    │
              └───────┬────────┘
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
    ▼                 ▼                 ▼
 DHT Node        Object Store      SMPP Store
 (network)       (storage)         (security)
    │                 │                 │
    └─────────────────┼─────────────────┘
                      │
                      ▼
              ┌────────────────┐
              │   RUDP         │
              │ (transport)    │
              └────────────────┘
```

---

## Key Features

1. **Multi-user collaboration** - CRDT-based authorization
2. **Content-addressed storage** - Merkle DAG for deduplication
3. **Cryptographic verification** - SMPP signatures
4. **P2P communication** - RUDP for reliable transfers
5. **Distributed hash table** - DHT for peer discovery
6. **REST API** - HTTP endpoints for web clients
7. **Commit history** - Git-like version control
8. **File retrieval** - Get files at any commit

---

## System Integration

The API module sits at the top of the backend architecture:

```
frontend/          → Web UI
    │
backend/api/       → REST API (FastAPI)
    │
backend/network/   → DHT, peer discovery
backend/transport/ → RUDP (reliable P2P)
backend/storage/    → Merkle DAG storage
backend/security/   → Crypto, SMPP
backend/crdt/      → Conflict resolution
```

The current server uses HTTP for web API, while RUDP handles peer-to-peer data transfer between nodes in the decentralized network.
