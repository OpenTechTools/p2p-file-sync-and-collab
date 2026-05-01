# Network Module

## Overview

The `backend/network/` package implements the **Kademlia Distributed Hash Table (DHT)** protocol for peer discovery in a decentralized peer-to-peer version control system. It provides the data structures for node identification, peer routing, and DHT message types.

**Important**: This package is a **well-structured skeleton** -- the core DHT algorithms (iterative lookup, peer refresh, bucket maintenance) and all network I/O (UDP sockets, async event loops) are **not implemented**. The four `DHTNode` RPC methods all raise `NotImplementedError`. Actual transport is handled by the sibling `backend/transport/` package (RUDP), which is also a stub without socket code.

---

## Architecture

```
backend/network/
├── __init__.py          # Package exports
├── dht.py               # Core Kademlia DHT structures
│   ├── NodeID           # 160-bit node identifier with XOR distance
│   ├── Peer             # Network peer (node_id, address, port)
│   ├── KBucket          # K-bucket storing up to 20 peers (MRU eviction)
│   ├── RoutingTable     # Collection of KBuckets indexed by XOR distance
│   └── DHTNode          # DHT node (stub -- all RPCs unimplemented)
└── protocol.py          # DHT message protocol
    ├── MessageType      # 8 Kademlia RPC types (PING, FIND_NODE, STORE, etc.)
    ├── DHTMessage       # Base message structure
    ├── PingMessage      # PING/PONG message
    ├── FindNodeMessage  # FIND_NODE request (with target)
    ├── StoreMessage     # STORE request (key-value)
    ├── NodesMessage     # NODES response (list of node IDs)
    ├── serialize_message()    # JSON serialization
    └── deserialize_message()  # JSON deserialization

backend/transport/       # Sibling package -- Reliable UDP (RUDP)
└── rudp.py
    ├── PacketType       # DATA, ACK, NAK, SYN, FIN
    ├── Packet           # 13-byte header + data (CRC32 integrity)
    ├── SlidingWindow    # Selective Repeat ARQ (window=16, timeout=5s)
    ├── RUDPSession      # Bidirectional session with sender + receiver windows
    └── RUDPProtocol     # Binary serialization/deserialization
```

---

## dht.py -- Kademlia DHT Structures

### NodeID

A **160-bit (20-byte)** identifier that uniquely identifies a node in the DHT network.

| Field | Type | Description |
|-------|------|-------------|
| `data` | `bytes` | 20-byte raw identifier |

#### Factory Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `generate` | `() -> NodeID` | Creates a random 20-byte NodeID via `os.urandom(20)` |
| `from_bytes` | `(data: bytes) -> NodeID` | Creates a NodeID from bytes, truncated to 20 bytes |

#### XOR Distance Metric

`xor_distance(other: NodeID) -> bytes`

Computes the **bitwise XOR** of two NodeIDs byte-by-byte:

```python
bytes(a ^ b for a, b in zip(self.data, other.data))
```

The XOR metric is the foundation of Kademlia routing. It satisfies:

| Property | Meaning |
|----------|---------|
| Identity | `d(x, x) = 0` |
| Symmetry | `d(x, y) = d(y, x)` |
| Triangle inequality | `d(x, z) <= d(x, y) + d(y, z)` |
| Unidirectionality | For any `x` and distance `d`, there is exactly one `y` such that `d(x, y) = d` |

The XOR distance determines which k-bucket a peer belongs to in the routing table.

#### Comparison

`__lt__(other: NodeID) -> bool` -- Lexicographic comparison on raw bytes, used for ordering peers by distance.

### Peer

Represents a network peer in the DHT.

| Field | Type | Description |
|-------|------|-------------|
| `node_id` | `NodeID` | The peer's 160-bit identifier |
| `address` | `str` | IP address or hostname |
| `port` | `int` | UDP port number |

### KBucket

A **k-bucket** stores up to K=20 peers whose XOR distance from the local node falls within a specific range.

| Field | Type | Description |
|-------|------|-------------|
| `range_start` | `bytes` | Lower bound of XOR distance range |
| `range_end` | `bytes` | Upper bound of XOR distance range |
| `peers` | `List[Peer]` | Peers in this bucket |

#### Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `K` | `20` | Maximum peers per bucket |

#### Operations

| Method | Signature | Description |
|--------|-----------|-------------|
| `add` | `(peer: Peer) -> bool` | Adds a peer; returns `False` if bucket is full |
| `remove` | `(peer: Peer) -> None` | Removes a peer from the bucket |

#### MRU (Most Recently Used) Policy

When `add()` is called for a peer that already exists in the bucket:
1. The peer is **removed** from its current position
2. The peer is **appended** to the end of the list

This moves the most recently seen peer to the tail, providing an implicit liveness signal. In a complete Kademlia implementation, when the bucket is full, the head peer (least recently seen) would be pinged for liveness and replaced if unresponsive.

#### Bucket Fill Behavior

- **New peer, bucket not full** (`len < K`): Appended to the end, returns `True`
- **Existing peer**: Moved to end (MRU refresh), returns `True`
- **New peer, bucket full**: Rejected, returns `False`

### RoutingTable

The Kademlia routing table -- a collection of KBuckets indexed by XOR distance from the local node.

| Field | Type | Description |
|-------|------|-------------|
| `local_id` | `NodeID` | This node's own identifier |
| `buckets` | `List[KBucket]` | List of KBuckets |

#### Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `K` | `20` | Maximum peers per bucket |

#### `_get_bucket_index(peer_id: NodeID) -> int`

Finds the bucket index for a given peer by:
1. Computing `distance = local_id.xor_distance(peer_id)`
2. Iterating through buckets to find the one where `range_start <= distance < range_end`
3. Returning the last bucket index if no match is found

**Important**: This method assumes buckets exist. Since `__init__` creates an empty `buckets` list, calling `_get_bucket_index` on a fresh routing table would return `-1` (from `len([]) - 1`).

#### Incomplete Initialization

The routing table starts with **zero buckets**. A complete Kademlia implementation would:
1. Create an initial bucket spanning the full ID space (`0x00...00` to `0xFF...FF`)
2. **Split buckets** when they fill up and the local node's ID falls within the range
3. Provide an `add_peer()` method that routes peers to the correct bucket

None of this logic exists.

### DHTNode

The main DHT node class -- the entry point for all DHT operations.

| Field | Type | Description |
|-------|------|-------------|
| `node_id` | `NodeID` | This node's 160-bit identifier (auto-generated if not provided) |
| `address` | `str` | Network address (default: `"0.0.0.0"`) |
| `port` | `int` | UDP port (default: `0`) |
| `routing_table` | `RoutingTable` | This node's routing table |

#### Constructor

```python
DHTNode(node_id=None, address="0.0.0.0", port=0)
```

If no `node_id` is provided, one is generated randomly via `NodeID.generate()`.

#### RPC Methods (All Stubbed)

All four core Kademlia RPC operations raise `NotImplementedError`:

| Method | Signature | Intended Purpose |
|--------|-----------|-----------------|
| `find_node` | `(target_id: NodeID) -> List[Peer]` | Iteratively find the K closest nodes to a target ID |
| `find_value` | `(key: bytes) -> Optional[bytes]` | Look up a value in the DHT or return closest nodes |
| `store` | `(key: bytes, value: bytes) -> bool` | Store a key-value pair at the K closest nodes to the key |
| `ping` | `(peer: Peer) -> bool` | Check if a peer is reachable |

#### What's Missing

To make this a functional DHT node, the following would need to be implemented:

- **UDP socket I/O**: `socket.sendto()` / `socket.recvfrom()` or async equivalents
- **Iterative lookup algorithm**: The Kademlia FIND_NODE procedure that progressively narrows down to closest nodes
- **Parallelism**: Concurrent RPCs to multiple nodes during lookup (typically α=3 parallel queries)
- **Peer refresh**: Periodic PING to check liveness of stale peers
- **Bucket maintenance**: Splitting full buckets, evicting unresponsive peers
- **Value storage/retrieval**: The STORE and FIND_VALUE procedures
- **Async event loop**: `asyncio` or similar for handling concurrent operations

---

## protocol.py -- DHT Message Protocol

### MessageType

An enumeration of all 8 Kademlia RPC message types:

