"""
Kademlia DHT implementation for peer discovery.
"""

from dataclasses import dataclass
from typing import List, Optional
import hashlib


@dataclass
class NodeID:
    """160-bit node identifier."""
    data: bytes

    @classmethod
    def generate(cls) -> 'NodeID':
        import os
        return cls(data=os.urandom(20))

    @classmethod
    def from_bytes(cls, data: bytes) -> 'NodeID':
        return cls(data=data[:20])

    def xor_distance(self, other: 'NodeID') -> bytes:
        return bytes(a ^ b for a, b in zip(self.data, other.data))

    def __lt__(self, other: 'NodeID') -> bool:
        return self.data < other.data


@dataclass
class Peer:
    """Network peer representation."""
    node_id: NodeID
    address: str
    port: int


class KBucket:
    """K-bucket for storing up to k peers."""
    K = 20

    def __init__(self, range_start: bytes, range_end: bytes):
        self.range_start = range_start
        self.range_end = range_end
        self.peers: List[Peer] = []

    def add(self, peer: Peer) -> bool:
        if peer in self.peers:
            self.peers.remove(peer)
            self.peers.append(peer)
            return True
        if len(self.peers) < self.K:
            self.peers.append(peer)
            return True
        return False

    def remove(self, peer: Peer) -> None:
        if peer in self.peers:
            self.peers.remove(peer)


class RoutingTable:
    """Kademlia routing table with k-buckets."""
    K = 20

    def __init__(self, local_node_id: NodeID):
        self.local_id = local_node_id
        self.buckets: List[KBucket] = []

    def _get_bucket_index(self, peer_id: NodeID) -> int:
        distance = self.local_id.xor_distance(peer_id)
        for i, b in enumerate(self.buckets):
            if b.range_start <= distance < b.range_end:
                return i
        return len(self.buckets) - 1


class DHTNode:
    """Kademlia DHT node for peer discovery."""

    def __init__(self, node_id: Optional[NodeID] = None, address: str = "0.0.0.0", port: int = 0):
        self.node_id = node_id or NodeID.generate()
        self.address = address
        self.port = port
        self.routing_table = RoutingTable(self.node_id)

    def find_node(self, target_id: NodeID) -> List[Peer]:
        """Find nodes closest to target_id."""
        raise NotImplementedError

    def find_value(self, key: bytes) -> Optional[bytes]:
        """Find value or return closest nodes."""
        raise NotImplementedError

    def store(self, key: bytes, value: bytes) -> bool:
        """Store value at key."""
        raise NotImplementedError

    def ping(self, peer: Peer) -> bool:
        """Check if peer is reachable."""
        raise NotImplementedError