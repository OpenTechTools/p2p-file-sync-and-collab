# Transport Module

This package implements RUDP (Reliable UDP) - a protocol that adds reliability to unreliable UDP datagrams.

---

## Overview

UDP (User Datagram Protocol) is a connectionless, unreliable protocol. It offers fast delivery but has no guarantees:
- **Packets can be lost** - No acknowledgment of delivery
- **Packets can be duplicated** - No detection of duplicates
- **Packets can arrive out of order** - No sequence numbering

RUDP fixes these issues using **Selective Repeat ARQ** (Automatic Repeat Request), which provides:
- Reliability through acknowledgments (ACK/NAK)
- Ordering through sequence numbers
- Flow control through sliding windows
- Integrity through checksums

---

## Architecture

```
backend/transport/
├── rudp.py          # Core RUDP implementation
└── README.md        # This file
```

---

## PacketType Enum (lines 13-18)

Defines the types of packets in the RUDP protocol:

```python
class PacketType(Enum):
    DATA = 0x01
    ACK = 0x02
    NAK = 0x03
    SYN = 0x04
    FIN = 0x05
```

| Type  | Value | Description |
|-------|-------|-------------|
| DATA  | 0x01 | Carries application data payload |
| ACK   | 0x02 | Positive acknowledgment - confirms receipt |
| NAK   | 0x03 | Negative acknowledgment - requests retransmission |
| SYN   | 0x04 | Synchronize - initiates connection |
| FIN   | 0x05 | Finish - terminates connection |

### Why These Packet Types?

**DATA (0x01):** The workhorse - carries actual application data. Each DATA packet has a sequence number for ordering.

**ACK (0x02):** Sent by receiver to confirm which packets were received successfully. Contains the next expected sequence number.

**NAK (0x03):** Sent when receiver detects missing packets. Allows selective retransmission rather than resending everything.

**SYN (0x04):** Initiates connection handshake. Similar to TCP's three-way handshake, ensures both parties are ready.

**FIN (0x05):** Graceful connection closure. Ensures all data is delivered before closing.

---

## Packet Class (lines 21-38)

Represents a single RUDP packet - the fundamental unit of communication:

```python
@dataclass
class Packet:
    seq_num: int           # Sequence number (for ordering)
    ack_num: int          # Ack number (what we received)
    packet_type: PacketType
    data: bytes           # Payload
    checksum: int = 0     # CRC32 for integrity
```

### Fields Explained

| Field | Type | Description |
|-------|------|-------------|
| seq_num | int | Sequence number of this packet. Used for ordering and identifying duplicates. Starts at 0, increments for each packet sent. |
| ack_num | int | Acknowledgment number. Indicates the next sequence number the sender expects to receive. Acts as cumulative ACK. |
| packet_type | PacketType | Type of packet (DATA, ACK, NAK, SYN, FIN) |
| data | bytes | Actual payload data. Can be empty for control packets. |
| checksum | int | CRC32 checksum for integrity verification. Computed from header + data. |

### compute_checksum() Method (lines 30-34)

```python
def compute_checksum(self) -> int:
    """Compute CRC32 checksum of packet."""
    import zlib
    header = struct.pack('!IIB', self.seq_num, self.ack_num, self.packet_type.value)
    return zlib.crc32(header + self.data) & 0xFFFFFFFF
```

**Purpose:** Generates a checksum for integrity verification.

**Process:**
1. Pack the header fields (seq_num, ack_num, packet_type) into binary format
2. Append the data payload
3. Compute CRC32 hash using zlib
4. Mask to 32-bit unsigned integer

**Format string `!IIB`:**
- `!` - Network byte order (big-endian) - ensures consistent encoding across different systems
- `I` - Unsigned int (4 bytes) for seq_num
- `I` - Unsigned int (4 bytes) for ack_num
- `B` - Unsigned char (1 byte) for packet_type

**Returns:** 32-bit CRC32 checksum

### verify() Method (lines 36-38)

```python
def verify(self) -> bool:
    """Verify packet integrity."""
    return self.checksum == self.compute_checksum()
```

**Purpose:** Verifies packet hasn't been corrupted during transmission.

**Process:**
1. Recompute checksum from current packet data
2. Compare with stored checksum
3. Return True if match, False if mismatch

This detects:
- Bit flips during transmission
- Data corruption
- Tampering

---

