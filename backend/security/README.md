# Security Module

## Overview

The `backend/security/` package provides the **cryptographic foundation**, **commit validation protocol**, and **user management** for a decentralized peer-to-peer version control system. It is organized into three modules:

| Module | Purpose |
|--------|---------|
| `crypto.py` | Cryptographic primitives -- key generation, HMAC-SHA256 signing, hashing |
| `smpp.py` | Signed Merkle Pointer Protocol (SMPP) -- commit validation and record storage |
| `user.py` | User identity, keypair management, and session handling |

Together, these modules ensure that every commit in the system is **cryptographically signed**, **authorization-checked against a CRDT state**, and **protected against replay attacks**.

---

## Architecture

```
backend/security/
├── __init__.py          # Package exports
├── crypto.py            # Cryptographic primitives
│   ├── KeyPair          # HMAC-SHA256 signing keypair
│   ├── SignedData       # Container for signed data with verification
│   └── Hasher           # Static hashing utilities (SHA-256, SHA-1, HMAC-SHA256)
├── smpp.py              # Signed Merkle Pointer Protocol
│   ├── SMPPRecord       # Protocol record structure
│   ├── SMPPValidator    # 4-step validation pipeline
│   └── SMPPStore        # File-based record persistence
└── user.py              # User management
    ├── User             # User identity with keypair
    ├── UserManager      # Multi-user management with session persistence
    └── create_demo_users()  # Factory for demo user setup
```

---

## crypto.py -- Cryptographic Primitives

### KeyPair

A signing keypair based on **HMAC-SHA256**.

| Field | Type | Description |
|-------|------|-------------|
| `public_key` | `bytes` | Derived as `SHA-256(private_key)` |
| `private_key` | `bytes` | 32-byte cryptographically random key |

#### `KeyPair.generate() -> KeyPair`

Generates a new keypair:
1. Creates a 32-byte private key using `secrets.token_bytes(32)` (CSPRNG)
2. Derives the public key as `SHA-256(private_key)`

**Important**: This is a **symmetric HMAC scheme**, not asymmetric public-key cryptography. The "public key" is a one-way hash of the private key. It cannot be used to verify signatures in the traditional public-key sense -- the private key is required for both signing and verification.

#### `sign(message: bytes) -> bytes`

Signs a message using HMAC-SHA256 with the private key:

```python
hmac.new(self.private_key, message, hashlib.sha256).digest()
```

Produces a 32-byte signature.

#### `verify(message: bytes, signature: bytes) -> bool`

**Demo mode**: Always returns `True`. This method is a placeholder that trusts its own signatures. In a production system, this would compute the expected signature and compare it.

### SignedData

A container that bundles data with its signature and the signer's public key.

| Field | Type | Description |
|-------|------|-------------|
| `data` | `bytes` | The raw signed data |
| `signature` | `bytes` | The HMAC-SHA256 signature |
| `public_key` | `bytes` | The signer's public key |

#### `verify() -> bool`

Performs proper signature verification:
1. Computes `HMAC-SHA256(public_key, data)`
2. Compares the result against the stored signature using `hmac.compare_digest()`

The use of `hmac.compare_digest()` ensures **timing-safe comparison**, preventing timing side-channel attacks.

**Note**: `SignedData` uses the `public_key` as the HMAC key for verification, which differs from how `KeyPair.sign()` uses the `private_key` as the HMAC key. This means `SignedData.verify()` and `KeyPair.sign()` are **not directly compatible** -- `SignedData` is designed for a different verification scenario where the public key itself serves as a shared secret.

### Hasher

Static utility class providing common hash functions.

| Method | Description |
|--------|-------------|
| `sha256(data: bytes) -> bytes` | SHA-256 hash (32 bytes) |
| `sha1(data: bytes) -> bytes` | SHA-1 hash (20 bytes) -- available but unused in codebase |
| `hmac_sha256(key: bytes, message: bytes) -> bytes` | HMAC-SHA256 computation |

---

## smpp.py -- Signed Merkle Pointer Protocol

### Purpose

SMPP is the **commit validation protocol** that cryptographically binds a commit to the CRDT authorization state at the time of signing. It ensures that:

1. Only authorized users can create commits
2. Each commit is linked to the authorization state snapshot used during signing
3. Replay attacks are detected and rejected

### SMPPRecord

The core data structure that represents a signed commit pointer.

| Field | Type | Description |
|-------|------|-------------|
| `repo_id` | `str` | Repository identifier |
| `commit_cid` | `str` | Content-ID (SHA-256 hex) of the Merkle commit object |
| `crdt_state_cid` | `str` | Content-ID of the serialized CRDT authorization state |
| `timestamp` | `float` | Unix timestamp of when the record was created |
| `signature` | `bytes` | HMAC-SHA256 signature over the record's serialized form |