| Type | Value | Direction | Purpose |
|------|-------|-----------|---------|
| `PING` | `0x01` | Request | Check if a peer is alive |
| `PONG` | `0x02` | Response | Reply to PING |
| `FIND_NODE` | `0x03` | Request | Find K closest nodes to a target ID |
| `NODES` | `0x04` | Response | Return list of closest nodes |
| `STORE` | `0x05` | Request | Store a key-value pair |
| `STORED` | `0x06` | Response | Confirm key-value was stored |
| `FIND_VALUE` | `0x07` | Request | Look up a value by key |
| `VALUE` | `0x08` | Response | Return the value for a key |

### DHTMessage

The base message structure for all DHT communication.

| Field | Type | Description |
|-------|------|-------------|
| `msg_type` | `MessageType` | The type of message |
| `transaction_id` | `bytes` | Unique identifier for request/response matching |
| `node_id` | `bytes` | The sender's NodeID |

### Message Subtypes

#### PingMessage

```python
@dataclass
class PingMessage(DHTMessage):
    pass
```

No additional fields. A PING carries only the base message fields.

#### FindNodeMessage

```python
@dataclass
class FindNodeMessage(DHTMessage):
    target: bytes
```

Adds `target` -- the 160-bit NodeID to find closest nodes for.

#### StoreMessage

```python
@dataclass
class StoreMessage(DHTMessage):
    key: bytes
    value: bytes
```

Adds `key` and `value` -- the data to store in the DHT.

#### NodesMessage

```python
@dataclass
class NodesMessage(DHTMessage):
    nodes: List[bytes]
```

Adds `nodes` -- a list of 160-bit NodeIDs for the closest nodes.

### Serialization

#### `serialize_message(msg: DHTMessage) -> bytes`

Serializes a DHT message to **JSON bytes**:

```python
{
    "type": 3,                    # MessageType.value (int)
    "txn_id": "a1b2c3d4...",      # transaction_id as hex string
    "node_id": "e5f6a7b8..."      # node_id as hex string
}
```

**Critical gap**: Only the base `DHTMessage` fields are serialized. Subtype-specific fields (`target`, `key`, `value`, `nodes`) are **not included**. A `FindNodeMessage` serialized through this function loses its `target` field.

#### `deserialize_message(data: bytes) -> DHTMessage`

Deserializes JSON bytes back to a `DHTMessage`. Always returns the base `DHTMessage` type -- the original subtype information is lost since `serialize_message` doesn't preserve it.

The code includes an explicit comment: *"Simplified deserialization - full implementation would handle all types"*.

---

## transport/rudp.py -- Reliable UDP (Sibling Package)

The `backend/transport/` package provides a **Reliable UDP (RUDP)** implementation using Selective Repeat ARQ. It is designed to be the transport layer for DHT messages but is also a stub without actual socket I/O.

### PacketType

| Type | Value | Purpose |
|------|-------|---------|
| `DATA` | `0x01` | Carries payload data |
| `ACK` | `0x02` | Acknowledges received packets |
| `NAK` | `0x03` | Negative acknowledgment (request retransmission) |
| `SYN` | `0x04` | Connection establishment |
| `FIN` | `0x05` | Connection teardown |

### Packet

The RUDP packet structure with a **13-byte header** followed by variable-length data.

| Field | Type | Size | Description |
|-------|------|------|-------------|
| `seq_num` | `int` | 4 bytes | Sequence number (unsigned 32-bit) |
| `ack_num` | `int` | 4 bytes | Acknowledgment number (unsigned 32-bit) |
| `packet_type` | `PacketType` | 1 byte | Type of packet |
| `checksum` | `int` | 4 bytes | CRC32 integrity check (unsigned 32-bit) |
| `data` | `bytes` | variable | Payload |

#### Wire Format

```
[seq_num: 4B][ack_num: 4B][type: 1B][checksum: 4B][data: variable]
```

Network byte order (big-endian) via `struct.pack('!IIBI', ...)`.

#### `compute_checksum() -> int`

Computes CRC32 over the header (seq_num, ack_num, type) plus data:

```python
zlib.crc32(header + self.data) & 0xFFFFFFFF
```

