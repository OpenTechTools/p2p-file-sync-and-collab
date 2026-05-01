# CRDT Module

## Overview

The `backend/crdt/` package implements **Conflict-free Replicated Data Types (CRDTs)** for managing decentralized authorization in a peer-to-peer version control system. Specifically, it provides a **Last-Writer-Wins Set (LWW-Set)** CRDT used to track which public keys are authorized to perform operations (like commits) on a repository.

In a distributed system where multiple nodes can independently grant or revoke access, CRDTs guarantee that all nodes will eventually converge to the same state without requiring a central coordinator or consensus protocol.

---

## Architecture

```
backend/crdt/
├── __init__.py      # Package exports
└── lww_set.py       # Core CRDT implementation
    ├── OperationType  # Enum: ADD / REMOVE
    ├── LWWElement     # Dataclass: value + timestamp + operation
    ├── LWWSet         # The core LWW-Set CRDT
    ├── CRDTState      # Repository-scoped authorization state
    └── CRDTManager    # Multi-repository state manager with disk persistence
```

---

## CRDT Type: LWW-Set (Last-Writer-Wins Set)

### What is an LWW-Set?

An LWW-Set is a grow-shrink set CRDT that resolves conflicts using timestamps. Each element carries a logical timestamp, and when two replicas disagree about whether an element is present, the operation with the **latest timestamp wins**.

### Internal Structure

The `LWWSet` class uses a **two-phase tombstone-based approach**:

| Field | Type | Purpose |
|-------|------|---------|
| `add_set` | `Dict[str, float]` | Maps each value to the timestamp of its most recent ADD |
| `remove_set` | `Dict[str, float]` | Maps each value to the timestamp of its most recent REMOVE |
| `elements` | `Dict[str, LWWElement]` | Convenience map of value to full `LWWElement` object |

The authoritative state is determined by `add_set` and `remove_set` -- the `elements` dict is a secondary cache.

### Determining Membership

An element is considered **present** in the set if:

1. It exists in `add_set`, AND
2. It does NOT exist in `remove_set`, **OR** its add timestamp is **strictly greater** than its remove timestamp

This means an element can be re-added after removal if the new add has a later timestamp.

### Operations

#### `add(value, timestamp=None)`

Adds an element to the set. The update is only applied if:
- The value has never been added, OR
- The new timestamp is **strictly greater** than the existing add timestamp

If no timestamp is provided, `time.time()` is used.

#### `remove(value, timestamp=None)`

Removes an element from the set. The update is only applied if:
- The value was previously added (`value in add_set`), AND
- The new timestamp is **greater than or equal to** the add timestamp, AND
- The new timestamp is **strictly greater** than any existing remove timestamp

This prevents removing an element that was never added, and ensures removes cannot retroactively undo later adds.

#### `contains(value) -> bool`

Returns whether a value is currently present in the set according to the LWW membership rules.

#### `merge(other: LWWSet)`

Merges another LWW-Set into this one by **replaying** all operations from the remote set:
1. For each entry in `other.add_set`, call `self.add(value, timestamp)`
2. For each entry in `other.remove_set`, call `self.remove(value, timestamp)`

The individual `add`/`remove` methods enforce LWW semantics, so merging is **commutative**, **associative**, and **idempotent** -- the three mathematical properties required for a CRDT.

#### `get_all() -> Set[str]`

Returns all currently "alive" elements by filtering `add_set` through the `contains()` logic.

### Serialization

- `to_dict()` -- Produces `{'add_set': {...}, 'remove_set': {...}}`
- `from_dict(data)` -- Reconstructs an LWWSet from the dictionary format

The serialized form only includes `add_set` and `remove_set` (timestamps), not the full `LWWElement` objects.

---

## CRDTState

`CRDTState` is a **repository-scoped** authorization container that wraps an `LWWSet` of authorized public keys.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `authorized_keys` | `LWWSet` | The set of authorized public key hex strings |
| `repository_id` | `str` | Identifier for the repository this state belongs to |

### Operations

| Method | Description |
|--------|-------------|
| `is_authorized(key)` | Checks if a public key is in the authorized set |
| `authorize(key)` | Adds a public key to the authorized set |
| `deauthorize(key)` | Removes a public key from the authorized set |
| `merge(other)` | Merges another CRDTState -- **only if** both have the same `repository_id` |
| `to_dict()` / `from_dict()` | JSON serialization and deserialization |

### Merge Guard

`CRDTState.merge()` enforces that `self.repository_id == other.repository_id` before merging. This prevents accidental cross-repository contamination where keys from one repository could leak into another.

---

## CRDTManager

`CRDTManager` handles **multi-repository** CRDT state management with **disk persistence**.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `storage_path` | `str` | Directory path for on-disk JSON state files |
| `states` | `Dict[str, CRDTState]` | In-memory cache of all active repository states |

### Operations

| Method | Description |
|--------|-------------|
| `get_or_create_state(repo_id)` | Returns existing state for a repo, or creates a new empty one |
| `merge_state(repo_id, other_state)` | Merges an external state into the local state for a given repo |
| `save_state(repo_id)` | Writes state to `{storage_path}/{repo_id}_crdt.json` |
| `load_state(repo_id)` | Reads state from disk; returns `None` if file doesn't exist |

### Persistence Format

Each repository's state is stored as a JSON file:

```json
{
  "repository_id": "abc123",
  "authorized_keys": {
    "add_set": {
      "a1b2c3d4...": 1714500000.123,
      "e5f6g7h8...": 1714500001.456
    },
    "remove_set": {
      "a1b2c3d4...": 1714500002.789
    }
  }
}
```

---

