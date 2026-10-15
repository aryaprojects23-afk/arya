"""
HarvestLink 2.0 - Authentication & Role-Based Access Control (RBAC) Service
Provides password hashing, user registration, role enforcement, demo role switching,
and session management.
"""

import hashlib
import uuid
import secrets
from typing import Optional, Dict, Any, List
from backend.database import db_session

# Simple token storage for sessions
_ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}

def hash_password(password: str) -> str:
    """Hash password with SHA-256 and constant salt."""
    salt = "harvestlink_secure_salt_2026"
    return hashlib.sha256(f"{password}{salt}".encode("utf-8")).hexdigest()

def create_user(
    phone: str,
    password: str,
    full_name: str,
    role: str,
    state: str,
    district: str,
    email: str = None,
    preferred_language: str = "en",
    organization_name: str = None,
    pincode: str = None
) -> Dict[str, Any]:
    """Register a new user and initialize user profile and language preference."""
    valid_roles = ('farmer', 'consumer', 'restaurant', 'retailer', 'wholesaler', 'admin')
    if role not in valid_roles:
        raise ValueError(f"Invalid role: {role}. Must be one of {valid_roles}")

    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    pwd_hash = hash_password(password)

    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (id, phone, email, password_hash, full_name, role, is_active, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, 1, 1)
        """, (user_id, phone, email, pwd_hash, full_name, role))

        cursor.execute("""
            INSERT INTO user_profiles (user_id, organization_name, state, district, pincode)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, organization_name, state, district, pincode))

        cursor.execute("""
            INSERT INTO user_language_preferences (user_id, preferred_language)
            VALUES (?, ?)
        """, (user_id, preferred_language))

    return {
        "id": user_id,
        "phone": phone,
        "full_name": full_name,
        "role": role,
        "state": state,
        "district": district,
        "preferred_language": preferred_language
    }

def authenticate_user(phone: str, password: str) -> Optional[Dict[str, Any]]:
    """Validate credentials and return user dictionary with profile."""
    pwd_hash = hash_password(password)
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.phone, u.email, u.full_name, u.role, u.is_verified,
                   p.state, p.district, p.organization_name,
                   COALESCE(lp.preferred_language, 'en') as preferred_language
            FROM users u
            LEFT JOIN user_profiles p ON u.id = p.user_id
            LEFT JOIN user_language_preferences lp ON u.id = lp.user_id
            WHERE u.phone = ? AND u.password_hash = ? AND u.is_active = 1
        """, (phone, pwd_hash))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def create_session_token(user: Dict[str, Any]) -> str:
    """Generate session token and store in session table."""
    token = secrets.token_hex(24)
    _ACTIVE_SESSIONS[token] = user
    return token

def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """Resolve active user session from token."""
    return _ACTIVE_SESSIONS.get(token)

def update_user_language(user_id: str, language_code: str) -> bool:
    """Persist user language preference in the database."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_language_preferences (user_id, preferred_language)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                preferred_language = excluded.preferred_language,
                updated_at = CURRENT_TIMESTAMP;
        """, (user_id, language_code))
        return True

def get_demo_users() -> List[Dict[str, Any]]:
    """Return pre-configured demo personas representing different marketplace roles."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.phone, u.full_name, u.role,
                   p.state, p.district, p.organization_name,
                   COALESCE(lp.preferred_language, 'en') as preferred_language
            FROM users u
            JOIN user_profiles p ON u.id = p.user_id
            LEFT JOIN user_language_preferences lp ON u.id = lp.user_id
            WHERE u.id LIKE 'demo_%'
            ORDER BY u.role ASC
        """)
        return [dict(r) for r in cursor.fetchall()]
