"""API module with controller pattern."""

from service import UserService, User
from typing import List, Optional


class UserController:
    """Controller for user API endpoints."""
    
    def __init__(self):
        self.service = UserService()
    
    def create_user(self, name: str, email: str) -> dict:
        user = self.service.create_user(name, email)
        return {"id": user.id, "name": user.name, "email": user.email}
    
    def get_user(self, user_id: int) -> Optional[dict]:
        user = self.service.get_user(user_id)
        if user:
            return {"id": user.id, "name": user.name, "email": user.email}
        return None
    
    def list_users(self) -> List[dict]:
        users = self.service.list_users()
        return [{"id": u.id, "name": u.name, "email": u.email} for u in users]


def create_app():
    """Factory for creating the app."""
    return UserController()


# Old commented out code - fossil
# def old_create_user(name, email):
#     return {"name": name, "email": email}
# 
# class OldUserManager:
#     def __init__(self):
#         pass