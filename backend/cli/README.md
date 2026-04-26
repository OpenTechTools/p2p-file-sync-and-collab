# CLI Module

## Purpose
Command-line interface for interacting with the decentralized versioning system.

## Components
- `main.py` - CLI entry point with subcommands

## Commands
| Command | Description |
|---------|-------------|
| init | Initialize a new repository |
| commit | Create a new commit with file changes |
| log | Show commit history |
| cat | Show file content at specific commit |
| node-id | Display current node ID |
| start | Start the P2P node |
| stop | Stop the P2P node |

## Usage
```bash
python -m backend.cli.main init my-repo
python -m backend.cli.main commit my-repo -m "Add feature" -f file1.py file2.py
python -m backend.cli.main log my-repo -n 10
python -m backend.cli.main cat my-repo <commit-cid> filename
```

## System Connection
- Depends on `api/repo.py` for all operations
- Parses user commands and invokes appropriate API methods