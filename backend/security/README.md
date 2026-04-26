# Security Module

## Purpose
Provides cryptographic utilities and the Signed Merkle Pointer Protocol (SMPP) for secure commit validation and authorization.

## Components
- `crypto.py` - Cryptographic primitives (KeyPair, SignedData, Hasher)
- `smpp.py` - SMPP protocol (SMPPRecord, SMPPValidator, SMPPStore)

## Key Features
- Ed25519 digital signatures
- SHA-256 hashing
- SMPP record validation with 4-step verification
- Anti-replay protection via timestamps

## SMPP Validation Steps
1. Verify signature using author's public key
2. Fetch CRDT state from provided CID
3. Check if author is authorized in CRDT state
4. Validate timestamp (within tolerance, no duplicates)

## Record Structure
```
{
  repo_id,
  commit_cid,
  crdt_state_cid,
  timestamp,
  signature
}
```

## System Connection
- Used by `api/repo.py` for commit validation
- Depends on `crdt/lww_set.py` for authorization
- Integrates with `storage/merkle.py` for object references