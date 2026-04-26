#!/usr/bin/env python
"""
Demo script for decentralized P2P file versioning system.
"""

import os
import sys
import subprocess

def run(args):
    print(f"$ {' '.join(args)}")
    result = subprocess.run(args, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode

def main():
    print("=" * 60)
    print("Decentralized P2P File Versioning System - Demo")
    print("=" * 60)
    print()

    repo = "demo-repo"

    print("Step 1: Initialize a new repository")
    print("-" * 40)
    run(["python", "-m", "backend.cli.main", "init", repo])
    print()

    print("Step 2: Create and commit a Python file")
    print("-" * 40)
    with open("demo.py", "w") as f:
        f.write("print('Hello from decentralized versioning!')\n")
    run(["python", "-m", "backend.cli.main", "commit", repo, "-m", "Add demo.py", "-f", "demo.py"])
    print()

    print("Step 3: Create and commit another file")
    print("-" * 40)
    with open("utils.py", "w") as f:
        f.write("def add(a, b): return a + b\n")
    run(["python", "-m", "backend.cli.main", "commit", repo, "-m", "Add utils.py", "-f", "utils.py"])
    print()

    print("Step 4: View commit history")
    print("-" * 40)
    run(["python", "-m", "backend.cli.main", "log", repo])
    print()

    print("Step 5: View file content at latest commit")
    print("-" * 40)
    commit_cid = "e5e1d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e1d2c3b4a5f6e7d8c9b0a1f2"
    print(f"(Use first commit CID from log above)")
    print()

    print("Step 6: Show node ID")
    print("-" * 40)
    run(["python", "-m", "backend.cli.main", "node-id"])
    print()

    print("=" * 60)
    print("Demo complete!")
    print("=" * 60)

    os.remove("demo.py")
    os.remove("utils.py")

if __name__ == "__main__":
    main()