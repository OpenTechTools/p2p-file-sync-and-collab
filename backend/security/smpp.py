"""
Signed Merkle Pointer Protocol (SMPP) for commit validation.
"""

from dataclasses import dataclass
from typing import Optional, Dict
import time
import json
import hashlib

from .crypto import KeyPair, SignedData
from ..crdt.lww_set import CRDTState


@dataclass
class SMPPRecord:
    """SMPP record structure."""
    repo_id: str
    commit_cid: str
    crdt_state_cid: str
    timestamp: float
    signature: bytes

    def to_bytes(self) -> bytes:
        """Serialize record to bytes."""
        return json.dumps({
            'repo_id': self.repo_id,
            'commit_cid': self.commit_cid,
            'crdt_state_cid': self.crdt_state_cid,
            'timestamp': self.timestamp,
        }).encode()

    @classmethod
    def from_bytes(cls, data: bytes, signature: bytes) -> 'SMPPRecord':
        """Deserialize record from bytes."""
        parsed = json.loads(data.decode())
        return cls(
            repo_id=parsed['repo_id'],
            commit_cid=parsed['commit_cid'],
            crdt_state_cid=parsed['crdt_state_cid'],
            timestamp=parsed['timestamp'],
            signature=signature
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'repo_id': self.repo_id,
            'commit_cid': self.commit_cid,
            'crdt_state_cid': self.crdt_state_cid,
            'timestamp': self.timestamp,
            'signature': self.signature.hex()
        }


@dataclass
class SMPPValidator:
    """Validates SMPP records."""

    def __init__(self, crdt_manager, object_store, clock_skew_tolerance: float = 300):
        self.crdt_manager = crdt_manager
        self.object_store = object_store
        self.clock_skew_tolerance = clock_skew_tolerance
        self.seen_records: Dict[str, float] = {}

    def create_record(self, key_pair: KeyPair, repo_id: str, commit_cid: str, crdt_state_cid: str) -> SMPPRecord:
        """Create a new SMPP record."""
        timestamp = time.time()
        record = SMPPRecord(
            repo_id=repo_id,
            commit_cid=commit_cid,
            crdt_state_cid=crdt_state_cid,
            timestamp=timestamp,
            signature=b''
        )
        signature = key_pair.sign(record.to_bytes())
        record.signature = signature
        return record

    def validate(self, record: SMPPRecord, public_key: bytes) -> tuple[bool, str]:
        """
        Validate SMPP record in 4 steps:
        1. Verify signature
        2. Fetch CRDT state
        3. Check authorization
        4. Check timestamp (anti-replay)
        """
        step = 0

        step += 1
        if not self._verify_signature(record, public_key):
            return False, f"Step {step}: Invalid signature"

        step += 1
        crdt_state = self._fetch_crdt_state(record.crdt_state_cid)
        if crdt_state is None:
            return False, f"Step {step}: CRDT state not found"

        step += 1
        if not self._check_authorization(crdt_state, public_key):
            return False, f"Step {step}: Unauthorized"

        step += 1
        if not self._check_timestamp(record):
            return False, f"Step {step}: Timestamp rejected (replay or clock skew)"

        return True, "Valid"

    def _verify_signature(self, record: SMPPRecord, public_key: bytes) -> bool:
        """Step 1: Verify signature."""
        try:
            key_pair = KeyPair(public_key=public_key, private_key=b'')
            return key_pair.verify(record.to_bytes(), record.signature)
        except Exception:
            return False

    def _fetch_crdt_state(self, crdt_state_cid: str) -> Optional[CRDTState]:
        """Step 2: Fetch CRDT state."""
        from ..storage.merkle import CID
        cid = CID.from_hex(crdt_state_cid)
        state_obj = self.object_store.get_blob(cid)
        if state_obj:
            import json
            try:
                data = json.loads(state_obj.data.decode())
                return CRDTState.from_dict(data)
            except Exception:
                pass
        return None

    def _check_authorization(self, crdt_state: CRDTState, public_key: bytes) -> bool:
        """Step 3: Check authorization."""
        key_hex = public_key.hex()
        return crdt_state.is_authorized(key_hex)

    def _check_timestamp(self, record: SMPPRecord) -> bool:
        """Step 4: Check timestamp for anti-replay."""
        now = time.time()
        if record.timestamp > now + self.clock_skew_tolerance:
            return False
        if record.timestamp < now - self.clock_skew_tolerance:
            return False

        record_key = f"{record.repo_id}:{record.commit_cid}:{record.timestamp}"
        if record_key in self.seen_records:
            return False

        self.seen_records[record_key] = record.timestamp
        return True


class SMPPStore:
    """Store for SMPP records."""

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        import os
        os.makedirs(storage_path, exist_ok=True)

    def store_record(self, record: SMPPRecord) -> None:
        """Store an SMPP record."""
        import json
        import os
        repo_path = os.path.join(self.storage_path, record.repo_id)
        os.makedirs(repo_path, exist_ok=True)
        filename = f"{record.commit_cid}.json"
        path = os.path.join(repo_path, filename)
        with open(path, 'w') as f:
            json.dump(record.to_dict(), f)

    def get_record(self, repo_id: str, commit_cid: str) -> Optional[SMPPRecord]:
        """Retrieve an SMPP record."""
        import json
        import os
        path = os.path.join(self.storage_path, repo_id, f"{commit_cid}.json")
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            data = json.load(f)
        sig = bytes.fromhex(data['signature'])
        record_data = json.dumps({
            'repo_id': data['repo_id'],
            'commit_cid': data['commit_cid'],
            'crdt_state_cid': data['crdt_state_cid'],
            'timestamp': data['timestamp'],
        }).encode()
        return SMPPRecord.from_bytes(record_data, sig)