## SlidingWindow Class (lines 41-104)

Implements **Selective Repeat ARQ** - a sliding window protocol that allows multiple packets to be in flight simultaneously.

### Why Sliding Window?

Without a sliding window, stop-and-wait ARQ would:
1. Send one packet
2. Wait for ACK
3. Repeat

This is inefficient on high-latency networks. Sliding window allows:
- Multiple unacknowledged packets in flight
- Selective retransmission (only lost packets)
- Better utilization of network bandwidth

### Constructor (lines 44-51)

```python
def __init__(self, window_size: int = 16, timeout: float = 5.0):
    self.window_size = window_size
    self.timeout = timeout
    self.unacked: Dict[int, Packet] = {}
    self.received: Dict[int, bytes] = {}
    self.base_seq: int = 0
    self.next_seq: int = 0
    self.timers: Dict[int, float] = {}
```

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| window_size | int | 16 | Maximum number of unacknowledged packets |
| timeout | float | 5.0 | Seconds before retransmitting |

**Internal State:**

| Field | Type | Description |
|-------|------|-------------|
| window_size | int | Max unacked packets allowed |
| timeout | float | Retransmission timeout in seconds |
| unacked | Dict[int, Packet] | Packets sent but not yet acknowledged |
| received | Dict[int, bytes] | Received packets buffered (out of order) |
| base_seq | int | Sequence number of oldest unacked packet (window start) |
| next_seq | int | Next sequence number to use (window end) |
| timers | Dict[int, float] | When each packet was sent (for timeout detection) |

### Visual Representation

```
Window Size = 4

Sequence:  0    1    2    3    4    5    6    7    8    9
            │    │    │    │    │    │    │    │    │    │
            ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼
Status:   [ACK] [ACK] [ACK] [SENT] [SENT] [SENT] [SENT] [..] [..]
                     ▲                      ▲
                     │                      │
                  base=3                next_seq=7

Window: 3, 4, 5, 6 (can send these)
```

When ACK 3 arrives → base becomes 4 → window slides → can now send 7

### send() Method (lines 53-67)

```python
def send(self, data: bytes) -> Optional[Packet]:
    """Add packet to send window."""
    if self.next_seq >= self.base_seq + self.window_size:
        return None  # Window full
    packet = Packet(
        seq_num=self.next_seq,
        ack_num=0,
        packet_type=PacketType.DATA,
        data=data
    )
    packet.checksum = packet.compute_checksum()
    self.unacked[self.next_seq] = packet
    self.timers[self.next_seq] = time.time()
    self.next_seq += 1
    return packet
```

**Purpose:** Add a new packet to the send window.

**Process:**
1. **Check window capacity** - If `next_seq >= base_seq + window_size`, window is full, return None
2. **Create packet** - Build Packet with current sequence number
3. **Compute checksum** - Calculate and store CRC32
4. **Store in unacked dict** - Keep reference for potential retransmission
5. **Start timer** - Record send time for timeout detection
6. **Increment sequence** - Prepare for next packet
7. **Return packet** - Caller will serialize and send

**Returns:** Packet object if window not full, None if window is full

### receive_ack() Method (lines 69-76)

```python
def receive_ack(self, ack_num: int) -> None:
    """Process incoming ACK."""
    if ack_num >= self.base_seq:
        for seq in list(self.unacked.keys()):
            if seq < ack_num:
                del self.unacked[seq]
                self.timers.pop(seq, None)
        self.base_seq = ack_num
```

**Purpose:** Process acknowledgment from receiver, slide window forward.

**Process:**
1. **Validate ACK** - Only process if ack_num >= base_seq (cumulative ACK)
2. **Remove acked packets** - Delete all packets with seq < ack_num from unacked
3. **Clear timers** - Remove timers for acked packets
4. **Slide window** - Update base_seq to ack_num

**Example:**
```
Before: unacked = {0: pkt0, 1: pkt1, 2: pkt2, 3: pkt3}, base_seq = 0
Receive ACK 3
After:  unacked = {3: pkt3}, base_seq = 3
```

Packets 0, 1, 2 are acknowledged. Packet 3 still pending.

### receive_packet() Method (lines 78-85)

```python
def receive_packet(self, packet: Packet) -> Optional[bytes]:
    """Process incoming data packet."""
    if packet.seq_num < self.base_seq:
        return None  # Already acknowledged
    if packet.seq_num in self.received:
        return None  # Duplicate
    self.received[packet.seq_num] = packet.data
    return packet.data
```

