"""
Kademlia DHT Protocol definitions.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Any
import json


class MessageType(Enum):
    PING = 0x01
    PONG = 0x02
    FIND_NODE = 0x03
    NODES = 0x04
    STORE = 0x05
    STORED = 0x06
    FIND_VALUE = 0x07
    VALUE = 0x08


@dataclass
class DHTMessage:
    """Base DHT message structure."""
    msg_type: MessageType
    transaction_id: bytes
    node_id: bytes


@dataclass
class PingMessage(DHTMessage):
    """Ping request/response."""
    pass


@dataclass
class FindNodeMessage(DHTMessage):
    """Find closest nodes to target."""
    target: bytes


@dataclass
class StoreMessage(DHTMessage):
    """Store key-value pair."""
    key: bytes
    value: bytes


@dataclass
class NodesMessage(DHTMessage):
    """Response with closest nodes."""
    nodes: List[bytes]


def serialize_message(msg: DHTMessage) -> bytes:
    """Serialize DHT message to bytes."""
    return json.dumps({
        'type': msg.msg_type.value,
        'txn_id': msg.transaction_id.hex(),
        'node_id': msg.node_id.hex(),
    }).encode()


def deserialize_message(data: bytes) -> DHTMessage:
    """Deserialize DHT message from bytes."""
    parsed = json.loads(data.decode())
    msg_type = MessageType(parsed['type'])
    # Simplified deserialization - full implementation would handle all types
    return DHTMessage(
        msg_type=msg_type,
        transaction_id=bytes.fromhex(parsed['txn_id']),
        node_id=bytes.fromhex(parsed['node_id'])
    )