## Conflict Resolution Strategy

### Last-Writer-Wins by Timestamp

When two replicas independently modify the same element:
- The operation with the **latest timestamp** takes precedence
- Adds use **strictly greater** (`>`) comparison
- Removes use **greater than or equal** (`>=`) against add timestamps and **strictly greater** (`>`) against existing remove timestamps

### Timestamp Comparison Rules

| Scenario | Outcome |
|----------|---------|
| Add at t=10, Add at t=5 | t=10 wins (t=5 is stale, ignored) |
| Add at t=10, Remove at t=15 | Remove wins (element absent) |
| Add at t=10, Remove at t=8 | Add wins (element present) |
| Add at t=10, Remove at t=10 | Remove wins (remove uses `>=` against add) |
| Remove at t=10, Add at t=15 | Add wins (element re-added, present) |

### CRDT Properties

The LWW-Set implementation satisfies the three CRDT convergence properties:

1. **Commutativity**: `A.merge(B) == B.merge(A)` -- order of merges doesn't matter
2. **Associativity**: `(A.merge(B)).merge(C) == A.merge(B.merge(C))` -- grouping doesn't matter
3. **Idempotency**: `A.merge(A) == A` -- merging the same state twice has no additional effect

---

## Integration with the Backend

### 1. API Server (`backend/api/server.py`)

- Creates a global `CRDTManager` at `./data/crdt`
- `RepoState` wraps a `CRDTState` from the manager
- Collaborator management flows through CRDT:
  - `add_collaborator()` --> `crdt_state.authorize(public_key_hex)`
  - `remove_collaborator()` --> `crdt_state.deauthorize(public_key_hex)`
  - `is_authorized()` --> `crdt_state.is_authorized(public_key_hex)`
  - `get_collaborators()` --> `crdt_state.authorized_keys.get_all()`
- Before creating a commit, the server checks CRDT authorization as Step 1 of a 5-step pipeline
- The CRDT state is serialized, stored as a blob, and its CID is embedded into the SMPP record

### 2. Repository/Node API (`backend/api/repo.py`)

- `Repository.__init__()` auto-authorizes the owner's public key upon repository creation
- `Repository.commit()` stores the CRDT state as a blob and includes its CID in the SMPP record
- `NodeAPI.__init__()` creates a `CRDTManager` at `{data_dir}/crdt`

### 3. SMPP Validator (`backend/security/smpp.py`)

- `SMPPValidator._fetch_crdt_state()` deserializes a `CRDTState` from the object store by CID
- `SMPPValidator._check_authorization()` uses `crdt_state.is_authorized(key_hex)` as **Step 3** of the 4-step SMPP validation pipeline:
  1. Verify signature
  2. Fetch CRDT state by CID
  3. **Check authorization via CRDT**
  4. Check timestamp (anti-replay)

---

## Data Flow

```
Owner creates repository
         │
         ▼
CRDTManager.get_or_create_state(repo_id)
         │
         ▼
CRDTState.authorize(owner_public_key)  ← auto-authorized
         │
         ▼
Owner adds collaborator
         │
         ▼
CRDTState.authorize(collaborator_key)
         │
         ▼
Collaborator makes commit
         │
         ▼
Server checks: CRDTState.is_authorized(collaborator_key) ──→ True → proceed
                                                      ──→ False → reject
         │
         ▼
On sync/merge with peer:
CRDTState.merge(peer_state)  ← converges authorization state
```

---

## Dependencies

The CRDT module uses **only Python standard library** modules:

| Module | Usage |
|--------|-------|
| `dataclasses` | `@dataclass` decorators for `LWWElement` and `CRDTState` |
| `typing` | Type hints (`Dict`, `Set`, `Optional`, `List`) |
| `enum` | `Enum` for `OperationType` |
| `time` | `time.time()` for timestamp generation |
| `json` | Serialization in `save_state()` / `load_state()` |
| `os` | Path operations in `save_state()` / `load_state()` |

Note: `hashlib` is imported but unused -- a minor code quality issue.

---

## Limitations and Design Notes

1. **Wall-clock timestamps**: The implementation relies on system clocks, making it vulnerable to clock skew between nodes. There is no vector clock, Lamport clock, or hybrid logical clock for causal ordering.

2. **Purpose-specific**: This is not a general-purpose CRDT library. It is purpose-built for authorization management where values are hex-encoded public key strings.

3. **No auto-save**: State is only persisted when `save_state()` is explicitly called. Mutations do not trigger automatic disk writes.

4. **Lazy loading**: `CRDTManager` does not automatically load states from disk on startup. States are created fresh and must be explicitly loaded via `load_state()`.

5. **Redundant `elements` dict**: The `LWWSet.elements` field stores full `LWWElement` objects but is not used by `contains()` or `get_all()`. The `add_set` and `remove_set` dictionaries are the authoritative source of truth.

6. **No tests**: There are currently no unit tests or integration tests for the CRDT module.

---

## Public API Summary

```python
from backend.crdt import LWWSet, LWWElement, CRDTState, CRDTManager, OperationType

# Create and manage states
manager = CRDTManager(storage_path="./data/crdt")
state = manager.get_or_create_state("repo-123")

# Authorization operations
state.authorize("public_key_hex_1")
state.authorize("public_key_hex_2")
state.is_authorized("public_key_hex_1")   # True
state.deauthorize("public_key_hex_2")
state.is_authorized("public_key_hex_2")   # False

# Get all authorized keys
state.authorized_keys.get_all()

# Merge with peer state
state.merge(peer_state)

# Persist to disk
manager.save_state("repo-123")

# Load from disk
loaded_state = manager.load_state("repo-123")
```
