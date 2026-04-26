# Network Module

## Purpose
Implements Kademlia DHT for peer-to-peer peer discovery and routing in the decentralized network.

## Components
- `dht.py` - Core DHT implementation (NodeID, KBucket, RoutingTable, DHTNode)
- `protocol.py` - DHT message types and serialization

## Key Features
- 160-bit node IDs using SHA-256
- XOR metric for distance calculation
- k-buckets with size 20
- FIND_NODE, PING, STORE, FIND_VALUE operations

## System Connection
- Used by `api/repo.py` for peer discovery
- Integrates with `transport` for network communication
- Nodes are identified by their 160-bit IDs in the P2P network