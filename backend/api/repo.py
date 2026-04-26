"""
Repository API for decentralized versioning.
"""

from typing import Optional, List, Dict
import time
import hashlib

from ..network.dht import DHTNode, NodeID, Peer
from ..transport.rudp import RUDPProtocol
from ..storage.merkle import CID, MerkleDAG, Blob, Tree, TreeEntry, Commit
from ..storage.store import ObjectStore
from ..crdt.lww_set import CRDTManager, CRDTState
from ..security.crypto import KeyPair
from ..security.smpp import SMPPRecord, SMPPValidator, SMPPStore


class Repository:
    """Main repository interface for decentralized versioning."""

    def __init__(
        self,
        repo_id: str,
        node: DHTNode,
        object_store: ObjectStore,
        crdt_manager: CRDTManager,
        smpp_store: SMPPStore,
        key_pair: KeyPair
    ):
        self.repo_id = repo_id
        self.node = node
        self.object_store = object_store
        self.crdt_manager = crdt_manager
        self.smpp_store = smpp_store
        self.key_pair = key_pair
        self.head: Optional[CID] = None

        crdt_state = crdt_manager.get_or_create_state(repo_id)
        crdt_state.authorize(key_pair.public_key.hex())

    def init(self) -> CID:
        """Initialize empty repository."""
        empty_tree = Tree(entries=[])
        self.object_store.dag.put(empty_tree)
        assert empty_tree.cid is not None
        initial_commit = Commit(
            tree_cid=empty_tree.cid,
            parent_cids=[],
            author=self.key_pair.public_key.hex()[:8],
            message="Initial commit",
            timestamp=time.time()
        )
        self.object_store.dag.put(initial_commit)
        assert initial_commit.cid is not None
        self.head = initial_commit.cid
        return self.head

    def commit(self, message: str, changed_files: Dict[str, bytes]) -> CID:
        """Create a new commit with file changes."""
        entries = []

        for filename, content in changed_files.items():
            blob_cid = self.object_store.store_blob(content)
            entries.append(TreeEntry(name=filename, cid=blob_cid, entry_type='blob'))

        tree_cid = self.object_store.store_tree(entries)
        assert tree_cid is not None

        parent_cids = [self.head] if self.head else []

        commit = Commit(
            tree_cid=tree_cid,
            parent_cids=parent_cids,
            author=self.key_pair.public_key.hex()[:8],
            message=message,
            timestamp=time.time()
        )
        self.object_store.dag.put(commit)
        assert commit.cid is not None
        self.head = commit.cid

        crdt_state = self.crdt_manager.get_or_create_state(self.repo_id)
        crdt_state_cid = self.object_store.store_blob(str(crdt_state.to_dict()).encode())

        record = SMPPRecord(
            repo_id=self.repo_id,
            commit_cid=str(commit.cid),
            crdt_state_cid=str(crdt_state_cid),
            timestamp=time.time(),
            signature=self.key_pair.sign(
                SMPPRecord(
                    repo_id=self.repo_id,
                    commit_cid=str(commit.cid),
                    crdt_state_cid=str(crdt_state_cid),
                    timestamp=time.time(),
                    signature=b''
                ).to_bytes()
            )
        )
        self.smpp_store.store_record(record)

        return commit.cid

    def get_commit(self, cid: CID) -> Optional[Commit]:
        """Retrieve a commit by CID."""
        return self.object_store.get_commit(cid)

    def get_file(self, commit_cid: CID, filename: str) -> Optional[bytes]:
        """Get file content at specific commit."""
        commit = self.object_store.get_commit(commit_cid)
        if not commit:
            return None

        tree = self.object_store.get_tree(commit.tree_cid)
        if not tree:
            return None

        for entry in tree.entries:
            if entry.name == filename and entry.entry_type == 'blob':
                blob = self.object_store.get_blob(entry.cid)
                return blob.data if blob else None

        return None

    def get_history(self, limit: int = 10) -> List[Commit]:
        """Get commit history."""
        history = []
        current = self.head
        count = 0

        while current and count < limit:
            commit = self.object_store.get_commit(current)
            if commit:
                history.append(commit)
                current = commit.parent_cids[0] if commit.parent_cids else None
                count += 1
            else:
                break

        return history

    def get_head(self) -> Optional[CID]:
        """Get current head commit CID."""
        return self.head


class NodeAPI:
    """High-level API for P2P node operations."""

    def __init__(self, data_dir: str = "./data"):
        import os
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        self.node = DHTNode()
        self.dht = MerkleDAG(os.path.join(data_dir, "objects"))
        self.object_store = ObjectStore(self.dht)
        self.crdt_manager = CRDTManager(os.path.join(data_dir, "crdt"))
        self.smpp_store = SMPPStore(os.path.join(data_dir, "smpp"))
        self.key_pair = KeyPair.generate()
        self.repositories: Dict[str, Repository] = {}

    def create_repository(self, repo_id: str) -> Repository:
        """Create a new repository."""
        repo = Repository(
            repo_id=repo_id,
            node=self.node,
            object_store=self.object_store,
            crdt_manager=self.crdt_manager,
            smpp_store=self.smpp_store,
            key_pair=self.key_pair
        )
        self.repositories[repo_id] = repo
        return repo

    def get_repository(self, repo_id: str) -> Optional[Repository]:
        """Get existing repository."""
        return self.repositories.get(repo_id)

    def join_network(self, bootstrap_nodes: List[tuple]) -> None:
        """Join P2P network via bootstrap nodes."""
        for addr, port in bootstrap_nodes:
            peer = Peer(
                node_id=NodeID.generate(),
                address=addr,
                port=port
            )
            self.node.routing_table.buckets[0].add(peer)

    def start(self) -> None:
        """Start the node."""
        pass

    def stop(self) -> None:
        """Stop the node."""
        pass