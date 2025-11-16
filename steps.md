# Steps(include the steps to make this project)

The project is done in 3 phases of development 

### Phase 1(Foundation and immutability) :

1. **Peer Identity & Cryptography**: Implement Public/Private Key generation for peer identity (NodeID) and implement core digital signature and verification utilities.

2. **Kademlia Networking**: Set up the basic Kademlia DHT client to handle peer discovery and routing tables (k-buckets). Implement the basic FIND_NODE RPC.

3. **Merkle DAG Data Model**: Implement file chunking and Content-Addressing (CID) based on cryptographic hashing. Define the core Blob, Tree, and Commit data structures necessary to represent file history immutably.

4. **Custom RUDP Transport**: Implement the basic UDP sockets for direct peer-to-peer connection. Define the simple packet structure including a Sequence Number and Checksum but without full reliability yet.

5. **Local Repository Management**: Create basic CLI commands (init, commit) to test local creation and committing of text-based files, generating the Root Commit CID.

### Phase 2(Security and collaboration logic) :

1. **RUDP Reliability Layer**: Finalize the Reliable UDP (RUDP) transport by implementing the Selective Repeat ARQ mechanism: ACKs, Timeout Logic, and Retry Counter to guarantee reliable delivery of small data packets.

2. **Authorization CRDT**: Implement a Conflict-Free Replicated Data Type (CRDT) (e.g., LWW-Set) to maintain the decentralized, self-merging list of Authorized Collaborator Public Keys.

3. **SMPP Protocol Implementation**: Implement the Signed Merkle Pointer Protocol (SMPP) record structure. Implement the logic to digitally sign this record (linking the latest Commit CID to the latest CRDT CID) using the repository owner's private key.

4. **Secure Publishing Guardrails**: Modify the Kademlia STORE RPC to act as a security gate. Before storing an SMPP record, the node must verify the digital signature against the public keys defined in the local Authorization CRDT.

5. **Basic Data Exchange**: Implement a simple GET/PUT protocol over RUDP to allow peers to request specific Blob CIDs from known hosts.

### Phase 3(Synchornization, Experience and paper finalization) :

1. **Full Synchronization Logi**c: Implement the full sync or pull workflow: 1) Retrieve the latest validated SMPP record via Kademlia. 2) Compare its Commit CID history to the local history. 3) Download missing Blob chunks using the RUDP Swarming Protocol (switching peers on transfer failure).

2. **Conflict Resolution**: Implement CRDT Merge Logic for seamless, automatic merging of metadata updates (e.g., collaborator list changes). Implement a basic conflict mechanism for text file content (e.g., three-way merge or conflict flagging).

3. **User Experience (CLI/GUI)**: Build the final interface. Focus on clear feedback for Signature Validation (e.g., showing a commit as "Verified" or "Unauthorized") and commands for key management and adding/removing collaborators (updating the CRDT).

4. **Security Hardening & Documentation**: Implement DTLS (or another suitable encryption layer) over RUDP for end-to-end encryption. Finalize the academic paper, focusing the thesis on the SMPP protocol as the core novel contribution to solving trustless authorization in decentralized version control.

