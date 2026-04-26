"""
CRDT implementation - Last-Writer-Wins (LWW) Set for authorization.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Optional, List
from enum import Enum
import time
import hashlib


class OperationType(Enum):
    ADD = 0x01
    REMOVE = 0x02


@dataclass
class LWWElement:
    """LWW Element with timestamp and value."""
    value: str
    timestamp: float
    operation: OperationType

    @classmethod
    def add(cls, value: str, timestamp: Optional[float] = None) -> 'LWWElement':
        return cls(value=value, timestamp=timestamp or time.time(), operation=OperationType.ADD)

    @classmethod
    def remove(cls, value: str, timestamp: Optional[float] = None) -> 'LWWElement':
        return cls(value=value, timestamp=timestamp or time.time(), operation=OperationType.REMOVE)


class LWWSet:
    """Last-Writer-Wins Set CRDT."""

    def __init__(self):
        self.elements: Dict[str, LWWElement] = {}
        self.add_set: Dict[str, float] = {}
        self.remove_set: Dict[str, float] = {}

    def add(self, value: str, timestamp: Optional[float] = None) -> None:
        """Add element to set."""
        ts = timestamp or time.time()
        if value not in self.add_set or ts > self.add_set[value]:
            self.add_set[value] = ts
            self.elements[value] = LWWElement.add(value, ts)

    def remove(self, value: str, timestamp: Optional[float] = None) -> None:
        """Remove element from set."""
        ts = timestamp or time.time()
        if value in self.add_set and ts >= self.add_set[value]:
            if value not in self.remove_set or ts > self.remove_set[value]:
                self.remove_set[value] = ts
                self.elements[value] = LWWElement.remove(value, ts)

    def contains(self, value: str) -> bool:
        """Check if value is in set."""
        if value not in self.add_set:
            return False
        if value in self.remove_set:
            return self.add_set[value] > self.remove_set[value]
        return True

    def merge(self, other: 'LWWSet') -> None:
        """Merge another LWWSet into this one."""
        for value, ts in other.add_set.items():
            self.add(value, ts)
        for value, ts in other.remove_set.items():
            self.remove(value, ts)

    def get_all(self) -> Set[str]:
        """Get all elements in set."""
        return {v for v in self.add_set if self.contains(v)}

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'add_set': self.add_set,
            'remove_set': self.remove_set
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'LWWSet':
        """Deserialize from dictionary."""
        set_obj = cls()
        set_obj.add_set = data.get('add_set', {})
        set_obj.remove_set = data.get('remove_set', {})
        return set_obj


@dataclass
class CRDTState:
    """CRDT state container for authorization."""
    authorized_keys: LWWSet
    repository_id: str

    def is_authorized(self, key: str) -> bool:
        """Check if key is authorized."""
        return self.authorized_keys.contains(key)

    def authorize(self, key: str) -> None:
        """Authorize a key."""
        self.authorized_keys.add(key)

    def deauthorize(self, key: str) -> None:
        """Remove authorization."""
        self.authorized_keys.remove(key)

    def merge(self, other: 'CRDTState') -> None:
        """Merge another CRDT state."""
        if self.repository_id == other.repository_id:
            self.authorized_keys.merge(other.authorized_keys)

    def to_dict(self) -> dict:
        """Serialize state."""
        return {
            'repository_id': self.repository_id,
            'authorized_keys': self.authorized_keys.to_dict()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CRDTState':
        """Deserialize state."""
        state = cls(
            repository_id=data['repository_id'],
            authorized_keys=LWWSet.from_dict(data.get('authorized_keys', {}))
        )
        return state


class CRDTManager:
    """Manages CRDT states for multiple repositories."""

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.states: Dict[str, CRDTState] = {}

    def get_or_create_state(self, repo_id: str) -> CRDTState:
        """Get or create CRDT state for repository."""
        if repo_id not in self.states:
            self.states[repo_id] = CRDTState(
                repository_id=repo_id,
                authorized_keys=LWWSet()
            )
        return self.states[repo_id]

    def merge_state(self, repo_id: str, other_state: CRDTState) -> None:
        """Merge external state."""
        local_state = self.get_or_create_state(repo_id)
        local_state.merge(other_state)

    def save_state(self, repo_id: str) -> None:
        """Save CRDT state to disk."""
        import json
        import os
        state = self.states.get(repo_id)
        if state:
            path = os.path.join(self.storage_path, f"{repo_id}_crdt.json")
            with open(path, 'w') as f:
                json.dump(state.to_dict(), f)

    def load_state(self, repo_id: str) -> Optional[CRDTState]:
        """Load CRDT state from disk."""
        import json
        import os
        path = os.path.join(self.storage_path, f"{repo_id}_crdt.json")
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                return CRDTState.from_dict(data)
        return None