# Transport Module

## Purpose
Implements Reliable UDP (RUDP) using Selective Repeat ARQ for guaranteed packet delivery over unreliable networks.

## Components
- `rudp.py` - Core RUDP protocol (Packet, SlidingWindow, RUDPSession, RUDPProtocol)

## Key Features
- Selective Repeat ARQ for reliable transmission
- Sliding window flow control
- ACK/NAK based acknowledgment
- Checksum verification for data integrity
- Configurable window size and timeout

## System Connection
- Base transport layer for all P2P communication
- Used by `network/dht.py` for DHT message exchange
- Provides reliable data transfer between peers