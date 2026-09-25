"""
AutoAnalyst Pro - Authentication & User Persistence Layer
Implements dual-database architecture:
- Supabase PostgreSQL (Cloud / Production) when DATABASE_URL is configured
- SQLite local database (Offline / Development) as seamless fallback
Includes password hashing, session tracking, and user activity logging.
"""

import os
import json
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Automatically load environment variables from .env in project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE)
load_dotenv()

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

DB_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DB_DIR, "users.db")


def get_database_url() -> Optional[str]:
    """Returns normalized PostgreSQL connection URL if configured in environment."""
    url = os.environ.get("DATABASE_URL")
    if url and url.strip():
        url = url.strip()
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    return None


def is_postgres() -> bool:
    """Returns True if PostgreSQL is enabled and driver is installed."""
    return bool(get_database_url() and PSYCOPG2_AVAILABLE)


class PGCursorWrapper:
    """
    Transparent cursor wrapper that adapts SQLite parameter placeholders (?)
    to PostgreSQL placeholders (%s) and populates lastrowid for INSERT statements.
    """
    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = None

    def execute(self, query: str, params=None):
        pg_query = query.replace('?', '%s')
        is_insert = pg_query.strip().upper().startswith("INSERT INTO")
        has_returning = "RETURNING" in pg_query.upper()

        if is_insert and not has_returning:
            pg_query_with_return = pg_query.rstrip().rstrip(";") + " RETURNING id;"
            try:
                if params:
                    self._cursor.execute(pg_query_with_return, params)
                else:
                    self._cursor.execute(pg_query_with_return)
                row = self._cursor.fetchone()
                if row:
                    self.lastrowid = row["id"] if isinstance(row, dict) else row[0]
                return self
            except Exception:
                pass

        if params:
            self._cursor.execute(pg_query, params)
        else:
            self._cursor.execute(pg_query)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        self._cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PGConnectionWrapper:
    """Connection wrapper for psycopg2 returning dictionary rows via RealDictCursor."""
    def __init__(self, pg_conn):
        self._conn = pg_conn

    def cursor(self):
        return PGCursorWrapper(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._conn.rollback()
        else:
            self._conn.commit()
        self.close()


def get_db_connection():
    """
    Provides a unified database connection.
    Connects to Supabase PostgreSQL when DATABASE_URL is set;
    falls back to local SQLite at data/users.db when offline/unset.
    Automatically handles IPv4 pooler fallback for IPv6-restricted cloud containers (like Render).
    """
    db_url = get_database_url()
    if db_url and PSYCOPG2_AVAILABLE:
        try:
            pg_conn = psycopg2.connect(db_url, connect_timeout=5)
            return PGConnectionWrapper(pg_conn)
        except Exception as e:
            # Check if this was a Supabase Direct URL (IPv6-only, which fails on Render IPv4)
            if "db." in db_url and ".supabase.co" in db_url:
                import re
                m = re.match(r"postgresql://([^:]+):([^@]+)@db\.([^.]+)\.supabase\.co(?::\d+)?/(.+)", db_url)
                if m:
                    user, pwd, ref, dbname = m.groups()
                    pooler_url = f"postgresql://postgres.{ref}:{pwd}@aws-0-ap-south-1.pooler.supabase.com:5432/{dbname}"
                    try:
                        print(f"[AutoAnalyst Pro] Direct connection failed ({e}). Auto-switching to Supabase IPv4 Pooler...", flush=True)
                        pg_conn = psycopg2.connect(pooler_url, connect_timeout=8)
                        return PGConnectionWrapper(pg_conn)
                    except Exception as e2:
                        print(f"[AutoAnalyst Pro] Supabase IPv4 Pooler also failed: {e2}", flush=True)
            # Re-raise original error if pooler fallback could not resolve it
            raise e

    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    """Initializes schema (PostgreSQL or SQLite) and creates default demo analyst account if missing."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if is_postgres():
        # PostgreSQL Schema for Supabase
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name VARCHAR(150) NOT NULL,
            role VARCHAR(50) DEFAULT 'Data Analyst',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_activity (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            dataset_name VARCHAR(255) NOT NULL,
            records_count INTEGER NOT NULL,
            health_score REAL NOT NULL,
            action_type VARCHAR(100) DEFAULT 'Analyzed Dataset',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_verifications (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            otp_code VARCHAR(10) NOT NULL,
            purpose VARCHAR(50) NOT NULL,
            payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0
        );
        """)
    else:
        # SQLite Schema
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

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            otp_code TEXT NOT NULL,
            purpose TEXT NOT NULL,
            payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0
        )
        """)

    # Seed default demo account
    cursor.execute("SELECT id FROM users WHERE username = ?", ("admin",))
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


def get_user_history(user_id: int, limit: int = 30) -> List[Dict[str, Any]]:
    """Retrieves recent datasets analyzed by the user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, dataset_name, records_count, health_score, action_type, created_at
    FROM user_activity
    WHERE user_id = ?
    ORDER BY id DESC LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()

    history = []
    for r in rows:
        history.append({
            "id": r["id"],
            "dataset_name": r["dataset_name"],
            "records_count": r["records_count"],
            "health_score": round(r["health_score"], 1),
            "action_type": r["action_type"],
            "created_at": str(r["created_at"])
        })
    return history