**Purpose:** Buffer incoming packets, handle duplicates and out-of-order delivery.

**Process:**
1. **Check if already processed** - If seq_num < base_seq, already acknowledged, ignore
2. **Check for duplicates** - If seq_num already in received dict, ignore
3. **Buffer packet** - Store data in received dictionary
4. **Return data** - Return to caller for processing

**Returns:** Packet data if new, None if duplicate or too old

**Why buffer?** With out-of-order delivery, we might receive packet 5 before packet 4. We buffer 5 until 4 arrives, then deliver in order.

### get_ordered_data() Method (lines 87-94)

```python
def get_ordered_data(self) -> List[bytes]:
    """Get all ordered data starting from base."""
    result = []
    seq = self.base_seq
    while seq in self.received:
        result.append(self.received.pop(seq))
        seq += 1
    return result
```

**Purpose:** Extract consecutive ordered packets from receive buffer.

**Process:**
1. **Start from base** - Begin at base_seq (oldest expected)
2. **Check consecutive** - While next sequence number exists in received
3. **Extract data** - Pop from received, add to result
4. **Advance** - Increment sequence
5. **Return ordered data** - List of consecutive packets

**Example:**
```
received = {0: data0, 1: data1, 3: data3, 4: data4}, base_seq = 0
get_ordered_data() returns [data0, data1]
received now = {3: data3, 4: data4}
```

Packet 2 is missing, so we stop at 1. Packet 2 must be retransmitted.

### retransmit_needed() Method (lines 96-104)

```python
def retransmit_needed(self) -> List[Packet]:
    """Get packets that need retransmission."""
    now = time.time()
    result = []
    for seq, pkt in list(self.unacked.items()):
        if now - self.timers[seq] > self.timeout:
            self.timers[seq] = now  # Reset timer
            result.append(pkt)
    return result
```

**Purpose:** Find packets that have timed out and need retransmission.

**Process:**
1. **Get current time** - Check how long since we sent each packet
2. **Check timeout** - If `now - send_time > timeout`, packet is lost
3. **Reset timer** - Reset for next timeout check
4. **Collect packet** - Add to list of packets needing retransmission

**Returns:** List of packets to retransmit

---

## RUDPSession Class (lines 107-126)

Manages a bidirectional RUDP session between two peers.

### Why Separate Sender and Receiver?

In bidirectional communication:
- We send DATA packets (as sender)
- We receive DATA packets (as receiver)
- We send ACK packets (as receiver)
- We receive ACK packets (as sender)

A session needs both capabilities simultaneously.

### Constructor (lines 110-114)

```python
def __init__(self, remote_addr: tuple, window_size: int = 16):
    self.remote_addr = remote_addr
    self.sender = SlidingWindow(window_size)    # For sending
    self.receiver = SlidingWindow(window_size)  # For receiving
    self.connected = False
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| remote_addr | tuple | (IP, port) of remote peer |
| window_size | int | Sliding window size |

**Internal State:**
| Field | Type | Description |
|-------|------|-------------|
| remote_addr | tuple | Peer address |
| sender | SlidingWindow | Sending window (DATA we sent, ACKs for them) |
| receiver | SlidingWindow | Receiving window (DATA from them, ACKs we send) |
| connected | bool | Connection state |

### send() Method (lines 116-118)

```python
def send(self, data: bytes) -> Optional[Packet]:
    """Send data reliably."""
    return self.sender.send(data)
```

**Purpose:** Send data through the session.

Delegates to sender's sliding window. Returns packet ready for serialization.

### receive() Method (lines 120-126)

```python
def receive(self, packet: Packet) -> Optional[bytes]:
    """Process received packet."""
    if packet.packet_type == PacketType.DATA:
        return self.sender.receive_packet(packet)
    elif packet.packet_type == PacketType.ACK:
        self.sender.receive_ack(packet.ack_num)
    return None
```

**Purpose:** Process incoming packets (DATA or ACK).

**Process:**
1. **If DATA packet** - Process as receiver (buffer, check order)
2. **If ACK packet** - Process as sender (slide window, remove acked packets)
3. **Otherwise** - Ignore (NAK, SYN, FIN not implemented in this version)

---

## RUDPProtocol Class (lines 129-163)

Main protocol handler - serializes/deserializes packets for network transmission.

### Why Serialization?

Packets are Python objects. To send over network, they must be converted to bytes. This class handles that conversion.

### Constructor (lines 132-134)

```python
def __init__(self, local_port: int = 0):
    self.local_port = local_port
    self.sessions: Dict[tuple, RUDPSession] = {}