#### Serialization

- `to_bytes() -> bytes` -- JSON-encodes `repo_id`, `commit_cid`, `crdt_state_cid`, and `timestamp` (excludes signature), then encodes to UTF-8 bytes
- `from_bytes(data: bytes, signature: bytes) -> SMPPRecord` -- Deserializes from bytes and attaches the signature
- `to_dict() -> dict` -- Full serialization including signature as hex string

#### Signing Flow

```python
# 1. Create unsigned record with current timestamp
record = SMPPRecord(repo_id=..., commit_cid=..., crdt_state_cid=..., timestamp=time.time(), signature=b'')

# 2. Sign the serialized form (excludes signature field)
signature = key_pair.sign(record.to_bytes())

# 3. Attach signature
record.signature = signature
```

### SMPPValidator

Implements the **4-step validation pipeline** for incoming SMPP records.

#### Constructor

```python
SMPPValidator(crdt_manager, object_store, clock_skew_tolerance=300)
```

| Parameter | Description |
|-----------|-------------|
| `crdt_manager` | `CRDTManager` instance for state access |
| `object_store` | `ObjectStore` instance for fetching CRDT blobs by CID |
| `clock_skew_tolerance` | Max allowed time drift in seconds (default: 300 = 5 minutes) |

The validator also maintains an in-memory `seen_records: Dict[str, float]` dictionary keyed by `{repo_id}:{commit_cid}:{timestamp}` for replay detection.

#### 4-Step Validation Pipeline

`validate(record: SMPPRecord, public_key: bytes) -> tuple[bool, str]`

```
Step 1: Signature Verification
    ↓
Step 2: CRDT State Fetch
    ↓
Step 3: Authorization Check
    ↓
Step 4: Timestamp Check (Anti-Replay)
    ↓
Result: (True, "Valid") or (False, "Step N: reason")
```

**Step 1 -- Signature Verification** (`_verify_signature`)

Attempts to verify the record's signature against the provided public key. Creates a temporary `KeyPair` with `private_key=b''` and calls `verify()`, which **always returns `True`** in demo mode. This step currently does not provide actual cryptographic validation.

**Step 2 -- CRDT State Fetch** (`_fetch_crdt_state`)

1. Converts `crdt_state_cid` (hex string) to a `CID` object
2. Fetches the corresponding blob from the `object_store`
3. Parses the blob's JSON data and deserializes it into a `CRDTState`
4. Returns `None` if the CID is not found or deserialization fails

**Step 3 -- Authorization Check** (`_check_authorization`)

1. Converts the `public_key` bytes to a hex string
2. Calls `crdt_state.is_authorized(key_hex)` which checks the LWW-Set
3. Returns `True` only if the key is present in the authorized set

This is the **actual access control gate** -- even with a valid signature, an unauthorized key will cause validation to fail.

**Step 4 -- Timestamp Check** (`_check_timestamp`)

Rejects records where:
- Timestamp is more than `clock_skew_tolerance` seconds in the **future**
- Timestamp is more than `clock_skew_tolerance` seconds in the **past**
- The `{repo_id}:{commit_cid}:{timestamp}` key already exists in `seen_records` (replay detection)

On success, records the key in `seen_records` to prevent future replays.

### SMPPStore

File-based persistence layer for SMPP records.

#### Constructor

```python
SMPPStore(storage_path: str)
```

Creates the storage directory if it does not exist.

#### `store_record(record: SMPPRecord) -> None`

Persists a record as a JSON file at `{storage_path}/{repo_id}/{commit_cid}.json`. Auto-creates the repository subdirectory.

#### `get_record(repo_id: str, commit_cid: str) -> Optional[SMPPRecord]`

Retrieves a record by reconstructing it from the JSON file. Reads the hex-encoded signature, converts it back to bytes, and calls `SMPPRecord.from_bytes()`.

---

## user.py -- User Management

### User

Represents a system identity with a cryptographic keypair.

| Field | Type | Description |
|-------|------|-------------|
| `username` | `str` | Human-readable username |
| `user_id` | `str` | 32-char hex random identifier |
| `public_key` | `bytes` | The user's public key (SHA-256 of private key) |
| `keypair` | `KeyPair` | The full signing keypair (excluded from repr and serialization) |

#### `User.create(username: str) -> User`

Factory method that:
1. Generates a random 16-byte user ID via `secrets.token_hex(16)`
2. Generates a new `KeyPair` via `KeyPair.generate()`
3. Returns a new `User` instance

#### Serialization

- `to_dict() -> dict` -- Serializes `username`, `user_id`, and `public_key` (as hex). **Excludes the private key** for safety.
- `from_dict(data: dict, keypair: KeyPair) -> User` -- Deserializes and requires a `keypair` to be provided externally.

### UserManager

Manages the user registry and session state.

