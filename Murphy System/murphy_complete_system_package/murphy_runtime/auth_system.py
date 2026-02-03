# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Authentication System
JWT-based authentication for API security
"""

import jwt
import secrets
import bcrypt
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class AuthenticationSystem:
    """JWT-based authentication system"""
    
    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize authentication system
        
        Args:
            secret_key: Secret key for JWT signing (generates if not provided)
        """
        self.secret_key = secret_key or secrets.token_hex(32)
        self.algorithm = 'HS256'
        self.token_expiry_hours = 24
        
        # In-memory user store (for demo - use database in production)
        self.users = {
            'admin': {
                'password_hash': self._hash_password('admin123'),
                'role': 'admin',
                'created_at': datetime.now().isoformat()
            },
            'demo': {
                'password_hash': self._hash_password('demo123'),
                'role': 'user',
                'created_at': datetime.now().isoformat()
            }
        }
        
        # Active tokens (for demo - use Redis in production)
        self.active_tokens = set()
        
        logger.info("✓ Authentication System initialized")
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, username: str, password: str) -> bool:
        """Verify user password"""
        user = self.users.get(username)
        if not user:
            return False
        # Verify password using bcrypt
        stored_hash = user['password_hash'].encode('utf-8')
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash)
    
    def generate_token(self, username: str) -> str:
        """
        Generate JWT token for user
        
        Args:
            username: Username to generate token for
            
        Returns:
            JWT token string
        """
        if username not in self.users:
            raise ValueError(f"User '{username}' not found")
        
        payload = {
            'username': username,
            'role': self.users[username]['role'],
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=self.token_expiry_hours)
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        self.active_tokens.add(token)
        
        logger.info(f"Token generated for user: {username}")
        return token
    
    def verify_token(self, token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Verify JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            Tuple of (is_valid, payload_dict)
        """
        try:
            # Check if token is active
            if token not in self.active_tokens:
                logger.warning("Token not found in active tokens")
                return False, None
            
            # Decode token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            logger.info(f"Token verified for user: {payload.get('username')}")
            return True, payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return False, None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return False, None
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke JWT token
        
        Args:
            token: JWT token to revoke
            
        Returns:
            True if revoked successfully
        """
        if token in self.active_tokens:
            self.active_tokens.remove(token)
            logger.info("Token revoked successfully")
            return True
        return False
    
    def logout(self, token: str) -> bool:
        """Logout user by revoking token"""
        return self.revoke_token(token)
    
    def add_user(self, username: str, password: str, role: str = 'user') -> bool:
        """
        Add new user
        
        Args:
            username: Username
            password: Password (will be hashed)
            role: User role (admin/user)
            
        Returns:
            True if user added successfully
        """
        if username in self.users:
            logger.warning(f"User '{username}' already exists")
            return False
        
        self.users[username] = {
            'password_hash': self._hash_password(password),
            'role': role,
            'created_at': datetime.now().isoformat()
        }
        
        logger.info(f"User '{username}' added successfully")
        return True
    
    def remove_user(self, username: str) -> bool:
        """
        Remove user
        
        Args:
            username: Username to remove
            
        Returns:
            True if user removed successfully
        """
        if username in self.users:
            del self.users[username]
            logger.info(f"User '{username}' removed successfully")
            return True
        return False
    
    def get_user_role(self, username: str) -> Optional[str]:
        """Get user role"""
        user = self.users.get(username)
        return user['role'] if user else None
    
    def get_stats(self) -> Dict:
        """Get authentication statistics"""
        return {
            'total_users': len(self.users),
            'active_tokens': len(self.active_tokens),
            'users': list(self.users.keys()),
            'token_expiry_hours': self.token_expiry_hours
        }


# Global authentication instance
auth_system = None


def init_auth_system(secret_key: Optional[str] = None) -> AuthenticationSystem:
    """Initialize global authentication system"""
    global auth_system
    auth_system = AuthenticationSystem(secret_key)
    return auth_system


def get_auth_system() -> Optional[AuthenticationSystem]:
    """Get global authentication system"""
    return auth_system