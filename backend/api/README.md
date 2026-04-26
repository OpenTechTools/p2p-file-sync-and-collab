# API Module

## Purpose
Provides high-level API for repository operations and P2P node management in the decentralized versioning system.

## Components
- `repo.py` - Core interfaces (Repository, NodeAPI)

## Key Features
- Repository creation and management
- Commit creation with file changes
- History traversal and file retrieval
- Node bootstrapping and network joining
- Integration of all subsystems (DHT, transport, storage, CRDT, security)

## System Connection
- Depends on all other modules
- Provides CLI interface with commands
- Manages lifecycle of repositories and network node