```

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| local_port | int | Local UDP port (0 = auto-assign) |

**Internal State:**
| Field | Type | Description |
|-------|------|-------------|
| local_port | int | Local port |
| sessions | Dict[tuple, RUDPSession] | Active sessions by remote address |

### create_session() Method (lines 136-140)

```python
def create_session(self, remote_addr: tuple) -> RUDPSession:
    """Create or get existing session."""
    if remote_addr not in self.sessions:
        self.sessions[remote_addr] = RUDPSession(remote_addr)
    return self.sessions[remote_addr]
```

**Purpose:** Get or create session for a peer.

**Process:**
1. Check if session exists for this remote address
2. If not, create new RUDPSession
3. Return existing or new session

**Returns:** RUDPSession for the peer

### send_packet() Method (lines 142-150)

```python
def send_packet(self, addr: tuple, packet: Packet) -> bytes:
    """Serialize packet for sending."""
    header = struct.pack('!IIBI',
        packet.seq_num,
        packet.ack_num,
        packet.packet_type.value,
        packet.checksum
    )
    return header + packet.data
```

**Purpose:** Convert Packet object to bytes for network transmission.

**Packet Format (13 bytes header + data):**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RUDP Packet Structure                        │
├──────────┬──────────┬──────────┬──────────┬────────────────────────┤
│ seq_num  │ ack_num  │  type    │ checksum │         data           │
│  (4B)    │  (4B)    │  (1B)    │  (4B)    │     (variable)        │
└──────────┴──────────┴──────────┴──────────┴────────────────────────┘
└────────────────────── 13 bytes ──────────────────────┘
```

**Format string `!IIBI`:**
| Character | Type | Size | Description |
|-----------|------|------|-------------|
| ! | - | - | Network byte order (big-endian) |
| I | unsigned int | 4 bytes | seq_num |
| I | unsigned int | 4 bytes | ack_num |
| B | unsigned char | 1 byte | packet_type.value |
| I | unsigned int | 4 bytes | checksum |

**Returns:** Serialized bytes ready for UDP send()

### recv_packet() Method (lines 152-163)

```python
def recv_packet(self, data: bytes) -> Optional[Packet]:
    """Deserialize packet."""
    if len(data) < 13:
        return None
    header = struct.unpack('!IIBI', data[:13])
    return Packet(
        seq_num=header[0],
        ack_num=header[1],
        packet_type=PacketType(header[2]),
        checksum=header[3],
        data=data[13:]
    )
```

**Purpose:** Convert received bytes back to Packet object.

**Process:**
1. **Validate length** - Minimum 13 bytes for header
2. **Unpack header** - Extract seq_num, ack_num, type, checksum
3. **Convert type** - Enum value to PacketType
4. **Create packet** - Build Packet with header fields and remaining data
5. **Return packet** - For processing by session

**Returns:** Packet object or None if invalid

---

## How RUDP Works - Complete Flow

### Scenario: Sending a Message

```
Sender A                                      Receiver B
   │                                             │
   │  1. Create packet with seq=0, data="Hello"   │
   │  2. Compute checksum                        │
   │  3. Store in unacked[0]                     │
   │  4. Start timer                             │
   │  ─────────────────────────────────────────► │
   │                                             │
   │                                       5. Receive packet
   │                                       6. Verify checksum
   │                                       7. Buffer in received[0]
   │                                             │
   │  8. Send ACK(ack_num=1)                     │
   │  ◄───────────────────────────────────────── │
   │                                             │
   │  9. receive_ack(1)                          │
   │ 10. Remove seq 0 from unacked               │
   │ 11. Slide base_seq to 1                    │
   │                                             │
   │              Window Slid!                    │
```

### Step-by-Step Breakdown

#### Sending Data (lines 53-67)

1. Application calls `session.send(b"Hello")`
2. `SlidingWindow.send()` checks if window is full
3. Creates `Packet(seq_num=0, data=b"Hello")`
4. Computes checksum with `packet.compute_checksum()`
5. Stores in `self.unacked[0]`
6. Records send time in `self.timers[0]`
7. Returns packet to caller

