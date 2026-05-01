# Storage Module

## Overview

The `backend/storage/` package implements a **content-addressable Merkle DAG** for version control, modeled after Git's object store. It provides the foundational data structures and persistence layer that enable content integrity, deduplication, and tamper-evident history tracking in a decentralized system.

Every piece of data -- files, directory structures, and version snapshots -- is stored as an object whose address is derived from its content via SHA-256 hashing. This means identical content always produces the same identifier, and any modification changes the identifier, making tampering immediately detectable.

---

## Architecture

```
backend/storage/
├── __init__.py          # Package exports
├── merkle.py            # Core Merkle DAG implementation
│   ├── CID              # Content Identifier (SHA-256 wrapper)
│   ├── Blob             # Raw file content object
│   ├── TreeEntry        # Single entry in a tree node
│   ├── Tree             # Merkle tree node (directory structure)
│   ├── Commit           # Version snapshot
│   ├── MerkleDAG        # Filesystem-backed object store
│   └── factory functions (create_blob, create_tree, create_commit)
└── store.py             # High-level object store facade
    └── ObjectStore      # Type-safe API wrapping MerkleDAG
```

---

## Object Model

The storage system follows a **three-tier Git-like hierarchy**:

```
         ┌──────────────────────────────────────┐
         │              Commit                   │
         │  (version snapshot with metadata)     │
         │  tree_cid → Tree                      │
         │  parent_cids → [Commit, ...]          │
         │  author, message, timestamp           │
         └──────────────────┬───────────────────┘
                            │ tree_cid
                            ▼
         ┌──────────────────────────────────────┐
         │               Tree                    │
         │  (directory listing)                  │
         │  entries → [TreeEntry, ...]           │
         └──────────┬──────────────┬────────────┘
                    │              │
          name:cid  │              │ name:cid
                    ▼              ▼
         ┌──────────────┐  ┌──────────────┐
         │    Blob      │  │    Tree      │
         │  (file data) │  │ (subdir)     │
         └──────────────┘  └──────────────┘
```

Each object references its children by **CID** (Content Identifier), forming a directed acyclic graph. Because every CID is a hash of the object's content, the entire graph is **self-verifying**.

---

## merkle.py -- Core Merkle DAG

### CID (Content Identifier)

A wrapper around a SHA-256 digest that serves as the unique address for every stored object.

| Field | Type | Description |
|-------|------|-------------|
| `digest` | `bytes` | 32 bytes -- raw SHA-256 output |

#### Factory Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `from_data` | `(data: bytes) -> CID` | Computes SHA-256 of raw bytes and creates a CID |
| `from_hex` | `(hex_str: str) -> CID` | Decodes a 64-character hex string into a CID |

#### Representation

- `str(cid)` -- Returns the 64-character hex-encoded digest
- `repr(cid)` -- Returns `CID(hex_string)` format

### Blob

Represents raw file content.

| Field | Type | Description |
|-------|------|-------------|
| `data` | `bytes` | The raw file bytes |
| `cid` | `Optional[CID]` | Auto-computed from `data` in `__post_init__` |

When a `Blob` is created without an explicit `cid`, the `__post_init__` hook automatically computes `CID.from_data(self.data)`. This ensures every blob's identifier is deterministically derived from its content.

**Note**: The docstring mentions "chunked at 256KB" but **no chunking is implemented**. Blobs store data as-is regardless of size.

### TreeEntry

A single named reference within a tree node.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Filename or directory name |
| `cid` | `CID` | Content identifier of the referenced object |
| `entry_type` | `str` | Either `'blob'` (file) or `'tree'` (subdirectory) |

### Tree

Represents a directory structure -- a collection of named entries pointing to blobs or nested trees.

| Field | Type | Description |
|-------|------|-------------|
| `entries` | `List[TreeEntry]` | List of directory entries |
| `cid` | `Optional[CID]` | Auto-computed from serialized entries in `__post_init__` |

#### Serialization

