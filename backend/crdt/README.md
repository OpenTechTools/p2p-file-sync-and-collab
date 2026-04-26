# CRDT Module

## Purpose
Implements Conflict-free Replicated Data Types (CRDT) using Last-Writer-Wins (LWW) Set for authorization management in a decentralized setting.

## Components
- `lww_set.py` - LWW Set implementation (LWWElement, LWWSet, CRDTState, CRDTManager)

## Key Features
- Last-Writer-Wins semantics for conflict resolution
- Add/Remove operations with timestamps
- Merge capability for distributed state synchronization
- Persistent state storage

## How It Works
- Each element has a timestamp
- On conflict, the element with the latest timestamp wins
- Supports both add and remove operations
- Can merge states from multiple nodes

## System Connection
- Used by `security/smpp.py` for authorization checking
- Integrated with `api/repo.py` for repository access control
- State stored and loaded by CRDTManager