"""
CLI interface for the decentralized versioning system.
"""

import argparse
import sys
import os
import pickle

DATA_DIR = "./data"
STATE_FILE = os.path.join(DATA_DIR, "cli_state.pkl")


def load_state():
    """Load persisted state."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'rb') as f:
            return pickle.load(f)
    return None


def save_state(api):
    """Persist API state."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_FILE, 'wb') as f:
        pickle.dump(api, f)


def get_api():
    """Get or create API instance."""
    state = load_state()
    if state:
        return state
    from backend.api.repo import NodeAPI
    api = NodeAPI(DATA_DIR)
    save_state(api)
    return api


def main():
    parser = argparse.ArgumentParser(
        description="Decentralized P2P File Versioning System"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    init_parser = subparsers.add_parser("init", help="Initialize a new repository")
    init_parser.add_argument("repo_id", help="Repository ID")

    commit_parser = subparsers.add_parser("commit", help="Create a new commit")
    commit_parser.add_argument("repo_id", help="Repository ID")
    commit_parser.add_argument("-m", "--message", required=True, help="Commit message")
    commit_parser.add_argument("-f", "--files", nargs="+", help="Files to commit")

    log_parser = subparsers.add_parser("log", help="Show commit history")
    log_parser.add_argument("repo_id", help="Repository ID")
    log_parser.add_argument("-n", "--limit", type=int, default=10, help="Number of commits")

    cat_parser = subparsers.add_parser("cat", help="Show file content at commit")
    cat_parser.add_argument("repo_id", help="Repository ID")
    cat_parser.add_argument("commit", help="Commit CID")
    cat_parser.add_argument("filename", help="File name")

    subparsers.add_parser("node-id", help="Show node ID")

    subparsers.add_parser("start", help="Start the P2P node")
    subparsers.add_parser("stop", help="Stop the P2P node")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "init":
        api = get_api()
        repo = api.create_repository(args.repo_id)
        head = repo.init()
        save_state(api)
        print(f"Initialized repository '{args.repo_id}'")
        print(f"Initial commit: {head}")

    elif args.command == "commit":
        api = get_api()
        repo = api.get_repository(args.repo_id)
        if not repo:
            print(f"Repository '{args.repo_id}' not found")
            sys.exit(1)

        files = {}
        if args.files:
            for f in args.files:
                if os.path.exists(f):
                    with open(f, 'rb') as fp:
                        files[f] = fp.read()

        head = repo.commit(args.message, files)
        save_state(api)
        print(f"Created commit: {head}")

    elif args.command == "log":
        api = get_api()
        repo = api.get_repository(args.repo_id)
        if not repo:
            print(f"Repository '{args.repo_id}' not found")
            sys.exit(1)

        for commit in repo.get_history(args.limit):
            print(f"Commit: {commit.cid}")
            print(f"Author: {commit.author}")
            print(f"Message: {commit.message}")
            print(f"Timestamp: {commit.timestamp}")
            print()

    elif args.command == "cat":
        api = get_api()
        from backend.storage.merkle import CID
        repo = api.get_repository(args.repo_id)
        if not repo:
            print(f"Repository '{args.repo_id}' not found")
            sys.exit(1)

        content = repo.get_file(CID.from_hex(args.commit), args.filename)
        if content:
            print(content.decode())
        else:
            print(f"File not found")

    elif args.command == "node-id":
        api = get_api()
        print(f"Node ID: {api.node.node_id.data.hex()}")

    elif args.command == "start":
        print("Starting P2P node...")
        api = get_api()
        api.start()
        save_state(api)
        print("Node started")

    elif args.command == "stop":
        print("Stopping P2P node...")


if __name__ == "__main__":
    main()