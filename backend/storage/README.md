# Storage Module

## Purpose
Implements Merkle DAG storage for content-addressable version control, similar to Git's object model.

## Components
- `merkle.py` - Core DAG objects (CID, Blob, Tree, TreeEntry, Commit, MerkleDAG)
- `store.py` - High-level object store interface (ObjectStore)

## Key Features
- Content Identifiers (CID) using SHA-256
- Three object types: Blob (file content), Tree (directory), Commit (snapshot)
- Content-addressable storage on filesystem
- Merkle DAG for deduplication and integrity verification

## Object Types
| Type | Description |
|------|-------------|
| Blob | Raw file content (chunked at 256KB) |
| Tree | Directory structure with entries |
| Commit | Version snapshot with parent references |

## System Connection
- Used by `api/repo.py` for version history
- CIDs used by `security/smpp.py` for record references
- Integrated with CRDT for state management