Entries are sorted **alphabetically by name**, then serialized as:

```
filename:blob:abc123...
subdir:tree:def456...
```

Each line is `name:entry_type:cid_hex`, joined by newline (`\n`). The resulting bytes are hashed to produce the tree's CID.

```python
def _serialize(self) -> bytes:
    parts = []
    for e in sorted(self.entries, key=lambda x: x.name):
        parts.append(f"{e.name}:{e.entry_type}:{e.cid}".encode())
    return b'\n'.join(parts)
```

#### Deserialization

`Tree._deserialize(data: bytes, cid: CID) -> Tree` splits the data by newlines, parses each line by `:`, and reconstructs `TreeEntry` objects.

### Commit

Represents a version snapshot in the repository history.

| Field | Type | Description |
|-------|------|-------------|
| `tree_cid` | `CID` | Points to the root tree (file state at commit time) |
| `parent_cids` | `List[CID]` | Parent commit CIDs -- 0 for initial, 1 for linear, 2+ for merges |
| `author` | `str` | Author identity string |
| `message` | `str` | Commit message |
| `timestamp` | `float` | Unix timestamp |
| `cid` | `Optional[CID]` | Auto-computed from serialized data in `__post_init__` |

#### Serialization

Commits are serialized as a **pipe-delimited** string:

```
tree_cid|parent_cid1,parent_cid2|author|message|timestamp
```

Parent CIDs are comma-separated (empty string if no parents). The resulting bytes are hashed to produce the commit's CID.

```python
def _serialize(self) -> bytes:
    parent_str = ','.join(str(p) for p in self.parent_cids)
    data = f"{self.tree_cid}|{parent_str}|{self.author}|{self.message}|{self.timestamp}"
    return data.encode()
```

#### Deserialization

`Commit._deserialize(data: bytes, cid: CID) -> Commit` splits by `|` and parses each field. Parent CIDs are split by `,`.

### Merkle Property

The CID of every object is a hash of its content:

- **Blob CID** = `SHA-256(data)`
- **Tree CID** = `SHA-256(serialized_entries)`
- **Commit CID** = `SHA-256(serialized_commit_fields)`

Because trees contain the CIDs of their children, and commits contain the CIDs of their trees and parents, any change to any content **cascades upward** and changes all ancestor CIDs. This provides:

| Property | How It Works |
|----------|-------------|
| **Integrity** | Re-hashing any object's content must match its CID |
| **Deduplication** | Identical content always produces the same CID |
| **Tamper detection** | Any modification changes the hash, breaking the chain |
| **History immutability** | Changing a past commit changes its CID, breaking all descendant references |

### MerkleDAG

The filesystem-backed storage engine for all Merkle objects.

| Field | Type | Description |
|-------|------|-------------|
| `storage_path` | `str` | Directory path where objects are stored as files |

#### `_object_path(cid: CID) -> str`

Returns the filesystem path for an object: `{storage_path}/{cid_hex}`. The filename is the 64-character hex-encoded CID.

#### `put(obj: Blob | Tree | Commit) -> CID`

Stores an object to disk with a **type prefix**:

| Object Type | On-Disk Format |
|-------------|---------------|
| `Blob` | `BLOB:<raw_data_bytes>` |
| `Tree` | `TREE:<serialized_entries_bytes>` |
| `Commit` | `COMMIT:<serialized_commit_bytes>` |

The type prefix enables `get()` to determine how to deserialize the object. The filename is the CID hex string.

#### `get(cid: CID) -> Optional[Blob | Tree | Commit]`

Retrieves and deserializes an object by CID:

1. Reads the file at `{storage_path}/{cid_hex}`
2. Splits by the first `:` to extract the type prefix
3. Dispatches to the appropriate deserialization:
   - `BLOB` → Creates `Blob(data=content, cid=cid)`
   - `TREE` → Calls `Tree._deserialize(content, cid)`
   - `COMMIT` → Calls `Commit._deserialize(content, cid)`
