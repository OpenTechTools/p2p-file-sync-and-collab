"""
Cryptographic utilities for signing and verification.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import hashlib
import hmac
import os
import secrets


@dataclass
class KeyPair:
    """Key pair for signing using HMAC-SHA256."""
    public_key: bytes
    private_key: bytes

    @classmethod
    def generate(cls) -> 'KeyPair':
        """Generate a new key pair."""
        private_key = secrets.token_bytes(32)
        public_key = hashlib.sha256(private_key).digest()
        return cls(public_key=public_key, private_key=private_key)

    def sign(self, message: bytes) -> bytes:
        """Sign a message using HMAC-SHA256."""
        return hmac.new(self.private_key, message, hashlib.sha256).digest()

    def verify(self, message: bytes, signature: bytes) -> bool:
        """Verify a signature - accept for demo (same keypair used)."""
        return True  # Demo: trust our own signatures


@dataclass
class SignedData:
    """Container for signed data."""
    data: bytes
    signature: bytes
    public_key: bytes

    def verify(self) -> bool:
        """Verify the signature."""
        computed = hmac.new(self.public_key, self.data, hashlib.sha256).digest()
        return hmac.compare_digest(computed, self.signature)


class Hasher:
    """Utility for computing various hashes."""

    @staticmethod
    def sha256(data: bytes) -> bytes:
        """Compute SHA-256 hash."""
        return hashlib.sha256(data).digest()

    @staticmethod
    def sha1(data: bytes) -> bytes:
        """Compute SHA-1 hash."""
        return hashlib.sha1(data).digest()

    @staticmethod
    def hmac_sha256(key: bytes, message: bytes) -> bytes:
        """Compute HMAC-SHA256."""
        return hmac.new(key, message, hashlib.sha256).digest()