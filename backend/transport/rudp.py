"""
Reliable UDP (RUDP) implementation using Selective Repeat ARQ.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from enum import Enum
import time
import struct
import hashlib


class PacketType(Enum):
    DATA = 0x01
    ACK = 0x02
    NAK = 0x03
    SYN = 0x04
    FIN = 0x05


@dataclass
class Packet:
    """RUDP packet structure."""
    seq_num: int
    ack_num: int
    packet_type: PacketType
    data: bytes
    checksum: int = 0

    def compute_checksum(self) -> int:
        """Compute CRC32 checksum of packet."""
        import zlib
        header = struct.pack('!IIB', self.seq_num, self.ack_num, self.packet_type.value)
        return zlib.crc32(header + self.data) & 0xFFFFFFFF

    def verify(self) -> bool:
        """Verify packet integrity."""
        return self.checksum == self.compute_checksum()


class SlidingWindow:
    """Selective Repeat ARQ sliding window."""

    def __init__(self, window_size: int = 16, timeout: float = 5.0):
        self.window_size = window_size
        self.timeout = timeout
        self.unacked: Dict[int, Packet] = {}
        self.received: Dict[int, bytes] = {}
        self.base_seq: int = 0
        self.next_seq: int = 0
        self.timers: Dict[int, float] = {}

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

    def receive_ack(self, ack_num: int) -> None:
        """Process incoming ACK."""
        if ack_num >= self.base_seq:
            for seq in list(self.unacked.keys()):
                if seq < ack_num:
                    del self.unacked[seq]
                    self.timers.pop(seq, None)
            self.base_seq = ack_num

    def receive_packet(self, packet: Packet) -> Optional[bytes]:
        """Process incoming data packet."""
        if packet.seq_num < self.base_seq:
            return None  # Already acknowledged
        if packet.seq_num in self.received:
            return None  # Duplicate
        self.received[packet.seq_num] = packet.data
        return packet.data

    def get_ordered_data(self) -> List[bytes]:
        """Get all ordered data starting from base."""
        result = []
        seq = self.base_seq
        while seq in self.received:
            result.append(self.received.pop(seq))
            seq += 1
        return result

    def retransmit_needed(self) -> List[Packet]:
        """Get packets that need retransmission."""
        now = time.time()
        result = []
        for seq, pkt in list(self.unacked.items()):
            if now - self.timers[seq] > self.timeout:
                self.timers[seq] = now
                result.append(pkt)
        return result


class RUDPSession:
    """RUDP session for reliable communication."""

    def __init__(self, remote_addr: tuple, window_size: int = 16):
        self.remote_addr = remote_addr
        self.sender = SlidingWindow(window_size)
        self.receiver = SlidingWindow(window_size)
        self.connected = False

    def send(self, data: bytes) -> Optional[Packet]:
        """Send data reliably."""
        return self.sender.send(data)

    def receive(self, packet: Packet) -> Optional[bytes]:
        """Process received packet."""
        if packet.packet_type == PacketType.DATA:
            return self.sender.receive_packet(packet)
        elif packet.packet_type == PacketType.ACK:
            self.sender.receive_ack(packet.ack_num)
        return None


class RUDPProtocol:
    """RUDP protocol handler."""

    def __init__(self, local_port: int = 0):
        self.local_port = local_port
        self.sessions: Dict[tuple, RUDPSession] = {}

    def create_session(self, remote_addr: tuple) -> RUDPSession:
        """Create or get existing session."""
        if remote_addr not in self.sessions:
            self.sessions[remote_addr] = RUDPSession(remote_addr)
        return self.sessions[remote_addr]

    def send_packet(self, addr: tuple, packet: Packet) -> bytes:
        """Serialize packet for sending."""
        header = struct.pack('!IIBI',
            packet.seq_num,
            packet.ack_num,
            packet.packet_type.value,
            packet.checksum
        )
        return header + packet.data

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