4. Returns `None` if the file does not exist or the type is unrecognized

#### `has(cid: CID) -> bool`

Checks whether an object file exists on disk via `os.path.exists()`.

### Factory Functions

Convenience constructors that create objects without requiring manual instantiation:

```python
create_blob(data: bytes) -> Blob
create_tree(entries: List[TreeEntry]) -> Tree
create_commit(tree_cid: CID, parent_cids: List[CID], author: str, message: str, timestamp: float = 0) -> Commit
```

`create_commit` uses `timestamp or time.time()` so that passing `0` (the default) triggers automatic timestamp generation.

---

## store.py -- ObjectStore

`ObjectStore` is a **facade** over `MerkleDAG` that provides a type-safe, higher-level API for storing and retrieving objects.

| Field | Type | Description |
|-------|------|-------------|
| `dag` | `MerkleDAG` | The underlying MerkleDAG instance |

### Constructor

```python
ObjectStore(dag: MerkleDAG)
```

Accepts an existing `MerkleDAG` instance. The `ObjectStore` does not manage the filesystem path directly -- it delegates all I/O to the wrapped `MerkleDAG`.

### Store Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `store_blob` | `(data: bytes) -> CID` | Creates a `Blob`, stores it, returns the CID |
| `store_tree` | `(entries: List[TreeEntry]) -> CID` | Creates a `Tree`, stores it, returns the CID |
| `store_commit` | `(tree_cid, parent_cids, author, message) -> CID` | Creates a `Commit` with auto-timestamp, stores it, returns the CID |

Each method handles object construction, calls `dag.put()`, asserts the CID is set, and returns it.

### Get Methods (Type-Safe)

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_blob` | `(cid: CID) -> Optional[Blob]` | Retrieves by CID; returns `None` if not a `Blob` |
| `get_tree` | `(cid: CID) -> Optional[Tree]` | Retrieves by CID; returns `None` if not a `Tree` |
| `get_commit` | `(cid: CID) -> Optional[Commit]` | Retrieves by CID; returns `None` if not a `Commit` |

Each method calls `dag.get(cid)` and uses `isinstance()` to ensure the returned object matches the expected type.

### Query Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `has_object` | `(cid: CID) -> bool` | Delegates to `dag.has(cid)` |
| `list_objects` | `() -> List[CID]` | Scans the storage directory and returns CIDs for all 64-character filenames |

`list_objects()` uses filename length (64 characters) as a heuristic for valid CIDs. This could produce false positives if non-object files with 64-character names exist in the storage directory.

---

## CID Computation Details

### Blob

```
data: bytes
  ↓
SHA-256(data)
  ↓
32-byte digest → CID
```

### Tree

```
entries: [TreeEntry(name, cid, type), ...]
  ↓
Sort by name
  ↓
Serialize: "name:type:cid\n" for each entry
  ↓
SHA-256(serialized_bytes)
  ↓
32-byte digest → CID
```

### Commit

```
tree_cid, parent_cids, author, message, timestamp
  ↓
Serialize: "tree_cid|parent1,parent2|author|message|timestamp"
  ↓
SHA-256(serialized_bytes)
  ↓
32-byte digest → CID
```

---

## Persistence Layout

```
./data/objects/
    ├── a1b2c3d4e5f6...  (64-char hex = Blob CID)
    │       Content: BLOB:<raw file data>
    │
    ├── b7c8d9e0f1a2...  (64-char hex = Tree CID)
    │       Content: TREE:file1.txt:blob:a1b2c3...\nsubdir:tree:c3d4e5...
    │
    └── c3d4e5f6a7b8...  (64-char hex = Commit CID)
            Content: COMMIT:b7c8d9...|parent_cid|Deepanshu|initial commit|1714500000.0
```

Every file in the objects directory is named by its CID (64 hex characters) and prefixed with its type (`BLOB:`, `TREE:`, `COMMIT:`).

---

## Integration with the Backend

### Dependency Map

```
┌─────────────────────────────────────────────┐
│              API Layer                       │
│   server.py  /  repo.py                     │
└──────────┬──────────────────────┬───────────┘
           │                      │
           ▼                      ▼