#### `verify() -> bool`

Compares the stored `checksum` against a freshly computed one.

### SlidingWindow

Implements **Selective Repeat ARQ** (Automatic Repeat reQuest) for reliable data transfer.

| Field | Type | Description |
|-------|------|-------------|
| `window_size` | `int` | Maximum unacknowledged packets in flight (default: 16) |
| `timeout` | `float` | Retransmission timeout in seconds (default: 5.0) |
| `unacked` | `Dict[int, Packet]` | Sent but not yet acknowledged |
| `received` | `Dict[int, bytes]` | Out-of-order buffered data |
| `base_seq` | `int` | Lowest unacknowledged sequence number |
| `next_seq` | `int` | Next sequence number to assign |
| `timers` | `Dict[int, float]` | Per-packet send timestamps for timeout detection |

#### Operations

| Method | Signature | Description |
|--------|-----------|-------------|
| `send` | `(data: bytes) -> Optional[Packet]` | Creates a DATA packet; returns `None` if window is full |
| `receive_ack` | `(ack_num: int) -> None` | Processes cumulative ACK; slides window forward |
| `receive_packet` | `(packet: Packet) -> Optional[bytes]` | Buffers out-of-order data; returns data or `None` for duplicates |
| `get_ordered_data` | `() -> List[bytes]` | Delivers in-order data from `base_seq` onward |
| `retransmit_needed` | `() -> List[Packet]` | Returns packets whose timeout has elapsed |

#### Selective Repeat ARQ Logic

**Sending**:
1. If `next_seq >= base_seq + window_size`, the window is full -- return `None`
2. Create a DATA packet with `seq_num = next_seq`
3. Compute CRC32 checksum
4. Store in `unacked` dict with current timestamp
5. Increment `next_seq`

**Receiving ACKs (cumulative)**:
1. For all `seq < ack_num`, remove from `unacked` and `timers`
2. Advance `base_seq` to `ack_num`

**Receiving DATA packets**:
1. If `seq_num < base_seq`, the packet is already acknowledged -- ignore
2. If `seq_num` is already in `received`, it's a duplicate -- ignore
3. Otherwise, buffer the data in `received`

**Retransmission**:
1. Check each unacked packet's timestamp against current time
2. If `now - timestamp > timeout`, add to retransmit list and reset timer

### RUDPSession

A bidirectional RUDP session with separate sender and receiver sliding windows.

| Field | Type | Description |
|-------|------|-------------|
| `remote_addr` | `tuple` | Remote peer address `(host, port)` |
| `sender` | `SlidingWindow` | Outgoing data window |
| `receiver` | `SlidingWindow` | Incoming data window |
| `connected` | `bool` | Session state (never set to `True` in current code) |

#### Operations

| Method | Signature | Description |
|--------|-----------|-------------|
| `send` | `(data: bytes) -> Optional[Packet]` | Delegates to `sender.send()` |
| `receive` | `(packet: Packet) -> Optional[bytes]` | Dispatches by packet type: DATA → buffer, ACK → update sender window |

### RUDPProtocol

The protocol handler that manages sessions and handles binary serialization.

| Field | Type | Description |
|-------|------|-------------|
| `local_port` | `int` | Local UDP port (default: 0) |
| `sessions` | `Dict[tuple, RUDPSession]` | Active sessions keyed by remote address |

#### Operations

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_session` | `(remote_addr: tuple) -> RUDPSession` | Creates or returns existing session for a remote peer |
| `send_packet` | `(addr: tuple, packet: Packet) -> bytes` | Serializes a packet to bytes: 13-byte header + data |
| `recv_packet` | `(data: bytes) -> Optional[Packet]` | Deserializes bytes to a Packet; returns `None` if data < 13 bytes |

---

## Integration with the Backend

### Dependency Map

```
┌─────────────────────────────────────────────┐
│              API Layer                       │
│   server.py  /  repo.py                     │
└──────────┬──────────────────────┬───────────┘
           │                      │
           ▼                      ▼
