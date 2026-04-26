"""
Decentralized P2P File Versioning System

A peer-to-peer version control system using:
- Kademlia DHT for peer discovery
- Reliable UDP (Selective Repeat ARQ) for transport
- Merkle DAG for content-addressable storage
- CRDT (LWW Set) for authorization
- SMPP for signed commit validation
"""

from .api.repo import Repository, NodeAPI

__all__ = ['Repository', 'NodeAPI']
__version__ = '0.1.0'