| Field | Type | Description |
|-------|------|-------------|
| `storage_path` | `str` | Directory for `users.json` and `session.json` |
| `users` | `Dict[str, User]` | In-memory user registry keyed by `user_id` |
| `current_user` | `Optional[User]` | Currently logged-in user |

#### Lifecycle

1. On construction, calls `_load_users()` to restore users from `users.json`
2. Creates the storage directory if needed

#### Operations

| Method | Description |
|--------|-------------|
| `create_user(username)` | Creates a new user, saves to disk, returns the user |
| `get_user(user_id)` | Lookup by user ID |
| `get_user_by_username(username)` | Linear search by username |
| `list_users()` | Returns all users as dictionaries (without private keys) |
| `login(user_id)` | Sets `current_user` and writes `session.json` |
| `logout()` | Clears `current_user` and deletes `session.json` |
| `get_current_user()` | Returns `current_user`, or restores from `session.json` if not set |

#### Session Mechanism

- **Login**: Writes `{"user_id": "..."}` to `{storage_path}/session.json`
- **Restore**: On `get_current_user()`, reads `session.json` and looks up the user
- **Logout**: Deletes `session.json`

There is **no password verification**, **no session expiration**, and **no token-based auth**. The session is purely a file-based pointer to a user ID.

#### `create_demo_users(storage_path) -> UserManager`

Factory function that creates a `UserManager` and populates it with four demo users if the registry is empty:

| Username | Purpose |
|----------|---------|
| Deepanshu | Demo user 1 |
| Priya | Demo user 2 |
| Mohit | Demo user 3 |
| Tanya | Demo user 4 |

This is called automatically when the FastAPI server starts.

---

## Cryptographic Design

### Key Generation

```
Private Key: 32 bytes from CSPRNG (secrets.token_bytes)
     ↓
Public Key: SHA-256(Private Key) = 32 bytes
```

This is a **symmetric key derivation**, not asymmetric cryptography. The public key is a one-way hash of the private key.

### Signing

```
Message ──┐
          ├──→ HMAC-SHA256(private_key, message) → 32-byte signature
Key ──────┘
```

### Verification (Demo Mode)

Currently bypassed -- `KeyPair.verify()` always returns `True`. The `SignedData.verify()` method provides the correct verification path using timing-safe comparison.

### Hashing

| Algorithm | Output Size | Usage |
|-----------|-------------|-------|
| SHA-256 | 32 bytes | CIDs, public key derivation, general hashing |
| SHA-1 | 20 bytes | Available but unused |
| HMAC-SHA256 | 32 bytes | Signing, `Hasher` utility |

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
│   security/         │  │   security/          │
│   UserManager       │  │   SMPPValidator      │
│   KeyPair           │  │   SMPPRecord         │
│   SMPPStore         │  │   SMPPStore          │
└────────┬────────────┘  └────────┬─────────────┘
         │                        │
         ▼                        ▼
┌─────────────────────┐  ┌──────────────────────┐
│   security/         │  │   crdt/              │
│   crypto.py         │  │   CRDTState          │
│   (KeyPair)         │  │   LWWSet             │
└─────────────────────┘  └────────┬─────────────┘
                                  │
                                  ▼
                        ┌──────────────────────┐
                        │   storage/           │
                        │   ObjectStore        │
                        │   CID                │
                        └──────────────────────┘
```

### API Server (`backend/api/server.py`)

- Initializes `UserManager` with `create_demo_users()` on startup
- **Login endpoint** (`POST /users/login`): Looks up user by username, auto-creates if not found, calls `UserManager.login()`
- **Logout endpoint** (`POST /users/logout`): Calls `UserManager.logout()`
- **Commit creation** (`POST /repos/{repo_id}/commits`):
  1. Checks CRDT authorization via `repo.is_authorized()`
  2. Creates `SMPPRecord` with the user's keypair
  3. Validates the record through `SMPPValidator` (4-step pipeline)
  4. Returns structured response with validation log entries

### Node API (`backend/api/repo.py`)

- `NodeAPI` aggregates all subsystems including `SMPPValidator` and `SMPPStore`
- `Repository.commit()`:
  1. Auto-authorizes the node's public key on initialization
  2. Creates SMPP records for every commit
  3. Stores records via `SMPPStore`
  4. Embeds CRDT state CID into the commit

### CRDT Module (`backend/crdt/lww_set.py`)

- `SMPPValidator._fetch_crdt_state()` deserializes `CRDTState` from the object store
- `SMPPValidator._check_authorization()` queries the LWW-Set for key membership
- CRDT state is the single source of truth for repository write permissions

### Storage Module (`backend/storage/merkle.py`)

- `CID` objects (SHA-256 based) are used to reference commits and CRDT states within SMPP records
- `SMPPValidator` uses the object store's `get_blob()` to retrieve CRDT state by CID

---

## Complete Data Flow: Commit Creation

```
1. User sends commit request to server
         │
