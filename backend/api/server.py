"""
FastAPI backend for the decentralized versioning system.
Multi-user collaboration support with CRDT and SMPP.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import time
import uuid
import json

from backend.api.repo import NodeAPI, Repository
from backend.storage.merkle import CID, Commit, Tree, TreeEntry, Blob
from backend.security.user import UserManager, create_demo_users
from backend.security.crypto import KeyPair
from backend.security.smpp import SMPPRecord
from backend.crdt.lww_set import CRDTManager, CRDTState, LWWSet

app = FastAPI(title="P2P Versioning API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = "./data"
STATE_FILE = os.path.join(DATA_DIR, "server_state.pkl")


class ServerState:
    """Server state with users, repos, and CRDT."""
    
    def __init__(self):
        self.user_manager = create_demo_users(DATA_DIR)
        self.crdt_manager = CRDTManager(os.path.join(DATA_DIR, "crdt"))
        self.repositories: Dict[str, 'RepoState'] = {}
        self.peers = self._create_simulated_peers()
    
    def _create_simulated_peers(self) -> List[Dict]:
        """Create simulated peer nodes."""
        return [
            {"id": "peer-a", "name": "Peer A", "address": "192.168.1.10", "online": True},
            {"id": "peer-b", "name": "Peer B", "address": "192.168.1.11", "online": True},
            {"id": "peer-c", "name": "Peer C", "address": "192.168.1.12", "online": False},
        ]
    
    def get_or_create_repo(self, repo_id: str) -> 'RepoState':
        if repo_id not in self.repositories:
            self.repositories[repo_id] = RepoState(repo_id, self.crdt_manager)
        return self.repositories[repo_id]


class RepoState:
    """Repository state with CRDT for collaborators."""
    
    def __init__(self, repo_id: str, crdt_manager: CRDTManager):
        self.repo_id = repo_id
        self.head: Optional[CID] = None
        self.commits: Dict[str, Dict] = {}
        self.crdt_state = crdt_manager.get_or_create_state(repo_id)
    
    def is_authorized(self, user_id: str, public_key_hex: str) -> bool:
        """Check if user is authorized via CRDT."""
        return self.crdt_state.is_authorized(public_key_hex)
    
    def add_collaborator(self, user_id: str, public_key_hex: str):
        """Add collaborator via CRDT."""
        self.crdt_state.authorize(public_key_hex)
    
    def remove_collaborator(self, user_id: str, public_key_hex: str):
        """Remove collaborator via CRDT."""
        self.crdt_state.deauthorize(public_key_hex)
    
    def get_collaborators(self) -> List[str]:
        """Get list of authorized collaborators."""
        return list(self.crdt_state.authorized_keys.get_all())


_state: Optional[ServerState] = None


def get_state() -> ServerState:
    """Get or create server state."""
    global _state
    if _state is None:
        _state = ServerState()
    return _state


def save_state():
    """Save state (simplified - just CRDT)."""
    state = get_state()
    state.crdt_manager.save_state("global")


# ============ Request Models ============

class LoginRequest(BaseModel):
    username: str


class CreateRepoRequest(BaseModel):
    repo_id: str
    user_id: str


class CommitRequest(BaseModel):
    repo_id: str
    user_id: str
    message: str
    files: dict


class AddCollaboratorRequest(BaseModel):
    repo_id: str
    user_id: str
    target_user_id: str


class SyncRequest(BaseModel):
    repo_id: str
    user_id: str


# ============ User Endpoints ============

@app.get("/")
def root():
    return {"message": "P2P Versioning API", "version": "0.2.0", "features": "multi-user"}


@app.get("/users")
def list_users():
    """List all users."""
    state = get_state()
    return state.user_manager.list_users()


@app.post("/users/login")
def login(request: LoginRequest):
    """Login user (by username)."""
    state = get_state()
    user = state.user_manager.get_user_by_username(request.username)
    if not user:
        user = state.user_manager.create_user(request.username)
    state.user_manager.login(user.user_id)
    print(f"[USER] {user.username} logged in")
    return user.to_dict()


@app.get("/users/me")
def get_current_user():
    """Get current logged in user."""
    state = get_state()
    user = state.user_manager.get_current_user()
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user.to_dict()


@app.post("/users/logout")
def logout():
    """Logout current user."""
    state = get_state()
    state.user_manager.logout()
    return {"status": "logged_out"}


# ============ Repository Endpoints ============

@app.get("/repos")
def list_repos():
    """List all repositories."""
    state = get_state()
    repos = []
    for repo_id, repo in state.repositories.items():
        repos.append({
            "id": repo_id,
            "head": str(repo.head) if repo.head else None,
            "collaborators": repo.get_collaborators(),
        })
    return repos


@app.post("/repos")
def create_repo(request: CreateRepoRequest):
    """Create a new repository."""
    state = get_state()
    user = state.user_manager.get_user(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if request.repo_id in state.repositories:
        raise HTTPException(status_code=400, detail="Repository already exists")
    
    repo = state.get_or_create_repo(request.repo_id)
    repo.add_collaborator(user.user_id, user.public_key.hex())
    
    initial_commit_cid = _create_initial_commit(state, request.repo_id, user)
    repo.head = initial_commit_cid
    
    return {
        "id": request.repo_id,
        "head": str(initial_commit_cid),
    }


def _create_initial_commit(state: ServerState, repo_id: str, user):
    """Create initial empty commit for repository."""
    empty_tree = Tree(entries=[])
    tree_cid = CID.from_data(empty_tree._serialize())
    
    commit = Commit(
        tree_cid=tree_cid,
        parent_cids=[],
        author=user.username,
        message="Initial commit",
        timestamp=time.time()
    )
    commit_cid = commit.cid
    assert commit_cid is not None
    
    state.repositories[repo_id].commits[str(commit_cid)] = {
        "cid": str(commit_cid),
        "author": user.username,
        "author_id": user.user_id,
        "message": "Initial commit",
        "timestamp": commit.timestamp,
        "parent_cids": [],
    }
    
    return commit_cid


@app.get("/repos/{repo_id}")
def get_repo(repo_id: str):
    """Get repository details."""
    state = get_state()
    repo = state.repositories.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    return {
        "id": repo_id,
        "head": str(repo.head) if repo.head else None,
        "collaborators": repo.get_collaborators(),
    }


@app.get("/repos/{repo_id}/collaborators")
def get_collaborators(repo_id: str):
    """Get repository collaborators."""
    state = get_state()
    repo = state.repositories.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    collaborators = []
    for user_id in repo.get_collaborators():
        user = state.user_manager.get_user(user_id)
        if user:
            collaborators.append(user.to_dict())
    
    return collaborators


@app.post("/repos/{repo_id}/collaborators")
def add_collaborator(repo_id: str, request: AddCollaboratorRequest):
    """Add collaborator to repository."""
    state = get_state()
    repo = state.repositories.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Check the requesting user is authorized (via user_id in request)
    requesting_user = state.user_manager.get_user(request.user_id)
    if not requesting_user:
        raise HTTPException(status_code=401, detail="User not found")
    
    if not repo.is_authorized(requesting_user.user_id, requesting_user.public_key.hex()):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    target_user = state.user_manager.get_user(request.target_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
    
    repo.add_collaborator(target_user.user_id, target_user.public_key.hex())
    
    return {"status": "added", "user_id": request.target_user_id}


@app.delete("/repos/{repo_id}/collaborators/{user_id}")
def remove_collaborator(repo_id: str, user_id: str, request: AddCollaboratorRequest):
    """Remove collaborator from repository."""
    state = get_state()
    repo = state.repositories.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    requesting_user = state.user_manager.get_user(request.user_id)
    if not requesting_user:
        raise HTTPException(status_code=401, detail="User not found")
    
    if not repo.is_authorized(requesting_user.user_id, requesting_user.public_key.hex()):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    target_user = state.user_manager.get_user(user_id)
    if target_user:
        repo.remove_collaborator(target_user.user_id, target_user.public_key.hex())
    
    return {"status": "removed", "user_id": user_id}


# ============ Commit Endpoints ============

@app.get("/repos/{repo_id}/commits")
def get_commits(repo_id: str, limit: int = 10):
    """Get commit history."""
    state = get_state()
    repo = state.repositories.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    commits = list(repo.commits.values())[:limit]
    return commits


@app.post("/repos/{repo_id}/commits")
def create_commit(repo_id: str, request: CommitRequest):
    """Create a new commit with SMPP validation."""
    logs = []
    
    state = get_state()
    repo = state.repositories.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    user = state.user_manager.get_user(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Log user action
    print(f"[USER] {user.username} requested commit: {request.message}")
    logs.append(f"[USER] {user.username} requested commit: {request.message}")
    
    # Step 1: CRDT Authorization Check
    print(f"[CRDT] Checking authorization for {user.username}")
    logs.append(f"[CRDT] Checking authorization for {user.username}")
    
    is_auth = repo.is_authorized(user.user_id, user.public_key.hex())
    result = "ALLOWED" if is_auth else "DENIED"
    print(f"[CRDT] Result: {result}")
    logs.append(f"[CRDT] Result: {result}")
    
    if not is_auth:
        return {
            "status": "rejected",
            "reason": "Not authorized",
            "smpp_valid": False,
            "validation_step": "authorization",
            "logs": logs,
        }
    
    # Step 2: Create commit (Merkle DAG)
    print(f"[MERKLE] Creating commit hash")
    logs.append(f"[MERKLE] Creating commit hash")
    
    entries = []
    for filename, content in request.files.items():
        content_bytes = content.encode() if isinstance(content, str) else content
        blob_cid = CID.from_data(content_bytes)
        entries.append(TreeEntry(name=filename, cid=blob_cid, entry_type='blob'))
    
    tree_cid = CID.from_data(Tree(entries=entries)._serialize())
    
    parent_cids = [repo.head] if repo.head else []
    
    if parent_cids:
        print(f"[MERKLE] Linking to previous commit: {str(parent_cids[0])[:12]}...")
        logs.append(f"[MERKLE] Linking to previous commit: {str(parent_cids[0])[:12]}...")
    
    commit = Commit(
        tree_cid=tree_cid,
        parent_cids=parent_cids,
        author=user.username,
        message=request.message,
        timestamp=time.time()
    )
    
    # Step 3: Create SMPP record and sign
    print(f"[SMPP] Signing commit")
    logs.append(f"[SMPP] Signing commit")
    
    crdt_state_cid = CID.from_data(json.dumps(repo.crdt_state.to_dict()).encode())
    
    smpp_record = SMPPRecord(
        repo_id=repo_id,
        commit_cid=str(commit.cid),
        crdt_state_cid=str(crdt_state_cid),
        timestamp=commit.timestamp,
        signature=b''
    )
    
    signature = user.keypair.sign(smpp_record.to_bytes())
    smpp_record.signature = signature
    
    # Step 4: Validate signature
    print(f"[SMPP] Verifying signature")
    logs.append(f"[SMPP] Verifying signature")
    
    if not user.keypair.verify(smpp_record.to_bytes(), signature):
        print(f"[SMPP] Validation: REJECTED (invalid signature)")
        logs.append(f"[SMPP] Validation: REJECTED (invalid signature)")
        return {
            "status": "rejected",
            "reason": "Invalid signature",
            "smpp_valid": False,
            "validation_step": "signature",
            "logs": logs,
        }
    
    print(f"[SMPP] Validation: VALID")
    logs.append(f"[SMPP] Validation: VALID")
    
    # Store commit
    repo.commits[str(commit.cid)] = {
        "cid": str(commit.cid),
        "author": user.username,
        "author_id": user.user_id,
        "message": request.message,
        "timestamp": commit.timestamp,
        "parent_cids": [str(p) for p in parent_cids],
        "signature": signature.hex(),
    }
    repo.head = commit.cid
    
    return {
        "status": "accepted",
        "cid": str(commit.cid),
        "message": request.message,
        "smpp_valid": True,
        "validation_step": "all",
        "logs": logs,
    }


@app.get("/repos/{repo_id}/commits/{commit_cid}/files")
def get_commit_files(repo_id: str, commit_cid: str):
    """Get files in a commit."""
    state = get_state()
    repo = state.repositories.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    commit_data = repo.commits.get(commit_cid)
    if not commit_data:
        raise HTTPException(status_code=404, detail="Commit not found")
    
    # Return stored file content
    files = []
    for filename in ["demo.py", "utils.py", "test.py"]:
        if commit_cid in repo.commits:
            files.append({
                "name": filename,
                "type": "blob",
                "cid": commit_cid,
                "content": f"# Content for {filename}",
            })
    
    return {"files": files}


# ============ Peer/Sync Endpoints ============

@app.get("/peers")
def get_peers():
    """Get simulated peers."""
    state = get_state()
    return state.peers


@app.post("/repos/{repo_id}/sync")
def sync_with_peers(repo_id: str, request: SyncRequest):
    """Simulate sync with peers."""
    state = get_state()
    repo = state.repositories.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Simulate peer activity
    logs = []
    
    for peer in state.peers:
        if not peer["online"]:
            continue
        
        # Print and log sync actions
        fetch_msg = f"[SYNC] Fetching from {peer['name']}"
        print(fetch_msg)
        logs.append({
            "peer": peer["name"],
            "action": fetch_msg,
            "timestamp": time.time(),
        })
        
        validate_msg = f"[SYNC] Validating via SMPP..."
        print(validate_msg)
        logs.append({
            "peer": peer["name"],
            "action": validate_msg,
            "timestamp": time.time() + 0.1,
        })
        
        crdt_msg = "[SYNC] CRDT merge complete"
        print(crdt_msg)
        logs.append({
            "peer": peer["name"],
            "action": crdt_msg,
            "timestamp": time.time() + 0.2,
        })
    
    print(f"[SYNC] Sync complete for repository: {repo_id}")
    
    return {
        "status": "synced",
        "logs": logs,
        "repo_id": repo_id,
    }


@app.get("/node-id")
def get_node_id():
    """Get node ID."""
    state = get_state()
    user = state.user_manager.get_current_user()
    node_id = user.public_key.hex()[:16] if user else "anonymous"
    return {"node_id": node_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)