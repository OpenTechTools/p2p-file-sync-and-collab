"""
User management system for multi-user collaboration.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict
import os
import json
import secrets
import hashlib

from backend.security.crypto import KeyPair


@dataclass
class User:
    """User with unique ID and keypair."""
    username: str
    user_id: str
    public_key: bytes
    keypair: KeyPair = field(repr=False)

    @classmethod
    def create(cls, username: str) -> 'User':
        """Create a new user with generated keypair."""
        user_id = secrets.token_hex(16)
        keypair = KeyPair.generate()
        return cls(
            username=username,
            user_id=user_id,
            public_key=keypair.public_key,
            keypair=keypair
        )

    def to_dict(self) -> dict:
        """Serialize user (without private key)."""
        return {
            'username': self.username,
            'user_id': self.user_id,
            'public_key': self.public_key.hex(),
        }

    @classmethod
    def from_dict(cls, data: dict, keypair: KeyPair) -> 'User':
        """Deserialize user."""
        return cls(
            username=data['username'],
            user_id=data['user_id'],
            public_key=bytes.fromhex(data['public_key']),
            keypair=keypair
        )


class UserManager:
    """Manages users and sessions."""

    def __init__(self, storage_path: str = "./data"):
        self.storage_path = storage_path
        self.users: Dict[str, User] = {}
        self.current_user: Optional[User] = None
        os.makedirs(storage_path, exist_ok=True)
        self._load_users()

    def _get_users_file(self) -> str:
        return os.path.join(self.storage_path, "users.json")

    def _get_session_file(self) -> str:
        return os.path.join(self.storage_path, "session.json")

    def _load_users(self):
        """Load users from disk."""
        users_file = self._get_users_file()
        if os.path.exists(users_file):
            with open(users_file, 'r') as f:
                users_data = json.load(f)
            for user_data in users_data:
                keypair = KeyPair.generate()
                user = User.from_dict(user_data, keypair)
                self.users[user.user_id] = user

    def _save_users(self):
        """Save users to disk."""
        users_file = self._get_users_file()
        users_data = [u.to_dict() for u in self.users.values()]
        with open(users_file, 'w') as f:
            json.dump(users_data, f)

    def create_user(self, username: str) -> User:
        """Create a new user."""
        user = User.create(username)
        self.users[user.user_id] = user
        self._save_users()
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self.users.get(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        for user in self.users.values():
            if user.username == username:
                return user
        return None

    def list_users(self) -> list:
        """List all users."""
        return [u.to_dict() for u in self.users.values()]

    def login(self, user_id: str) -> Optional[User]:
        """Login user (set current session)."""
        user = self.users.get(user_id)
        if user:
            self.current_user = user
            session = {'user_id': user_id}
            with open(self._get_session_file(), 'w') as f:
                json.dump(session, f)
        return user

    def logout(self):
        """Logout current user."""
        self.current_user = None
        if os.path.exists(self._get_session_file()):
            os.remove(self._get_session_file())

    def get_current_user(self) -> Optional[User]:
        """Get currently logged in user."""
        if self.current_user:
            return self.current_user
        
        session_file = self._get_session_file()
        if os.path.exists(session_file):
            with open(session_file, 'r') as f:
                session = json.load(f)
            user_id = session.get('user_id')
            if user_id and user_id in self.users:
                self.current_user = self.users[user_id]
                return self.current_user
        return None


def create_demo_users(storage_path: str = "./data") -> UserManager:
    """Create demo users for testing."""
    manager = UserManager(storage_path)
    
    # Create demo users if none exist
    if not manager.users:
        deepanshu = manager.create_user("Deepanshu")
        priya = manager.create_user("Priya")
        mohit = manager.create_user("Mohit")
        tanya = manager.create_user("Tanya")
        print(f"Created demo users: Deepanshu, Priya, Mohit, Tanya")
    
    return manager