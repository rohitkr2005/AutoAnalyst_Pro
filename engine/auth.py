"""
AutoAnalyst Pro - Authentication & User Persistence Layer
Implements SQLite storage, Werkzeug password hashing, session tracking, and user activity logging.
"""

import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional
from werkzeug.security import generate_password_hash, check_password_hash

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "users.db")


def get_db_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    """Initializes SQLite schema and creates default demo analyst account if missing."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT DEFAULT 'Data Analyst',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    )
    """)

    # User activity history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        dataset_name TEXT NOT NULL,
        records_count INTEGER NOT NULL,
        health_score REAL NOT NULL,
        action_type TEXT DEFAULT 'Analyzed Dataset',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)

    # Seed default demo account
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        demo_hash = generate_password_hash("Password123!")
        cursor.execute("""
        INSERT INTO users (username, email, password_hash, full_name, role)
        VALUES (?, ?, ?, ?, ?)
        """, (
            "admin",
            "analyst@autoanalyst.io",
            demo_hash,
            "Chief Data Analyst",
            "Lead Analyst"
        ))

    conn.commit()
    conn.close()


def register_user(username: str, email: str, password: str, full_name: str) -> Dict[str, Any]:
    """Registers a new user account with secure password hashing."""
    username = username.strip().lower()
    email = email.strip().lower()
    full_name = full_name.strip()

    if len(username) < 3:
        return {"success": False, "message": "Username must be at least 3 characters long."}
    if "@" not in email or "." not in email:
        return {"success": False, "message": "Please enter a valid email address."}
    if len(password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters long."}
    if not full_name:
        full_name = username.title()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if username or email exists
    cursor.execute("SELECT id, username, email FROM users WHERE username = ? OR email = ?", (username, email))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        if existing["username"] == username:
            return {"success": False, "message": "Username is already taken. Please choose another."}
        else:
            return {"success": False, "message": "An account with this email already exists."}

    pwd_hash = generate_password_hash(password)
    try:
        cursor.execute("""
        INSERT INTO users (username, email, password_hash, full_name, role, last_login)
        VALUES (?, ?, ?, ?, 'Data Analyst', CURRENT_TIMESTAMP)
        """, (username, email, pwd_hash, full_name))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        return {
            "success": True,
            "user": {
                "id": user_id,
                "username": username,
                "email": email,
                "full_name": full_name,
                "role": "Data Analyst"
            }
        }
    except Exception as e:
        conn.close()
        return {"success": False, "message": f"Database error: {str(e)}"}


def authenticate_user(username_or_email: str, password: str) -> Dict[str, Any]:
    """Verifies user credentials and returns profile if valid."""
    identifier = username_or_email.strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, username, email, password_hash, full_name, role
    FROM users
    WHERE username = ? OR email = ?
    """, (identifier, identifier))
    user_row = cursor.fetchone()

    if not user_row or not check_password_hash(user_row["password_hash"], password):
        conn.close()
        return {"success": False, "message": "Invalid username/email or password."}

    # Update last login
    cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_row["id"],))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "user": {
            "id": user_row["id"],
            "username": user_row["username"],
            "email": user_row["email"],
            "full_name": user_row["full_name"],
            "role": user_row["role"]
        }
    }


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves user profile data by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, username, email, full_name, role, created_at, last_login
    FROM users WHERE id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "full_name": row["full_name"],
        "role": row["role"],
        "created_at": str(row["created_at"]),
        "last_login": str(row["last_login"])
    }


def record_user_activity(user_id: int, dataset_name: str, records_count: int, health_score: float, action_type: str = "Analyzed Dataset"):
    """Records user dataset analysis in activity history."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO user_activity (user_id, dataset_name, records_count, health_score, action_type)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, dataset_name, records_count, health_score, action_type))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging user activity: {e}")


def get_user_history(user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieves recent datasets analyzed by the user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT dataset_name, records_count, health_score, action_type, created_at
    FROM user_activity
    WHERE user_id = ?
    ORDER BY id DESC LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()

    history = []
    for r in rows:
        history.append({
            "dataset_name": r["dataset_name"],
            "records_count": r["records_count"],
            "health_score": round(r["health_score"], 1),
            "action_type": r["action_type"],
            "created_at": str(r["created_at"])
        })
    return history
