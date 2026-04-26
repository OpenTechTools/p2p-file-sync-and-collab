# Backend Documentation

## Overview

The backend implements a decentralized P2P file versioning system with:
- Merkle DAG for content-addressable storage
- CRDT (LWW Set) for authorization
- SMPP (Signed Merkle Pointer Protocol) for commit validation
- Simulated Kademlia DHT and Reliable UDP (stubs)

## Folder Structure

```
backend/
├── api/           # FastAPI server & repository management
├── cli/           # Command-line interface
├── crdt/          # CRDT (LWW Set) implementation
├── network/       # Kademlia DHT (stub)
├── security/      # Crypto, SMPP, User management
├── storage/       # Merkle DAG
└── transport/     # Reliable UDP (stub)
```

## Module Details

### 1. network/ - Kademlia DHT

**Purpose**: Peer discovery in P2P network

| File | Description |
|------|-------------|
| `dht.py` | Node ID (160-bit), KBucket, RoutingTable, DHTNode |
| `protocol.py` | DHT message types and serialization |

**Status**: Stub implementation (not fully connected)

### 2. transport/ - Reliable UDP

**Purpose**: Reliable data transmission using Selective Repeat ARQ

| File | Description |
|------|-------------|
| `rudp.py` | Packet, SlidingWindow, RUDPSession, RUDPProtocol |

**Status**: Stub implementation (not fully connected)

### 3. storage/ - Merkle DAG

**Purpose**: Content-addressable version storage

| File | Description |
|------|-------------|
| `merkle.py` | CID, Blob, Tree, TreeEntry, Commit classes; MerkleDAG |
| `store.py` | ObjectStore - high-level storage interface |

**Key Classes**:
- **CID**: Content Identifier (SHA-256 hash)
- **Blob**: Raw file content
- **Tree**: Directory structure
- **Commit**: Version snapshot with parent references
- **MerkleDAG**: Storage backend using filesystem

### 4. crdt/ - Conflict-free Replicated Data Type

**Purpose**: Manage authorized collaborators

| File | Description |
|------|-------------|
| `lww_set.py` | LWWElement, LWWSet, CRDTState, CRDTManager |

**Key Classes**:
- **LWWElement**: Element with timestamp and operation (add/remove)
- **LWWSet**: Last-Writer-Wins Set - latest timestamp wins
- **CRDTState**: Repository authorization state
- **CRDTManager**: Manages CRDT states for multiple repos

### 5. security/ - Security

**Purpose**: Cryptography, SMPP, and user management

| File | Description |
|------|-------------|
| `crypto.py` | KeyPair, SignedData, Hasher |
| `smpp.py` | SMPPRecord, SMPPValidator, SMPPStore |
| `user.py` | User, UserManager, create_demo_users |

**Key Classes**:
- **KeyPair**: Generates keypairs, signs/verifies messages
- **SMPPRecord**: Signed Merkle Pointer record structure
- **SMPPValidator**: Validates SMPP records (4-step validation)
- **User**: User with username, ID, and keypair
- **UserManager**: Manages users and sessions

### 6. api/ - Server

**Purpose**: HTTP API for frontend

| File | Description |
|------|-------------|
| `server.py` | FastAPI app with all endpoints |
| `repo.py` | Repository and NodeAPI classes |

**Key Endpoints**:
- Users: `/users/login`, `/users/me`, `/users`
- Repos: `/repos`, `/repos/{id}`, `/repos/{id}/collaborators`
- Commits: `/repos/{id}/commits`
- Peers: `/peers`, `/repos/{id}/sync`

### 7. cli/ - Command Line

**Purpose**: Terminal interface

| File | Description |
|------|-------------|
| `main.py` | CLI commands: init, commit, log, cat |

**Commands**:
```bash
python -m backend.cli.main init <repo_id>
python -m backend.cli.main commit <repo_id> -m "message" -f file1 file2
python -m backend.cli.main log <repo_id>
python -m backend.cli.main cat <repo_id> <commit_cid> 
```

## Running the Backend

```bash
# Install dependencies
pip install fastapi uvicorn

# Run server
python -m backend.api.server

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## Data Flow

1. **Request** comes to FastAPI endpoint
2. **ServerState** manages users, repos, CRDT
3. **RepoState** stores commits and CRDT state
4. **SMPP validation** checks signature + authorization
5. **Response** returned with status

## API Response Format

### Success
```json
{
  "status": "accepted",
  "cid": "...",
  "message": "...",
  "smpp_valid": true,
  "validation_step": "all"
}
```

### Rejection
```json
{
  "status": "rejected",
  "reason": "Not authorized",
  "smpp_valid": false,
  "validation_step": "authorization"
}
```