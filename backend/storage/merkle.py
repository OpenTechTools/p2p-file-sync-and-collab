"""
Merkle DAG storage for content-addressable versioning.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set
import hashlib
import os


@dataclass
class CID:
    """Content Identifier - SHA-256 based."""
    digest: bytes

    @classmethod
    def from_data(cls, data: bytes) -> 'CID':
        return cls(digest=hashlib.sha256(data).digest())

    @classmethod
    def from_hex(cls, hex_str: str) -> 'CID':
        return cls(digest=bytes.fromhex(hex_str))

    def __str__(self) -> str:
        return self.digest.hex()

    def __repr__(self) -> str:
        return f"CID({self})"


@dataclass
class Blob:
    """File content object (chunked at 256KB)."""
    data: bytes
    cid: Optional[CID] = None

    def __post_init__(self):
        if self.cid is None:
            self.cid = CID.from_data(self.data)


@dataclass
class TreeEntry:
    """Single entry in a tree node."""
    name: str
    cid: CID
    entry_type: str  # 'blob' or 'tree'


@dataclass
class Tree:
    """Merkle tree node - directory structure."""
    entries: List[TreeEntry]
    cid: Optional[CID] = None

    def __post_init__(self):
        if self.cid is None:
            serialized = self._serialize()
            self.cid = CID.from_data(serialized)

    def _serialize(self) -> bytes:
        parts = []
        for e in sorted(self.entries, key=lambda x: x.name):
            parts.append(f"{e.name}:{e.entry_type}:{e.cid}".encode())
        return b'\n'.join(parts)

    @classmethod
    def _deserialize(cls, data: bytes, cid: CID) -> 'Tree':
        entries = []
        for line in data.split(b'\n'):
            if line:
                name, etype, cid_str = line.decode().split(':')
                entries.append(TreeEntry(name=name, cid=CID.from_hex(cid_str), entry_type=etype))
        return cls(entries=entries, cid=cid)


@dataclass
class Commit:
    """Version snapshot."""
    tree_cid: CID
    parent_cids: List[CID]
    author: str
    message: str
    timestamp: float
    cid: Optional[CID] = None

    def __post_init__(self):
        if self.cid is None:
            serialized = self._serialize()
            self.cid = CID.from_data(serialized)

    def _serialize(self) -> bytes:
        parent_str = ','.join(str(p) for p in self.parent_cids)
        data = f"{self.tree_cid}|{parent_str}|{self.author}|{self.message}|{self.timestamp}"
        return data.encode()

    @classmethod
    def _deserialize(cls, data: bytes, cid: CID) -> 'Commit':
        parts = data.decode().split('|')
        tree_cid = CID.from_hex(parts[0])
        parent_cids = [CID.from_hex(p) for p in parts[1].split(',')] if parts[1] else []
        return cls(tree_cid=tree_cid, parent_cids=parent_cids, author=parts[2], message=parts[3], timestamp=float(parts[4]), cid=cid)


class MerkleDAG:
    """Merkle DAG for object storage and retrieval."""

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)

    def _object_path(self, cid: CID) -> str:
        return os.path.join(self.storage_path, str(cid))

    def put(self, obj: "Blob | Tree | Commit") -> CID:
        """Store object and return CID."""
        assert obj.cid is not None, "Object must have a CID"
        path = self._object_path(obj.cid)
        with open(path, 'wb') as f:
            if isinstance(obj, Blob):
                f.write(b'BLOB:' + obj.data)
            elif isinstance(obj, Tree):
                f.write(b'TREE:' + obj._serialize())
            elif isinstance(obj, Commit):
                f.write(b'COMMIT:' + obj._serialize())
        return obj.cid

    def get(self, cid: CID) -> Optional["Blob | Tree | Commit"]:
        """Retrieve object by CID."""
        path = self._object_path(cid)
        if not os.path.exists(path):
            return None
        with open(path, 'rb') as f:
            data = f.read()
        obj_type, content = data.split(b':', 1)
        if obj_type == b'BLOB':
            return Blob(data=content, cid=cid)
        elif obj_type == b'TREE':
            return Tree._deserialize(content, cid)
        elif obj_type == b'COMMIT':
            return Commit._deserialize(content, cid)
        return None

    def has(self, cid: CID) -> bool:
        """Check if object exists."""
        return os.path.exists(self._object_path(cid))


def create_blob(data: bytes) -> Blob:
    """Factory function for creating blobs."""
    return Blob(data=data)


def create_tree(entries: List[TreeEntry]) -> Tree:
    """Factory function for creating trees."""
    return Tree(entries=entries)


def create_commit(tree_cid: CID, parent_cids: List[CID], author: str, message: str, timestamp: float = 0) -> Commit:
    """Factory function for creating commits."""
    import time
    return Commit(tree_cid=tree_cid, parent_cids=parent_cids, author=author, message=message, timestamp=timestamp or time.time())