┌─────────────────────┐  ┌──────────────────────┐
│   network/          │  │   transport/         │
│   DHTNode           │  │   RUDPProtocol       │
│   NodeID, Peer      │  │   RUDPSession        │
│   RoutingTable      │  │   SlidingWindow      │
│   KBucket           │  │   Packet             │
└────────┬────────────┘  └──────────────────────┘
         │
         ▼
┌─────────────────────┐
│   api/repo.py       │
│   NodeAPI           │
│   (wires DHT + RUDP │
│    + storage + crdt │
│    + security)      │
└─────────────────────┘
```

### NodeAPI (`backend/api/repo.py`)

`NodeAPI` is the facade that initializes and coordinates all subsystems:

```python
class NodeAPI:
    def __init__(self, data_dir: str = "./data"):
        self.node = DHTNode()                    # Creates DHT node with random ID
        self.dht = MerkleDAG(...)                # Storage layer
        self.object_store = ObjectStore(self.dht)
        self.crdt_manager = CRDTManager(...)     # Authorization
        self.smpp_validator = SMPPValidator(...) # Commit validation
```

#### `join_network(bootstrap_nodes: List[tuple])`

Attempts to join the DHT network by adding bootstrap peers:

```python
for addr, port in bootstrap_nodes:
    peer = Peer(node_id=NodeID.generate(), address=addr, port=port)
    self.node.routing_table.buckets[0].add(peer)
```

**This will crash** with `IndexError` because `routing_table.buckets` is always empty (no initialization). There is no bucket creation logic.

#### `start()` / `stop()`

Both are no-ops (`pass`). No sockets are opened, no event loop is started.

### FastAPI Server (`backend/api/server.py`)

The server does **not** use the network module. Instead, it uses **simulated peers**:

```python
simulated_peers = [
    {"id": "peer-a", "name": "Peer A", "address": "192.168.1.10", "online": True},
    {"id": "peer-b", "name": "Peer B", "address": "192.168.1.11", "online": True},
    {"id": "peer-c", "name": "Peer C", "address": "192.168.1.12", "online": False},
]
```

The `/repos/{repo_id}/sync` endpoint iterates over these hardcoded peers and logs simulated sync steps ("Fetching", "Validating via SMPP", "CRDT merge complete") without any actual network communication.

### CLI (`backend/cli/main.py`)

Accesses the DHT node's ID for display:

```python
print(f"Node ID: {api.node.node_id.data.hex()}")
```

---

## Complete Peer Discovery Flow (As Designed, Not Implemented)

```
1. Node starts with random 160-bit NodeID
         │
2. Node joins network via bootstrap nodes:
   join_network([("bootstrap.example.com", 8000)])
         │
3. Bootstrap nodes added to routing table k-buckets
         │
4. Iterative FIND_NODE lookup:
   a. Query closest known peers for target
   b. Receive NODES response with closer peers
   c. Repeat until no closer peers found
   d. Result: K closest peers to target ID
         │
5. STORE value at K closest peers:
   a. FIND_NODE to locate closest peers to key hash
   b. Send STORE request to each
   c. Receive STORED confirmation
         │
6. FIND_VALUE by key:
   a. FIND_NODE to locate closest peers to key hash
   b. Query peers for value
   c. Receive VALUE response
         │
7. Periodic maintenance:
   - PING stale peers in k-buckets
   - Evict unresponsive peers
   - Split full buckets
```

**Currently**: Steps 2-7 are all unimplemented. Step 2 crashes with `IndexError`.

---

## RUDP Data Flow (As Designed, Not Implemented)

```
1. Create session to remote peer:
   session = protocol.create_session(("192.168.1.10", 8000))
         │
2. Send data (Selective Repeat ARQ):
   packet = session.send(b"hello")
   bytes = protocol.send_packet(remote_addr, packet)
   socket.sendto(bytes, remote_addr)
         │
3. Receive data:
   data, addr = socket.recvfrom(65535)
   packet = protocol.recv_packet(data)
   session.receive(packet)
         │
4. ACK processing:
   - Receiver sends ACK packet
   - Sender advances sliding window on ACK
   - Retransmit unacked packets after timeout
         │
5. Connection teardown:
   FIN → ACK → close