def clear_user_history(user_id: int) -> bool:
    """Clears all activity history for a specific user."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_activity WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error clearing history: {e}")
        return False


def create_otp(email: str, purpose: str, payload: Optional[Dict[str, Any]] = None, expiry_minutes: int = 10) -> str:
    """Generates a secure 6-digit OTP code and stores it in the database with expiration."""
    email = email.strip().lower()
    otp_code = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(minutes=expiry_minutes)
    payload_json = json.dumps(payload) if payload else None

    conn = get_db_connection()
    cursor = conn.cursor()
    # Mark old unused OTPs for this email and purpose as used
    cursor.execute("UPDATE otp_verifications SET used = 1 WHERE email = ? AND purpose = ?", (email, purpose))
    cursor.execute("""
    INSERT INTO otp_verifications (email, otp_code, purpose, payload, expires_at, used)
    VALUES (?, ?, ?, ?, ?, 0)
    """, (email, otp_code, purpose, payload_json, expires_at.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

    return otp_code


def verify_otp(email: str, otp_code: str, purpose: str) -> Dict[str, Any]:
    """Validates 6-digit OTP code, expiration, and returns stored payload."""
    email = email.strip().lower()
    otp_code = otp_code.strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, payload, expires_at, used
    FROM otp_verifications
    WHERE email = ? AND otp_code = ? AND purpose = ? AND used = 0
    ORDER BY id DESC LIMIT 1
    """, (email, otp_code, purpose))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"valid": False, "message": "Invalid or expired verification code."}

    # Check expiration
    exp = row["expires_at"]
    if isinstance(exp, str):
        expires_at = datetime.strptime(exp, "%Y-%m-%d %H:%M:%S")
    elif isinstance(exp, datetime):
        expires_at = exp
    else:
        expires_at = datetime.strptime(str(exp), "%Y-%m-%d %H:%M:%S")

    if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is not None:
        now = datetime.now(timezone.utc)
    else:
        now = datetime.utcnow()

    if now > expires_at:
        cursor.execute("UPDATE otp_verifications SET used = 1 WHERE id = ?", (row["id"],))
        conn.commit()
        conn.close()
        return {"valid": False, "message": "Verification code has expired. Please request a new one."}

    # Mark as used
    cursor.execute("UPDATE otp_verifications SET used = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()

    payload = json.loads(row["payload"]) if row["payload"] else {}
    return {"valid": True, "payload": payload}


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Looks up user record by email address."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, username, email, full_name, role
    FROM users WHERE email = ?
    """, (email.strip().lower(),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "full_name": row["full_name"],
        "role": row["role"]
    }


def reset_password_with_otp(email: str, otp_code: str, new_password: str) -> Dict[str, Any]:
    """Validates reset OTP and updates user password hash."""
    if len(new_password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters long."}

    v_res = verify_otp(email, otp_code, "reset_password")
    if not v_res["valid"]:
        return {"success": False, "message": v_res["message"]}

    pwd_hash = generate_password_hash(new_password)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ? WHERE email = ?", (pwd_hash, email.strip().lower()))
    conn.commit()
    conn.close()

    return {"success": True, "message": "Password reset successfully. You can now sign in with your new password."}