┌─────────────────────┐  ┌──────────────────────┐
│   storage/          │  │   security/          │
│   ObjectStore       │  │   SMPPValidator      │
│   MerkleDAG         │  │                      │
│   CID, Blob, Tree,  │  │   Uses CID.from_hex()│
│   Commit, TreeEntry │  │   to fetch CRDT state│
└────────┬────────────┘  └──────────────────────┘
         │
         ▼
┌─────────────────────┐
│   crdt/             │
│   CRDTState         │
│   (serialized as    │
│    blob in store)   │
└─────────────────────┘
```

### NodeAPI (`backend/api/repo.py`)

`NodeAPI` is the top-level component that wires storage into the system:

```python
class NodeAPI:
    def __init__(self, data_dir: str = "./data"):
        self.dht = MerkleDAG(os.path.join(data_dir, "objects"))
        self.object_store = ObjectStore(self.dht)
```

Creates the `MerkleDAG` filesystem store and wraps it with `ObjectStore`. All repository operations flow through this layer.

### Repository (`backend/api/repo.py`)

The `Repository` class uses `ObjectStore` for all version control operations:

| Operation | What It Does |
|-----------|-------------|
| `init()` | Creates an empty `Tree`, then an initial `Commit` with no parent, stores both via `object_store` |
| `commit(files)` | For each file: stores as `Blob` → collects `TreeEntry` → creates `Tree` → creates `Commit` with parent = HEAD → updates HEAD |
| `get_commit(cid)` | Calls `object_store.get_commit(cid)` |
| `get_file(commit_cid, filename)` | Traverses: Commit → Tree → Blob chain to retrieve file content |
| `get_history()` | Walks the parent chain from HEAD, yielding each commit |

### FastAPI Server (`backend/api/server.py`)

Imports `CID`, `Tree`, `TreeEntry`, `Commit`, `Blob` directly for creating objects and computing CIDs in HTTP API handlers. However, the server stores commits in an **in-memory `Dict`** (`repo.commits`) rather than using `MerkleDAG.put()`. The filesystem storage is primarily used through `NodeAPI` and the CLI.

### SMPP Validator (`backend/security/smpp.py`)

Uses `CID.from_hex()` in `_fetch_crdt_state()` to convert stored CID strings back into `CID` objects, then calls `object_store.get_blob(cid)` to retrieve CRDT state data.

### CLI (`backend/cli/main.py`)

Uses `CID.from_hex()` to parse commit CIDs from command-line arguments (e.g., for the `cat` command that displays commit content).

---

## Complete Data Flow: Commit Creation

```
1. User provides files to commit
         │
2. For each file:
   - Create Blob(data=file_bytes)
   - CID auto-computed as SHA-256(data)
   - object_store.store_blob() → blob_cid
         │
3. Create TreeEntry for each blob:
   - TreeEntry(name=filename, cid=blob_cid, entry_type='blob')
         │
4. Create and store Tree:
   - Tree(entries=[...])
   - CID auto-computed from serialized entries
   - object_store.store_tree() → tree_cid
         │
5. Create and store Commit:
   - Commit(tree_cid=tree_cid, parent_cids=[head_cid], author=..., message=..., timestamp=...)
   - CID auto-computed from serialized fields
   - object_store.store_commit() → commit_cid
         │
6. Update repository HEAD to new commit_cid
         │