#### Serialization (lines 142-150)

1. `RUDPProtocol.send_packet()` receives packet
2. Packs header: `struct.pack('!IIBI', 0, 0, 1, checksum)`
3. Appends data: `header + b"Hello"`
4. Returns 13+ bytes ready for UDP socket

#### Receiving Data (lines 78-85)

1. UDP socket receives bytes
2. `recv_packet()` deserializes to Packet
3. `session.receive(packet)` processes it
4. `receiver.receive_packet(packet)` buffers it
5. Returns data, caller processes

#### Sending ACK (not shown but implied)

1. After receiving DATA
2. Send ACK with ack_num = next expected sequence
3. This tells sender what we received

#### Receiving ACK (lines 69-76)

1. Receive ACK packet
2. `receive_ack(ack_num=1)` called
3. Remove all packets with seq < 1 from unacked
4. Clear their timers
5. Update base_seq to 1

---

## Sliding Window in Action

### Scenario: Sending 5 packets with one lost

```
Time 0:   Send pkt 0  → unacked = {0,1,2,3}
Time 1:   Send pkt 1    (window full at 4)
Time 2:   Send pkt 2
Time 3:   Send pkt 3
Time 4:   ACK 1 arrives → unacked = {2,3}, base_seq = 1
Time 5:   Send pkt 4    → unacked = {2,3,4}
Time 6:   ACK 2 arrives → unacked = {3,4}, base_seq = 2
...
```

### Loss Scenario

```
Send pkt 0,1,2,3 (window full)
Timeout for pkt 0
retransmit_needed() returns [pkt0]
Send pkt 0 again
Receive ACK 1
All packets acked
```

---

## Handling Out-of-Order Delivery

```
Received (in order):     0, 1, 2, 4, 5, 3

Buffer state:
  received[0] = data0
  received[1] = data1
  received[2] = data2
  received[4] = data4  ← Can't deliver yet!
  received[5] = data5
  received[3] = data3  ← Now consecutive!

get_ordered_data() from base_seq=0:
  Extract 0, 1, 2, 3, 4, 5
  All delivered in order!
```

---

## Error Handling

### Packet Loss Detection

- Timer tracks each sent packet
- If `current_time - send_time > timeout`, packet assumed lost
- `retransmit_needed()` returns such packets

### Duplicate Detection

- Receiver tracks received sequence numbers
- If `seq_num in received`, it's a duplicate
- Silently ignore duplicates

### Integrity Verification

- Sender computes CRC32 checksum
- Receiver verifies on receipt
- If mismatch, packet corrupted (drop it)

---

## Key Features

1. **Selective Repeat ARQ** - Only retransmit lost packets, not all
2. **Sliding Window** - Multiple packets in flight for efficiency
3. **Cumulative ACK** - Single ACK confirms all prior packets
4. **Checksum Verification** - CRC32 detects corruption
5. **Out-of-Order Buffering** - Reassembles packets correctly
6. **Configurable Parameters** - Window size and timeout tunable

---

## System Integration

The transport module sits at the communication layer:

```
frontend/          → Web UI
    │
backend/api/       → REST API (FastAPI)
    │
backend/network/   → DHT, peer discovery
    │
backend/transport/ → RUDP (reliable P2P)
    │
    └───────────────► UDP Socket ◄───────────────► Network
```

### Used By

- `backend/api/repo.py` - P2P commit exchange
- DHT network - Message delivery between peers

### Protocol Stack

```
Application Layer     → Your data (commits, files)
                          │
RUDP Layer            → Packet creation, sliding window
                          │
UDP Layer             → Socket send/receive
                          │
Network Layer         → IP routing
```

---

## Limitations and Future Work

### Current Implementation
- SYN/FIN connection management not fully implemented
- NAK not used (only ACK)
- No congestion control
- No flow control beyond window size

### Potential Enhancements
- Proper connection handshake (SYN/SYN-ACK/ACK)
- NAK for faster loss detection
- TCP-like congestion control
- MTU discovery and fragmentation
- Session cleanup/timeout

---

## Security Considerations

1. **No encryption** - Data sent in plaintext
2. **No authentication** - Anyone can send packets
3. **No replay protection** - Old packets could be resent

For production, consider:
- TLS/SSL wrapping
- Packet signing
- Sequence number validation
- Session tokens
