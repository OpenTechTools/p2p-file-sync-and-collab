# Transport Module

This package implements RUDP (Reliable UDP) - a protocol that adds reliability to unreliable UDP datagrams.

## Overview

UDP is fast but unreliable - packets can be lost, duplicated, or arrive out of order. RUDP fixes this using Selective Repeat ARQ (Automatic Repeat Request).

## PacketType Enum

| Type  | Value | Description                     |
|-------|------|------------------------------|
| DATA  | 0x01 | Data packet                   |
| ACK   | 0x02 | Acknowledgment (positive)    |
| NAK   | 0x03 | Negative acknowledgment          |
| SYN   | 0x04 | Connection establishment      |
| FIN   | 0x05 | Connection teardown          |

## Packet Class

Represents a single RUDP packet:

```python
@dataclass
class Packet:
    seq_num: int      # Sequence number (for ordering)
    ack_num: int     # Ack number (what we received)
    packet_type: PacketType
    data: bytes     # Payload
    checksum: int   # CRC32 for integrity
```

### Methods

| Method            | Description                      |
|------------------|--------------------------------|
| compute_checksum() | CRC32 hash of header + data     |
| verify()         | Check if checksum matches        |

## SlidingWindow Class

Selective Repeat ARQ - allows multiple unacknowledged packets.

### Constructor

```python
def __init__(self, window_size: int = 16, timeout: float = 5.0):
```

- `window_size`: Max unacked packets (16)
- `timeout`: Retransmit after 5 seconds

### Internal State

- `self.unacked: Dict[int, Packet]` - Sent but not acknowledged
- `self.received: Dict[int, bytes]` - Received packets (buffered)
- `self.base_seq: int` - Oldest unacked sequence number
- `self.next_seq: int` - Next sequence to use
- `self.timers: Dict[int, float]` - Per-packet timers

### Key Methods

| Method             | Description                          |
|-------------------|--------------------------------------|
| send(data)        | Add packet to send window (if not full) |
| receive_ack(ack_num) | Process incoming ACK, slide window forward |
| receive_packet(packet) | Buffer incoming packet, return data if in order |
| get_ordered_data() | Get consecutive packets starting from base |
| retransmit_needed() | Return packets that timed out       |

### How Sliding Window Works

Sender's View (window_size = 4):

```
Sent & Acked    |  In Window (can send)   |  Outside Window (wait)
----------------|------------------------|-----------------------
Seq 0,1,2       |  Seq 3,4,5,6           |  Seq 7,8,9...
(base=3)       |  (next_seq=7)          |
```

When ACK 3 arrives → base becomes 4 → window slides → can send more

## RUDPSession Class

Manages a bidirectional RUDP session between two peers:

```python
def __init__(self, remote_addr: tuple, window_size: int = 16):
    self.sender = SlidingWindow(window_size)   # For sending
    self.receiver = SlidingWindow(window_size)  # For receiving
    self.connected = False
```

### Methods

| Method   | Description                   |
|----------|-------------------------------|
| send(data) | Create packet, add to sender window |
| receive(packet) | Process DATA or ACK packet |

## RUDPProtocol Class

Main protocol handler - serializes/deserializes packets for network transmission.

### Methods

| Method              | Description                      |
|--------------------|----------------------------------|
| create_session(remote_addr) | Get or create session for peer |
| send_packet(addr, packet) | Serialize packet to bytes     |
| recv_packet(data) | Deserialize bytes to Packet     |

### Packet Serialization Format (13 bytes header)

```
Byte layout:  [seq_num:4][ack_num:4][type:1][checksum:4][data...n]
            └───────────────────13 bytes──────────────────┘
```

```python
struct.pack('!IIBI', seq_num, ack_num, type.value, checksum)
```

- `!` = Network byte order (big-endian)
- `I` = unsigned int (4 bytes)
- `B` = unsigned char (1 byte)

## How RUDP Works

### Sending Data

1. App calls `session.send(b"Hello")`
2. `SlidingWindow.send()` → creates `Packet(seq=0, data=b"Hello")`
3. `RUDPProtocol.send_packet()` → serializes to bytes
4. App sends bytes over UDP socket
5. Timer starts for seq=0

### Receiving ACK

1. Receive `ACK(seq=1)` from network
2. `session.receive()` → process as ACK type
3. `SlidingWindow.receive_ack(1)`
4. Remove seq 0 from unacked, slide base to 1

### Receiving Data

1. Receive DATA packet from network
2. `session.receive()` → process as DATA type
3. `receiver.receive_packet()` → buffer it
4. If consecutive → `get_ordered_data()` returns it
5. Send ACK back to sender

## Key Features

- Selective Repeat ARQ for reliable transmission
- Sliding window flow control
- ACK/NAK based acknowledgment
- Checksum verification for data integrity
- Configurable window size and timeout

## System Connection

- Base transport layer for all P2P communication
- Used by `backend/api/repo.py` for peer-to-peer commit exchange
- Provides reliable data transfer between nodes in the decentralized network
- Current backend server uses HTTP for web API, but RUDP handles P2P data transfer