7. Create SMPP record pointing to commit_cid and crdt_state_cid
```

---

## Serialization Format Reference

### On-Disk Format (all objects)

```
<TYPE_PREFIX>:<PAYLOAD>
```

| Type | Prefix | Payload |
|------|--------|---------|
| Blob | `BLOB:` | Raw file bytes (no encoding) |
| Tree | `TREE:` | `name:type:cid\n` lines, sorted by name |
| Commit | `COMMIT:` | `tree_cid\|parent_cids\|author\|message\|timestamp` |

### Tree Serialization (inside TREE: payload)

```
file.txt:blob:a1b2c3d4e5f6...
src:tree:b7c8d9e0f1a2...
```

- One entry per line
- Sorted alphabetically by name
- Format: `name:entry_type:cid_hex`

### Commit Serialization (inside COMMIT: payload)

```
b7c8d9e0f1a2...|a1b2c3d4e5f6...|Deepanshu|initial commit|1714500000.123
```

- Fields separated by `|`
- Parent CIDs separated by `,` (empty if no parents)
- Timestamp as float string

---

## Public API Summary

```python
from backend.storage import (
    CID, Blob, Tree, Commit, MerkleDAG, TreeEntry,
    create_blob, create_tree, create_commit,
    ObjectStore,
)

# --- Setup ---
dag = MerkleDAG("./data/objects")
store = ObjectStore(dag)

# --- Store a blob ---
blob_cid = store.store_blob(b"Hello, world!")

# --- Store a tree ---
tree_cid = store.store_tree([
    TreeEntry(name="hello.txt", cid=blob_cid, entry_type="blob"),
])

# --- Store a commit ---
commit_cid = store.store_commit(
    tree_cid=tree_cid,
    parent_cids=[],
    author="Deepanshu",
    message="Initial commit",
)

# --- Retrieve objects ---
blob = store.get_blob(blob_cid)
tree = store.get_tree(tree_cid)
commit = store.get_commit(commit_cid)

# --- Check existence ---
store.has_object(commit_cid)  # True

# --- List all objects ---
all_cids = store.list_objects()

# --- CID operations ---
cid = CID.from_data(b"some data")
cid = CID.from_hex("a1b2c3d4...")
str(cid)  # 64-char hex string

# --- Factory functions ---
blob = create_blob(b"data")
tree = create_tree([TreeEntry("file.txt", blob.cid, "blob")])
commit = create_commit(tree.cid, [], "Author", "message")
```

---

## Design Notes and Known Limitations

1. **No actual chunking**: The `Blob` docstring states "chunked at 256KB" but no chunking is implemented. Large files are stored as single blobs, which means their CID covers the entire file content.

2. **No integrity verification on read**: When `get()` deserializes an object, it does not re-hash the content to verify it matches the CID. Any corruption or tampering on disk would go undetected.

3. **Delimiter collision risk**: The serialization formats use `|`, `,`, `:`, and `\n` as delimiters. If a commit message contains `|`, a filename contains `:`, or entry data contains `\n`, deserialization will break or produce incorrect results.

4. **No atomic writes**: `put()` writes directly to the target file without using a temp file + rename pattern or `fsync`. A crash mid-write could leave a corrupted object.

5. **Server bypasses MerkleDAG**: The FastAPI server (`api/server.py`) creates `CID`/`Tree`/`Commit` objects in memory but stores commits in an in-memory `Dict` rather than calling `MerkleDAG.put()`. Filesystem persistence only occurs through `NodeAPI`/CLI paths.

6. **`list_objects()` heuristic**: Uses 64-character filename length to identify valid CIDs. Any non-object file with a 64-character name would be incorrectly returned as a CID.

7. **No garbage collection**: There is no mechanism to identify and remove unreferenced objects (e.g., blobs from deleted commits). Storage grows monotonically.

8. **`Set` imported but unused**: `typing.Set` is imported in `merkle.py` but never referenced.

9. **Timestamp inconsistency**: `create_commit()` uses `timestamp or time.time()` with a default of `0`, but `Commit.__post_init__` does not auto-set timestamp. Creating a `Commit` directly with `timestamp=0` will result in a zero timestamp rather than the current time.

10. **No compression**: Objects are stored as raw bytes with no compression (unlike Git's zlib-compressed objects).

11. **No tests**: There are no unit tests or integration tests for the storage package.