```

**Currently**: No socket code exists. Steps 2-5 are packet manipulation only.

---

## Public API Summary

```python
from backend.network import (
    DHTNode, NodeID, Peer, KBucket, RoutingTable,
    DHTMessage, MessageType,
    serialize_message, deserialize_message,
)
from backend.transport import (
    Packet, PacketType, SlidingWindow, RUDPSession, RUDPProtocol,
)

# --- NodeID ---
node_id = NodeID.generate()
node_id = NodeID.from_bytes(b'some 20 bytes...')
distance = node_id.xor_distance(other_node_id)
str(node_id)  # 40-char hex string

# --- Peer ---
peer = Peer(node_id=node_id, address="192.168.1.10", port=8000)

# --- KBucket ---
bucket = KBucket(range_start=b'\x00' * 20, range_end=b'\xFF' * 20)
bucket.add(peer)    # True
bucket.remove(peer)

# --- DHTNode ---
node = DHTNode()  # Random ID, empty routing table
node.node_id.data.hex()  # 40-char hex

# --- Protocol Messages ---
msg = FindNodeMessage(
    msg_type=MessageType.FIND_NODE,
    transaction_id=os.urandom(16),
    node_id=node.node_id.data,
    target=target_node_id.data,
)
serialized = serialize_message(msg)  # JSON bytes (subtype fields lost!)
parsed = deserialize_message(serialized)  # Base DHTMessage only

# --- RUDP ---
protocol = RUDPProtocol(local_port=9000)
session = protocol.create_session(("192.168.1.10", 8000))

packet = session.send(b"hello")
wire_bytes = protocol.send_packet(("192.168.1.10", 8000), packet)
# socket.sendto(wire_bytes, ("192.168.1.10", 8000))  # Would need socket

# Receive side:
# raw = socket.recvfrom(65535)
received = protocol.recv_packet(raw[0])
data = session.receive(received)
```

---

## Design Notes and Known Limitations

### Network Module (`network/`)

1. **Complete stub**: The `DHTNode` has four methods, all raising `NotImplementedError`. There is no UDP socket code, no async I/O, no iterative lookup, no peer discovery, no value storage or retrieval.

2. **Routing table never initialized**: `RoutingTable.__init__()` creates an empty bucket list. `NodeAPI.join_network()` accesses `buckets[0]` which will always raise `IndexError`. There is no bucket creation, splitting, or `add_peer()` method.

3. **Serialization loses subtype data**: `serialize_message()` only serializes base `DHTMessage` fields. The `target` (FindNodeMessage), `key`/`value` (StoreMessage), and `nodes` (NodesMessage) fields are silently dropped.

4. **Deserialization loses type specificity**: `deserialize_message()` always returns a base `DHTMessage` -- the original message subtype is irrecoverable.

5. **README claims SHA-256 for NodeIDs**: The README states "160-bit node IDs using SHA-256" but the actual implementation uses `os.urandom(20)` -- random bytes, not a hash. `hashlib` is imported but never used.

6. **No concurrency model**: A real DHT requires an async event loop (`asyncio`) for concurrent RPCs. There is no async infrastructure.

7. **No tests**: There are no unit tests or integration tests for the network package.

### Transport Module (`transport/`)

8. **No socket I/O**: The RUDP implementation handles packet serialization, sliding window management, and checksum computation, but contains zero `socket.sendto()` or `socket.recvfrom()` calls. It is a packet manipulation library, not a transport protocol.

9. **No connection handshake**: `RUDPSession.connected` is never set to `True`. The SYN/FIN packet types exist but are never used in session lifecycle.

10. **`receive()` routes DATA to wrong window**: In `RUDPSession.receive()`, DATA packets are processed through `self.sender.receive_packet()` instead of `self.receiver.receive_packet()`. This appears to be a bug -- incoming data should go to the receiver window.

11. **No encryption or authentication**: RUDP packets are not encrypted, authenticated, or protected against replay attacks.

12. **Sequence number overflow**: `seq_num` is an unbounded Python int. In a real implementation, sequence numbers would wrap around (typically at 2^32), requiring additional logic.

13. **NAK never generated**: The `NAK` packet type is defined but never created or handled anywhere in the code.

14. **No tests**: There are no unit tests or integration tests for the transport package.
