"""
Object store for managing Merkle DAG objects.
"""

import time
from typing import Optional, List, Dict
from .merkle import CID, Blob, Tree, Commit, MerkleDAG, TreeEntry


class ObjectStore:
    """High-level object storage interface."""

    def __init__(self, dag: MerkleDAG):
        self.dag = dag

    def store_blob(self, data: bytes) -> CID:
        """Store blob and return CID."""
        blob = Blob(data=data)
        self.dag.put(blob)
        assert blob.cid is not None
        return blob.cid

    def store_tree(self, entries: List[TreeEntry]) -> CID:
        """Store tree and return CID."""
        tree = Tree(entries=entries)
        self.dag.put(tree)
        assert tree.cid is not None
        return tree.cid

    def store_commit(self, tree_cid: CID, parent_cids: List[CID], author: str, message: str) -> CID:
        """Store commit and return CID."""
        commit = Commit(tree_cid=tree_cid, parent_cids=parent_cids, author=author, message=message, timestamp=time.time())
        self.dag.put(commit)
        assert commit.cid is not None
        return commit.cid

    def get_blob(self, cid: CID) -> Optional[Blob]:
        """Retrieve blob."""
        obj = self.dag.get(cid)
        return obj if isinstance(obj, Blob) else None

    def get_tree(self, cid: CID) -> Optional[Tree]:
        """Retrieve tree."""
        obj = self.dag.get(cid)
        return obj if isinstance(obj, Tree) else None

    def get_commit(self, cid: CID) -> Optional[Commit]:
        """Retrieve commit."""
        obj = self.dag.get(cid)
        return obj if isinstance(obj, Commit) else None

    def has_object(self, cid: CID) -> bool:
        """Check if object exists."""
        return self.dag.has(cid)

    def list_objects(self) -> List[CID]:
        """List all stored objects."""
        import os
        cids = []
        for f in os.listdir(self.dag.storage_path):
            if len(f) == 64:
                cids.append(CID.from_hex(f))
        return cids