2. Server checks: UserManager.get_current_user()
   ──→ None? Reject (not logged in)
   ──→ User found? Proceed
         │
3. Server checks: repo.is_authorized(public_key_hex)
   ──→ False? Reject (not in CRDT authorized set)
   ──→ True? Proceed
         │
4. Server creates Merkle commit:
   - Serializes tree and blobs
   - Computes SHA-256 CIDs
   - Creates Commit object
         │
5. Server creates SMPP record:
   - repo_id + commit_cid + crdt_state_cid + timestamp
   - Signs with user's KeyPair (HMAC-SHA256)
         │
6. Server validates SMPP record (4-step pipeline):
   Step 1: Signature check (demo: always passes)
   Step 2: Fetch CRDT state from object store by CID
   Step 3: Check public_key in CRDT authorized set
   Step 4: Check timestamp (not stale, not replayed)
   ──→ Any step fails? Reject with error message
   ──→ All pass? Proceed
         │
7. Server stores commit in repo.commits
   Updates repo.head
   Stores SMPP record via SMPPStore
         │
8. Return success response with commit CID
```

---

## Persistence Layout

```
./data/
├── users.json              # User registry (username, user_id, public_key)
├── session.json            # Current session (user_id only)
├── crdt/                   # CRDT states (from crdt module)
│   └── {repo_id}_crdt.json
└── smpp/                   # SMPP records
    └── {repo_id}/
        └── {commit_cid}.json
```

---

## Public API Summary

```python
from backend.security import (
    KeyPair, SignedData, Hasher,
    SMPPRecord, SMPPValidator, SMPPStore,
    User, UserManager, create_demo_users,
)

# --- User Management ---
users = create_demo_users("./data")
user = users.get_user_by_username("Deepanshu")
users.login(user.user_id)
current = users.get_current_user()

# --- Cryptography ---
keypair = KeyPair.generate()
message = b"commit:data"
signature = keypair.sign(message)

# Verify via SignedData (proper verification path)
signed = SignedData(data=message, signature=signature, public_key=keypair.public_key)
signed.verify()  # True (timing-safe comparison)

# --- Hashing ---
Hasher.sha256(b"data")
Hasher.hmac_sha256(keypair.private_key, b"message")

# --- SMPP ---
validator = SMPPValidator(crdt_manager=manager, object_store=store)
record = validator.create_record(
    key_pair=keypair,
    repo_id="repo-123",
    commit_cid="abc123...",
    crdt_state_cid="def456...",
)
is_valid, message = validator.validate(record, keypair.public_key)

# --- SMPP Storage ---
smpp_store = SMPPStore("./data/smpp")
smpp_store.store_record(record)
retrieved = smpp_store.get_record("repo-123", "abc123...")
```

---

## Design Notes and Known Limitations

1. **Signature verification is bypassed**: `KeyPair.verify()` always returns `True`, and `SMPPValidator._verify_signature()` uses this method. The SMPP pipeline does not perform actual cryptographic signature validation. Only `SignedData.verify()` implements proper verification, but it is not used in the validation pipeline.

2. **Symmetric keys, not asymmetric**: The "public key" is `SHA-256(private_key)`. This means anyone with the private key can sign, and verification requires the private key as well (or a shared secret arrangement). This is fundamentally a symmetric HMAC scheme, not public-key cryptography.

3. **Private key loss on reload**: When `UserManager._load_users()` restores users from `users.json`, it generates **new random keypairs** for each user. The original private keys are lost, meaning:
   - Previously signed data cannot be re-verified by reloaded users
   - Demo users get new keys on every server restart
   - Private keys are never persisted to disk (by design, but with no recovery mechanism)

4. **In-memory replay cache**: `SMPPValidator.seen_records` is not persisted. Server restarts clear the replay detection cache, allowing previously seen records to be replayed.

5. **No session security**: Sessions are file-based with no password verification, no expiration, no CSRF protection, and no encryption. Anyone with filesystem access can read or modify `session.json`.

6. **No password-based authentication**: The system uses identity-only authentication. Login requires only a `user_id` -- there is no password, challenge-response, or token verification.

7. **Unused SHA-1**: `Hasher.sha1()` is defined but never called anywhere in the codebase.

8. **No tests**: There are no unit tests or integration tests for any module in the security package.

9. **README discrepancy**: The existing README claims "Ed25519 digital signatures" but the implementation uses HMAC-SHA256. The actual algorithm is HMAC-SHA256, not Ed25519.

10. **Demo mode architecture**: The verification bypass is intentional for demonstration purposes but should be replaced with proper asymmetric cryptography (e.g., Ed25519 or ECDSA) for production use.
