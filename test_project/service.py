"""Test module with various patterns and issues."""

import os
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class User:
    id: int
    name: str
    email: str


class UserRepository:
    """Repository pattern for user management."""
    
    def __init__(self):
        self._users: List[User] = []
    
    def create(self, user: User) -> User:
        self._users.append(user)
        return user
    
    def find_by_id(self, user_id: int) -> Optional[User]:
        for user in self._users:
            if user.id == user_id:
                return user
        return None
    
    def find_all(self) -> List[User]:
        return self._users.copy()
    
    def delete(self, user_id: int) -> bool:
        for i, user in enumerate(self._users):
            if user.id == user_id:
                del self._users[i]
                return True
        return False


class UserService:
    """God class - does too many things."""
    
    def __init__(self):
        self.repo = UserRepository()
        self.cache = {}
        self.logger = None
        self.config = {}
        self.metrics = {}
        self.notifications = []
        self.audit_log = []
    
    def create_user(self, name: str, email: str) -> User:
        user = User(id=len(self.repo.find_all()) + 1, name=name, email=email)
        self.repo.create(user)
        self._log_audit("CREATE", user)
        self._send_notification(user)
        self._update_metrics("user_created")
        return user
    
    def get_user(self, user_id: int) -> Optional[User]:
        if user_id in self.cache:
            return self.cache[user_id]
        user = self.repo.find_by_id(user_id)
        if user:
            self.cache[user_id] = user
        return user
    
    def update_user(self, user_id: int, name: str = None, email: str = None) -> Optional[User]:
        user = self.get_user(user_id)
        if not user:
            return None
        if name:
            user.name = name
        if email:
            user.email = email
        self._log_audit("UPDATE", user)
        self._invalidate_cache(user_id)
        return user
    
    def delete_user(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        result = self.repo.delete(user_id)
        if result:
            self._log_audit("DELETE", user)
            self._invalidate_cache(user_id)
        return result
    
    def list_users(self) -> List[User]:
        return self.repo.find_all()
    
    def _log_audit(self, action: str, user: User):
        self.audit_log.append(f"{action}: {user.id}")
    
    def _send_notification(self, user: User):
        self.notifications.append(f"Welcome {user.name}")
    
    def _update_metrics(self, key: str):
        self.metrics[key] = self.metrics.get(key, 0) + 1
    
    def _invalidate_cache(self, user_id: int):
        self.cache.pop(user_id, None)
    
    def generate_report(self) -> str:
        return f"Users: {len(self.repo.find_all())}"
    
    def export_data(self) -> dict:
        return {"users": [u.__dict__ for u in self.repo.find_all()]}
    
    def import_data(self, data: dict):
        pass
    
    def backup(self):
        pass
    
    def restore(self):
        pass
    
    def validate_email(self, email: str) -> bool:
        return "@" in email
    
    def hash_password(self, password: str) -> str:
        return "hashed_" + password
    
    def check_permissions(self, user_id: int, permission: str) -> bool:
        return True
    
    def send_email(self, to: str, subject: str, body: str):
        pass
    
    def schedule_task(self, task: str, when: str):
        pass


def factory_create_user(name: str, email: str) -> User:
    """Factory function for creating users."""
    return User(id=0, name=name, email=email)


def legacy_function():
    """This function is never called - dead code."""
    x = 42
    y = 100
    z = 3.14159
    return x + y + z


# Magic numbers
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
BUFFER_SIZE = 8192